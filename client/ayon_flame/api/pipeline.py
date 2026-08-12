"""
Basic AYON integration
"""
import contextlib
import os
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import NoReturn
import flame

from ayon_core.host import HostBase, ILoadHost, IPublishHost, IWorkfileHost
from ayon_core.lib import Logger
from ayon_core.pipeline import (
    AYON_CONTAINER_ID,
    deregister_creator_plugin_path,
    deregister_loader_plugin_path,
    get_global_context,
    register_creator_plugin_path,
    register_loader_plugin_path,
    registered_host,
)
from ayon_core.pipeline.workfile import save_next_version
from ayon_core.tools.utils import show_message_dialog
from pyblish import api as pyblish
from qtpy import QtWidgets

from ayon_flame import FLAME_ADDON_ROOT

from . import batch_utils
from .lib import (
    get_current_sequence,
    maintained_segment_selection,
    set_clip_data_marker,
    set_segment_data_marker,
)

PLUGINS_DIR = os.path.join(FLAME_ADDON_ROOT, "plugins")
PUBLISH_PATH = os.path.join(PLUGINS_DIR, "publish")
LOAD_PATH = os.path.join(PLUGINS_DIR, "load")
CREATE_PATH = os.path.join(PLUGINS_DIR, "create")


log = Logger.get_logger(__name__)


def _show_artist_dialog(message, title):
    """Show a blocking message to the artist"""
    try:
        # Flame's own dialog renders behind AYON's Qt windows
        parent = QtWidgets.QApplication.activeWindow()
        if parent is None:
            flame.messages.show_in_dialog(title, message, "warning", ["OK"])
        else:
            show_message_dialog(title, message, level="warning", parent=parent)
    except Exception as error:
        log.debug("Could not show dialog: %r", error)


def show_artist_message(message, level="info", seconds=10):
    """Show a message in Flame's message bar."""
    try:
        flame.messages.show_in_console(f"AYON: {message}", level, seconds)
    except Exception as error:
        log.debug("Could not show console message: %r", error)


def _refuse_workfile_action(message, title) -> NoReturn:
    """Tell the artist why a workfile action was refused"""
    log.error(message)
    _show_artist_dialog(message, title)
    raise RuntimeError(message)


@dataclass
class WorkfileSkip:
    """Why a save did not sync."""
    message: str
    # a state the artist has to fix, not an expected one
    is_error: bool


def _duplicate_batch_message(count, batch_name, advice):
    """Explain that a task's workfile batch group cannot be identified."""
    return (
        f"{count} batch groups are named '{batch_name}'. Delete the "
        f"duplicates so this task has a single workfile batch group. {advice}"
    )


class FlameHost(HostBase, IWorkfileHost, ILoadHost, IPublishHost):
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

    def get_current_context(self):
        current_ctx = super().get_current_context()

        # Flame can be used as a multi-workfile host.
        # When working with batch, we try to get the
        # current context from the batch metadata.
        if batch_utils.is_batch_page():
            try:
                metadata_node = batch_utils.get_metadata_node()
                if metadata_node:
                    data = batch_utils.read_node_metadata(metadata_node)
                    return {
                        "project_name": current_ctx["project_name"],
                        "folder_path": data["folderPath"],
                        "task_name": data["task"]
                    }
            except (KeyError, TypeError, RuntimeError) as error:
                log.warning(
                    "Could not read context from batch metadata: %r",
                    error
                )

        return current_ctx

    # The Flame "workfile" is the current batch group (json file)
    def get_workfile_extensions(self):
        return [".json"]

    def save_workfile(self, dst_path=None):
        # the interface allows no path: keep the one the batch group
        # already points at
        if not dst_path:
            dst_path = self.get_current_workfile()
        if not dst_path:
            raise RuntimeError("No workfile path to save the batch group to.")

        # the workfile is the task batch group, not the active one
        batch = self._acquire_workfile_batch()

        log.info("Writing AYON workfile %r", dst_path)

        # stamp the path before serializing so the file records it
        batch_utils.stamp_workfile_path(dst_path, batch)
        batch_utils.save_batch_as_consolidated_json(batch, dst_path)

        _SyncState.last_skip = None

        show_artist_message(f"saved {os.path.basename(dst_path)}")
        return dst_path

    def open_workfile(self, filepath):
        batch_name = self._get_task_batch_name()
        if not batch_name:
            batch_name = os.path.splitext(os.path.basename(filepath))[0]

        log.info("Opening AYON workfile %r into %r", filepath, batch_name)

        # by name, so a duplicate is refused before anything is loaded
        batches = batch_utils.get_batches_from_workspace(batch_name)
        self._refuse_if_batch_duplicated(
            batches, batch_name, "Then open the workfile again."
        )

        batch = batches[0] if batches else None
        if batch is None:
            batch = flame.batch.create_batch_group(batch_name)

        batch_utils.set_current_batch(batch)
        batch_utils.show_batch_page()

        batch = batch_utils.load_batch_from_consolidated_json(
            filepath, name=batch_name, batch=batch
        )
        batch_utils.stamp_workfile_path(filepath, batch)
        return filepath

    def get_current_workfile(self):
        batches = self._get_task_batches()
        if not batches:
            return None
        return batch_utils.get_workfile_path(batches[0])

    def _get_task_batch_name(self):
        context = get_global_context()
        folder_path = context.get("folder_path")
        task_name = context.get("task_name")

        if folder_path and task_name:
            return batch_utils.get_task_batch_name(folder_path, task_name)
        return None

    def _get_task_batches(self):
        batch_name = self._get_task_batch_name()
        if not batch_name:
            return []
        return batch_utils.get_batches_from_workspace(batch_name)

    @staticmethod
    def _refuse_if_batch_duplicated(batches, batch_name, advice):
        if len(batches) > 1:
            _refuse_workfile_action(
                _duplicate_batch_message(len(batches), batch_name, advice),
                "AYON: Ambiguous Workfile Batch Group",
            )

    def _workfile_sync_skip_reason(self):
        batch_name = self._get_task_batch_name()
        if not batch_name:
            return WorkfileSkip(
                "No folder/task in the current context "
                "(AYON_FOLDER_PATH / AYON_TASK_NAME are not both set).",
                is_error=False,
            )

        task_batches = self._get_task_batches()
        if len(task_batches) > 1:
            return WorkfileSkip(
                _duplicate_batch_message(
                    len(task_batches), batch_name, "Nothing has been saved."
                ),
                is_error=True,
            )

        if not task_batches:
            return WorkfileSkip(
                f"No batch group named '{batch_name}' on the desktop yet. "
                "Save once through the Workfiles tool to create it; "
                "after that, Flame's own save gestures keep it in sync.",
                is_error=False,
            )

        try:
            current = batch_utils.get_current_batch()
        except RuntimeError as error:
            return WorkfileSkip(
                f"No active batch group ({error}).", is_error=False
            )

        current_name = batch_utils.normalized_batch_name(
            current.name.get_value()
        )
        if current_name != batch_name:
            return WorkfileSkip(
                f"Active batch group '{current_name}' is not the workfile "
                f"batch group '{batch_name}'.",
                is_error=False,
            )

        context = self.get_current_context()
        global_context = get_global_context()
        if (
            context.get("folder_path") != global_context.get("folder_path")
            or context.get("task_name") != global_context.get("task_name")
        ):
            return WorkfileSkip(
                "This batch group holds AYON instance data for "
                f"'{context.get('folder_path')} / {context.get('task_name')}' "
                "but the session is on "
                f"'{global_context.get('folder_path')} / "
                f"{global_context.get('task_name')}'. Relaunch on "
                f"'{context.get('folder_path')} / {context.get('task_name')}' "
                "to work on this batch group, or switch to a batch group "
                "belonging to the current task.",
                is_error=True,
            )

        return None

    def _acquire_workfile_batch(self):
        """Return the batch group to serialize as the AYON workfile."""
        batch_name = self._get_task_batch_name()
        current = batch_utils.get_current_batch()

        if not batch_name:
            # no folder/task context, nothing to enforce against
            return current

        # refuse before writing anything
        task_batches = self._get_task_batches()
        self._refuse_if_batch_duplicated(
            task_batches, batch_name, "Then save again."
        )

        current_name = batch_utils.normalized_batch_name(
            current.name.get_value()
        )
        if current_name == batch_name:
            return current

        if not task_batches:
            log.info(
                "Adopting batch group %r as the workfile batch %r",
                current_name,
                batch_name,
            )
            batch_utils.rename_batch(current, batch_name)
            return current

        _refuse_workfile_action(
            f"Active batch group '{current_name}' is not the AYON workfile "
            f"batch group '{batch_name}'. Switch to '{batch_name}' before "
            "saving, or publish the active batch instead.",
            "AYON: Wrong Batch Group",
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


# how long a version bump stays recognisable to the refresh that trails it
_SYNC_DEDUP_WINDOW = 5.0


class _SyncState:
    last_skip = None
    last_bump = None


def _report_skip(skip):
    """Log a skip, and tell the artist once per state."""
    log.info("Skipping AYON workfile sync. %s", skip.message)

    if skip.message == _SyncState.last_skip:
        return
    _SyncState.last_skip = skip.message

    if skip.is_error:
        _show_artist_dialog(skip.message, "AYON: Workfile Not Saved")
    else:
        show_artist_message(skip.message, "warning")


def _host_for_sync():
    """The host to sync through, or None if this gesture must not sync."""
    host = registered_host()
    if not isinstance(host, FlameHost):
        return None

    skip = host._workfile_sync_skip_reason()
    if skip:
        _report_skip(skip)
        return None

    return host


def _is_trailing_bump_rewrite(filepath):
    """Whether a version bump just wrote this exact file."""
    if _SyncState.last_bump is None:
        return False

    last_path, last_time = _SyncState.last_bump
    _SyncState.last_bump = None

    elapsed = time.monotonic() - last_time
    if last_path != filepath or elapsed >= _SYNC_DEDUP_WINDOW:
        return False

    log.info(
        "Version bump wrote %r %.2fs ago; skipping the refresh behind it.",
        filepath,
        elapsed,
    )
    return True


def bump_workfile_version():
    """Save the batch group as a new AYON workfile version.

    Core picks the number: Flame's iteration index is a pointer that can
    be re-used and re-indexed, so it cannot drive versions.

    Called from a Flame hook, so it reports failures instead of raising.
    """
    try:
        host = _host_for_sync()
        if host is None:
            return

        save_next_version(
            version=None,
            comment="",
            description="Saved from a Flame batch iteration",
        )
        filepath = host.get_current_workfile()
        # stamped after the save, so a failed save leaves the refresh
        # behind it free to write
        _SyncState.last_bump = (filepath, time.monotonic())
        log.info("Saved AYON workfile %r", filepath)
    except Exception:
        log.warning(
            "Could not save a new AYON workfile version.", exc_info=True
        )


def refresh_workfile():
    """Rewrite the AYON workfile the batch group already points at."""
    try:
        host = _host_for_sync()
        if host is None:
            return

        filepath = host.get_current_workfile()
        if not filepath:
            _report_skip(WorkfileSkip(
                "This batch group has no AYON workfile yet. Save once "
                "through the Work Files tool to create one; after that, "
                "Flame's own save gestures keep it up to date.",
                is_error=False,
            ))
            return

        if _is_trailing_bump_rewrite(filepath):
            return

        host.save_workfile(filepath)
        log.info("Refreshed AYON workfile %r", filepath)
    except Exception:
        log.warning("Could not refresh the AYON workfile.", exc_info=True)


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
