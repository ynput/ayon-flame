"""
Basic AYON integration
"""
import contextlib
import os
from copy import deepcopy
import ayon_api
import flame

from ayon_core.host import HostBase, ILoadHost, IPublishHost, IWorkfileHost
from ayon_core.lib import Logger, get_version_from_path
from ayon_core.pipeline import (
    AYON_CONTAINER_ID,
    deregister_creator_plugin_path,
    deregister_loader_plugin_path,
    register_creator_plugin_path,
    register_loader_plugin_path,
    registered_host,
)
from ayon_core.pipeline.context_tools import get_current_project_settings
from pyblish import api as pyblish

from ayon_flame import FLAME_ADDON_ROOT
from ayon_flame.constants import (
    BATCH_CREATOR_IDENTIFIER,
    BATCH_WORKFILE_EXTENSION,
    EDITORIAL_WORKFILE_EXTENSION,
)

from . import batch_utils, editorial_workfile
from .lib import (
    get_current_sequence,
    maintained_segment_selection,
    set_clip_data_marker,
    set_segment_data_marker,
    CTX,
)

PLUGINS_DIR = os.path.join(FLAME_ADDON_ROOT, "plugins")
PUBLISH_PATH = os.path.join(PLUGINS_DIR, "publish")
LOAD_PATH = os.path.join(PLUGINS_DIR, "load")
CREATE_PATH = os.path.join(PLUGINS_DIR, "create")


log = Logger.get_logger(__name__)


class FlameHost(HostBase, IWorkfileHost, ILoadHost, IPublishHost):
    """Registered host, its workfiles are the editorial workfiles.

    Batch groups have their own workfile host, 'FlameBatchHost'.
    """
    name = "flame"

    # Create, Publish and Load tools of the Batch menu use the context of
    # the batch group products. Workfile tools must not, see
    # 'FlameEditorialHost'.
    follow_batch_context = True

    def __init__(self):
        super().__init__()
        self._publish_context_data = {}
        self._ignore_batch_context = False

    def get_containers(self):
        return ls()

    def install(self):
        """Install all requirements for Flame host"""
        install()

    def get_context_data(self):
        """required by IPublishHost"""
        return deepcopy(self._publish_context_data)

    def update_context_data(self, data, changes):
        """required by IPublishHost"""
        self._publish_context_data = deepcopy(data)

    def get_workfile_extensions(self):
        return [EDITORIAL_WORKFILE_EXTENSION]

    def save_workfile(self, dst_path=None):
        if not dst_path:
            dst_path = self.get_current_workfile()
        if not dst_path:
            raise RuntimeError(
                "No editorial workfile was saved or opened for this task yet, "
                "use Save As."
            )

        log.info("Writing AYON editorial workfile %r", dst_path)
        # Session context, not the Batch metadata context of the override.
        editorial_workfile.save_editorial_workfile(
            dst_path, super().get_current_context()
        )

    def open_workfile(self, filepath):
        log.info("Opening AYON editorial workfile %r", filepath)
        editorial_workfile.open_editorial_workfile(filepath)

    def get_current_workfile(self):
        return editorial_workfile.get_current_editorial_workfile()

    def workfile_has_unsaved_changes(self):
        # Flame has no "dirty" state in its Python API.
        return None

    def save_workfile_with_context(self, *args, **kwargs):
        with self._session_context():
            super().save_workfile_with_context(*args, **kwargs)

    def open_workfile_with_context(self, *args, **kwargs):
        with self._session_context():
            super().open_workfile_with_context(*args, **kwargs)

    @contextlib.contextmanager
    def _session_context(self):
        """Editorial workfiles follow the session context only.

        A Batch menu action leaves 'CTX.context' set, which would make
        'get_current_context' return the Batch metadata context.
        """
        self._ignore_batch_context = True
        try:
            yield
        finally:
            self._ignore_batch_context = False

    def get_current_context(self):
        current_ctx = super().get_current_context()

        # Flame can be used as a multi-workfile host.
        # When working with batch, we try to get the
        # current context from the batch products.
        if (
            self.follow_batch_context
            and CTX.context == "FlameMenuBatch"
            and not self._ignore_batch_context
        ):
            batch_context = batch_utils.get_batch_products_context()
            if batch_context:
                current_ctx.update(batch_context)

        return current_ctx


class FlameEditorialHost(FlameHost):
    """Editorial workfile host of the Workfiles tool in the main menu.

    The same editorial workfiles as the registered 'FlameHost', with the
    session context only. 'CTX.context' keeps the last menu that ran an
    action, after a Batch menu action it would give the Workfiles tool
    the context of a batch group.
    """
    follow_batch_context = False


class FlameBatchHost(HostBase, IWorkfileHost):
    """Workfile host of the Batch page, saving batch groups as workfiles.

    A Batch workfile is a consolidated JSON document with its own
    '.flamebatch' extension, so it never matches other files or workfile
    hosts of Flame. The host has the name of the registered 'FlameHost':
    the workfile templates and settings of Flame are found by that name.
    It is not registered, the Workfiles tool of the Batch menu is built
    with it.

    Its context comes from the AYON products of the current batch group
    (Batch product first, then Batch Render products), the session
    context is used for a batch group without products. Saving and opening
    a workfile moves the products to the task of the workfile, so the
    context of the batch group is always the one of its workfile.
    """
    name = "flame"

    def __init__(self):
        super().__init__()
        self._save_entities = None
        self._session_context_only = False

    def get_current_context(self):
        current_ctx = super().get_current_context()
        if self._session_context_only:
            return current_ctx

        batch_context = batch_utils.get_batch_products_context()
        if batch_context:
            current_ctx.update(batch_context)
        return current_ctx

    def set_current_context(self, *args, **kwargs):
        # Core skips the change when the current context already matches,
        # compare with the session context so the session always follows
        # the opened or saved workfile.
        self._session_context_only = True
        try:
            return super().set_current_context(*args, **kwargs)
        finally:
            self._session_context_only = False

    def save_workfile_with_context(
        self, filepath, folder_entity, task_entity, *args, **kwargs
    ):
        self._confirm_save_from_batch(folder_entity, task_entity)
        # The AYON products are moved to the context in 'save_workfile',
        # which core calls after the context switch, their notes are part
        # of the saved content.
        self._save_entities = (folder_entity, task_entity)
        try:
            super().save_workfile_with_context(
                filepath, folder_entity, task_entity, *args, **kwargs
            )
        finally:
            self._save_entities = None

    def _confirm_save_from_batch(self, folder_entity, task_entity):
        """Ask before a Save As from a batch group of an older workfile.

        Only a batch group whose products are of the saved task is checked:
        a new version saved from it becomes the last one of the task, with
        older work in it. A save to another task is not checked.

        Raises:
            RuntimeError: The artist canceled the save.
        """
        try:
            batch = batch_utils.get_current_batch()
        except RuntimeError:
            return

        folder_path = folder_entity["path"]
        task_name = task_entity["name"]
        products_context = batch_utils.get_batch_products_context(batch)
        if products_context != {
            "folder_path": folder_path,
            "task_name": task_name,
        }:
            return

        issue = get_batch_workfile_issue(batch, folder_path, task_name)
        if not issue:
            return

        from qtpy import QtWidgets

        answer = QtWidgets.QMessageBox.question(
            QtWidgets.QApplication.activeWindow(),
            "Save from an older batch group?",
            f"{issue}\n\nA new version saved from it becomes the last"
            " workfile of the task. Save it anyway?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            raise RuntimeError(f"Save As canceled: {issue}")

    def get_workfile_extensions(self):
        return [BATCH_WORKFILE_EXTENSION]

    def save_workfile(self, dst_path=None):
        dst_path = dst_path or self.get_current_workfile()
        if not dst_path:
            raise RuntimeError(
                "No Batch workfile was saved or opened for this batch group"
                " yet, use Save As."
            )

        try:
            batch = batch_utils.get_current_batch()
        except RuntimeError as error:
            raise RuntimeError(
                "No active Flame Batch group to save."
            ) from error

        # Without a context (a direct 'save_workfile' call instead of
        # 'save_workfile_with_context') there is no task to move the
        # products to, only the file is written.
        if self._save_entities:
            # A failure fails the save: a workfile without its Batch
            # product, or with products of another task, is not a valid
            # result and nothing is written yet.
            folder_entity, task_entity = self._save_entities
            batch_utils.set_batch_products_context(
                batch, folder_entity["path"], task_entity["name"]
            )
            self._ensure_batch_product(folder_entity, task_entity)

        write_batch_workfile(batch, dst_path)
        # The task of the batch group, not of the session. A save from a
        # Flame project save keeps it when the session is on another task.
        context = self.get_current_context()
        batch_utils.set_session_batch_workfile(
            batch, dst_path, context["folder_path"], context["task_name"]
        )
        log.info("Saved AYON workfile %r", dst_path)

    def open_workfile(self, filepath):
        folder_path = self.get_current_folder_path()
        task_name = self.get_current_task_name()
        if not folder_path or not task_name:
            raise RuntimeError(
                "Batch workfile can be opened only in a task context, "
                f"got folder '{folder_path}' and task '{task_name}'."
            )

        batch_name = batch_utils.get_task_batch_name(folder_path, task_name)
        # Unique like the Batch loader does, so several versions of a
        # workfile can be open together: none replaces another, which is
        # not how workfiles of other DCCs behave.
        unique_batch_name = batch_utils.get_unique_batch_name(batch_name)
        if unique_batch_name != batch_name:
            log.warning(
                "Batch group %r already exists, opening workfile as %r.",
                batch_name,
                unique_batch_name,
            )

        log.debug(
            "Opening AYON workfile %r as batch group %r",
            filepath,
            unique_batch_name,
        )
        new_batch = flame.batch.create_batch_group(unique_batch_name)
        try:
            batch = batch_utils.load_batch_from_consolidated_json(
                filepath, name=unique_batch_name
            )
        except Exception:
            # A file that fails to load leaves no empty batch group.
            flame.delete(new_batch, confirm=False)
            raise
        batch_utils.set_instances_batch_name(batch, unique_batch_name)
        # A workfile saved by another build, or moved between tasks, can
        # carry products of another task.
        batch_utils.set_batch_products_context(batch, folder_path, task_name)
        batch_utils.set_session_batch_workfile(
            batch, filepath, folder_path, task_name
        )
        flame.set_current_tab("Batch")
        log.info(
            "Opened AYON workfile %r as batch group %r",
            filepath,
            unique_batch_name,
        )

    def get_current_workfile(self):
        # Batch groups do not store their workfile path. This Flame session
        # keeps the one saved or opened for each batch group, see
        # 'batch_utils.get_session_batch_workfile'.
        try:
            batch = batch_utils.get_current_batch()
        except RuntimeError:
            return None

        context = self.get_current_context()
        return batch_utils.get_session_batch_workfile(
            batch,
            context["folder_path"],
            context["task_name"],
        )

    def _ensure_batch_product(self, folder_entity, task_entity):
        """Create the Batch product of the current batch group if missing.

        The product is created by its creator, the same way as from the
        Publisher, in the given context. The creator is enabled only for
        Batch menu actions, so the menu context is forced meanwhile.
        """
        if batch_utils.get_batch_product_data():
            return

        log.debug(
            "Creating Batch product for %s / %s",
            folder_entity["path"], task_entity["name"],
        )
        from ayon_core.pipeline.create import CreateContext

        previous_context = CTX.context
        CTX.context = "FlameMenuBatch"
        try:
            create_context = CreateContext(
                registered_host(), discover_publish_plugins=False
            )
            creator = create_context.creators.get(BATCH_CREATOR_IDENTIFIER)
            if creator is None:
                raise RuntimeError(
                    "Batch product creator is not available, the Batch "
                    "workfile cannot be saved without its Batch product."
                )
            create_context.create(
                BATCH_CREATOR_IDENTIFIER,
                creator.default_variant,
                folder_entity=folder_entity,
                task_entity=task_entity,
            )
        finally:
            CTX.context = previous_context



def write_batch_workfile(batch, dst_path):
    """Write a batch group to a Batch workfile.

    The file is written next to the destination and replaces it at the
    end, so a failure never leaves a partial or corrupted workfile.
    """
    log.debug("Writing AYON workfile %r", dst_path)
    dirpath = os.path.dirname(os.path.abspath(dst_path))
    os.makedirs(dirpath, exist_ok=True)

    tmp_path = os.path.join(
        dirpath,
        ".{}.{}.tmp".format(os.path.basename(dst_path), os.getpid())
    )
    try:
        batch_utils.save_batch_as_consolidated_json(batch, tmp_path)
        os.replace(tmp_path, dst_path)
    except Exception as error:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise RuntimeError(
            f"Unable to save Flame Batch workfile '{dst_path}': {error}"
        ) from error


def get_last_batch_workfile(folder_path, task_name):
    """Return the path of the last saved Batch workfile of a task.

    Returns:
        Optional[str]: Path of the highest version available on disk.
    """
    host = FlameBatchHost()
    project_name = host.get_current_project_name()
    folder_entity = ayon_api.get_folder_by_path(project_name, folder_path)
    if not folder_entity:
        return None
    task_entity = ayon_api.get_task_by_name(
        project_name, folder_entity["id"], task_name
    )
    if not task_entity:
        return None

    workfiles = [
        workfile
        for workfile in host.list_workfiles(
            project_name, folder_entity, task_entity
        )
        if workfile.available and workfile.version is not None
    ]
    if not workfiles:
        return None
    return max(workfiles, key=lambda workfile: workfile.version).filepath


def get_batch_workfile_issue(batch, folder_path, task_name):
    """Return why a batch group is not on the last workfile of its task.

    Args:
        batch (flame.PyBatch): Batch group.
        folder_path (str): Folder path of the batch group products.
        task_name (str): Task name of the batch group products.

    Returns:
        Optional[str]: The reason, None when the batch group is on the last
            Batch workfile or the task has none yet.
    """
    last_filepath = get_last_batch_workfile(folder_path, task_name)
    if not last_filepath:
        return None
    last_name = os.path.basename(last_filepath)

    filepath = batch_utils.get_session_batch_workfile(
        batch, folder_path, task_name
    )
    if not filepath:
        return (
            f"{batch.name.get_value()} is not linked to a workfile in this"
            f" Flame session, the last one of the task is {last_name}."
        )

    version = get_version_from_path(os.path.basename(filepath))
    last_version = get_version_from_path(last_name)
    if version and last_version and int(last_version) > int(version):
        return f"{os.path.basename(filepath)} is older than {last_name}."
    return None


def refresh_batch_workfile():
    """Rewrite the Batch workfile of the current batch group.

    Runs after a Flame project save. Nothing is saved when the batch group
    has no Batch workfile in this Flame session. The artist is warned when
    a batch group with AYON products has none, or comes from an older
    version than the last one of its task.
    """
    project_settings = get_current_project_settings()
    if not project_settings["flame"]["update_batch_workfile"]["enabled"]:
        return

    host = FlameBatchHost()
    filepath = host.get_current_workfile()
    if not filepath:
        # A batch group without AYON products is not an AYON workfile.
        if batch_utils.get_batch_products_context():
            batch_name = batch_utils.get_current_batch().name.get_value()
            flame.messages.show_in_console(
                f"AYON: {batch_name} is not linked to a workfile, use Work"
                " Files > Open or Save As.",
                "warning",
                10,
            )
        return

    host.save_workfile(filepath)
    flame.messages.show_in_console(
        f"AYON: saved {os.path.basename(filepath)}", "info", 5
    )

    # Another artist, or another batch group, may have saved a newer
    # version since this one was opened. The file is saved already, a
    # failed lookup must not report a failed save.
    context = host.get_current_context()
    try:
        last_filepath = get_last_batch_workfile(
            context["folder_path"], context["task_name"]
        )
    except Exception:
        log.warning("Unable to find the last Batch workfile.", exc_info=True)
        return
    if not last_filepath:
        return
    version = get_version_from_path(os.path.basename(filepath))
    last_version = get_version_from_path(os.path.basename(last_filepath))
    if version and last_version and int(last_version) > int(version):
        last_name = os.path.basename(last_filepath)
        flame.messages.show_in_console(
            f"AYON: {os.path.basename(filepath)} is older than {last_name}."
            f" Open {last_name} from Work Files.",
            "warning",
            10,
        )


def install():
    pyblish.register_host("flame")
    pyblish.register_plugin_path(PUBLISH_PATH)
    register_loader_plugin_path(LOAD_PATH)
    register_creator_plugin_path(CREATE_PATH)
    log.info("AYON Flame plug-ins registered.")
    log.info("AYON Flame host installed.")


def uninstall():
    pyblish.deregister_host("flame")

    log.info("Deregistering Flame plug-ins.")
    pyblish.deregister_plugin_path(PUBLISH_PATH)
    deregister_loader_plugin_path(LOAD_PATH)
    deregister_creator_plugin_path(CREATE_PATH)

    log.info("AYON Flame host uninstalled.")


def containerise(flame_clip_segment,
                 name,
                 namespace,
                 context,
                 loader=None,
                 data=None):
    """ Containerise a flame clip segment.
    """
    data_imprint = {
        "schema": "ayon:container-3.0",
        "id": AYON_CONTAINER_ID,
        "name": str(name),
        "namespace": str(namespace),
        "loader": str(loader),
        "representation": context["representation"]["id"],
    }

    if data:
        data_imprint.update(data)

    # timeline item imprinted data
    set_segment_data_marker(flame_clip_segment, data_imprint)

    return True


def ls():
    """List available containers.
    """
    return []  # TODO implement this from metadata


def parse_container(tl_segment, validate=True):
    """Return container data from timeline_item's AYON tag.
    """
    log.debug("TODO: parse_container")


def update_container(tl_segment, data=None):
    """Update container data to input timeline_item's AYON tag.
    """
    log.debug("TODO: update_container")


def remove_instance(instance):
    """Remove instance marker from track item."""
    log.debug("TODO: remove_instance")


def list_instances():
    """List all created instances from current workfile."""
    log.debug("TODO: list_instances")


def imprint(item, data=None):
    """
    Adding AYON data to Flame timeline segment.

    Also including publish attribute into tag.

    Arguments:
        item (flame.PySegment | flame.PyClip): flame api object
        data (dict): Any data which needs to be imprinted

    Examples:
        data = {
            'asset': 'sq020sh0280',
            'productType': 'render',
            'productName': 'productMain'
        }
    """
    data = data or {}

    if isinstance(item, flame.PySegment):
        set_segment_data_marker(item, data)
    elif isinstance(item, flame.PyClip):
        set_clip_data_marker(item, data)
    else:
        raise TypeError("Unsupported item type: {}".format(type(item)))


@contextlib.contextmanager
def maintained_selection():
    from .lib import CTX
    sequence = get_current_sequence(CTX.selection)
    with maintained_segment_selection(sequence):
        yield
