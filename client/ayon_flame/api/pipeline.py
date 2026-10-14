"""
Basic AYON integration
"""
import contextlib
import os
from copy import deepcopy
import ayon_api
import flame

from ayon_core.host import HostBase, ILoadHost, IPublishHost, IWorkfileHost
from ayon_core.lib import Logger
from ayon_core.pipeline import (
    AYON_CONTAINER_ID,
    deregister_creator_plugin_path,
    deregister_loader_plugin_path,
    register_creator_plugin_path,
    register_loader_plugin_path,
    registered_host,
)
from pyblish import api as pyblish

from ayon_flame import FLAME_ADDON_ROOT

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

# Creator of the Batch product, stored in the batch metadata note.
BATCH_PRODUCT_CREATOR = "io.ayon.creators.flame.batch.workfile"


log = Logger.get_logger(__name__)


class FlameHost(HostBase, IWorkfileHost, ILoadHost, IPublishHost):
    """Registered host, its workfiles are the editorial workfiles.

    Batch groups have their own workfile host, 'FlameBatchHost'.
    """
    name = "flame"

    def __init__(self):
        super().__init__()
        self._publish_context_data = {}

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
        return [editorial_workfile.EDITORIAL_WORKFILE_EXTENSION]

    def save_workfile(self, dst_path=None):
        if not dst_path:
            dst_path = self.get_current_workfile()
        if not dst_path:
            raise RuntimeError(
                "No editorial workfile was saved or opened yet, use Save As."
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

    def get_current_context(self):
        current_ctx = super().get_current_context()

        # Flame can be used as a multi-workfile host.
        # When working with batch, we try to get the
        # current context from the batch products.
        if CTX.context == "FlameMenuBatch":
            batch_context = batch_utils.get_batch_products_context()
            if batch_context:
                current_ctx.update(batch_context)

        return current_ctx


class FlameBatchHost(HostBase, IWorkfileHost):
    """Workfile host of the Batch page, saving batch groups as .json.

    Its context comes from the AYON products of the current batch group
    (Batch product first, then Batch Render products), the session
    context is used for a batch group without products.
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
        # The Batch product is created in 'save_workfile', which core calls
        # after the context switch, its note is part of the saved content.
        self._save_entities = (folder_entity, task_entity)
        try:
            super().save_workfile_with_context(
                filepath, folder_entity, task_entity, *args, **kwargs
            )
        finally:
            self._save_entities = None

    def get_workfile_extensions(self):
        return [".json"]

    def save_workfile(self, dst_path=None):
        if not dst_path:
            raise RuntimeError(
                "Batch groups do not keep their workfile path, use Save As."
            )

        try:
            batch = batch_utils.get_current_batch()
        except RuntimeError as error:
            raise RuntimeError(
                "No active Flame Batch group to save."
            ) from error

        if self._save_entities:
            try:
                ensure_batch_product(*self._save_entities)
            except Exception:
                # Never lose the artist's save because of the product.
                log.warning("Batch product was not created.", exc_info=True)

        log.info("Writing AYON workfile %r", dst_path)
        dirpath = os.path.dirname(os.path.abspath(dst_path))
        os.makedirs(dirpath, exist_ok=True)

        # Write next to the destination and replace it at the end, so
        # a failure never leaves a partial or corrupted workfile behind.
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

    def open_workfile(self, filepath):
        batch_name = batch_utils.get_task_batch_name(
            self.get_current_folder_path(), self.get_current_task_name()
        )
        unique_batch_name = batch_utils.get_unique_batch_name(batch_name)
        if unique_batch_name != batch_name:
            log.warning(
                "Batch group %r already exists, opening workfile as %r.",
                batch_name,
                unique_batch_name,
            )

        log.info(
            "Opening AYON workfile %r as batch group %r",
            filepath,
            unique_batch_name,
        )
        flame.batch.create_batch_group(unique_batch_name)
        batch = batch_utils.load_batch_from_consolidated_json(
            filepath, name=unique_batch_name
        )
        batch_utils.set_instances_batch_name(batch, unique_batch_name)

    def get_current_workfile(self):
        # Batch groups do not store a workfile path, saved workfiles are
        # found per context with 'get_last_batch_workfile'.
        return None


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


def ensure_batch_product(folder_entity, task_entity):
    """Create the Batch product of the current batch group if missing.

    The product is created by its creator, the same way as from the
    Publisher, in the given context. The creator is enabled only for
    Batch menu actions, so the menu context is forced meanwhile.
    """
    if batch_utils.get_batch_product_data():
        return

    log.info(
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
        creator = create_context.creators.get(BATCH_PRODUCT_CREATOR)
        if creator is None:
            log.warning("Batch creator is not available, no product made.")
            return
        create_context.create(
            BATCH_PRODUCT_CREATOR,
            creator.default_variant,
            folder_entity=folder_entity,
            task_entity=task_entity,
        )
    finally:
        CTX.context = previous_context


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
