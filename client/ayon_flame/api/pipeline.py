"""
Basic AYON integration
"""
import contextlib
import os
from copy import deepcopy
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
)
from pyblish import api as pyblish

from ayon_flame import FLAME_ADDON_ROOT

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
        if CTX.context == "FlameMenuBatch":
            import ayon_flame.api as flapi
            metadata_node = flapi.get_metadata_node()
            if metadata_node:
                data = flapi.read_node_metadata(metadata_node)
                try:
                    return {
                        "project_name": current_ctx["project_name"],
                        "folder_path": data["folderPath"],
                        "task_name": data["task"]
                    }
                except (KeyError, TypeError) as error:
                    log.warning(
                        "Could not read context from batch metadata: %r",
                        error
                    )

        return current_ctx

    # The Flame "workfile" is the current batch group (json file)
    def get_workfile_extensions(self):
        return [".json"]

    def save_workfile(self, dst_path=None):
        import ayon_flame.api as flapi

        dst_path = dst_path or self.get_current_workfile()
        if not dst_path:
            raise RuntimeError(
                "No destination path provided to save workfile."
            )

        batch = flapi.get_current_batch()
        # stamp the path before serializing so the saved file records it
        flapi.stamp_workfile_path(dst_path, batch)
        flapi.save_batch_as_consolidated_json(batch, dst_path)
        return dst_path

    def open_workfile(self, filepath):
        import ayon_flame.api as flapi

        batch_name = self._get_task_batch_name()
        if not batch_name:
            batch_name = os.path.splitext(os.path.basename(filepath))[0]

        existing_batch = flapi.get_batch_from_workspace(batch_name)
        if existing_batch is None:
            flame.batch.create_batch_group(batch_name)
        else:
            existing_batch.open()

        batch = flapi.load_batch_from_consolidated_json(
            filepath, name=batch_name
        )
        flapi.stamp_workfile_path(filepath, batch)
        return filepath

    def get_current_workfile(self):
        import ayon_flame.api as flapi

        return flapi.get_workfile_path(self._get_task_batch())

    def _get_task_batch_name(self):
        import ayon_flame.api as flapi

        context = get_global_context()
        folder_path = context.get("folder_path")
        task_name = context.get("task_name")

        if folder_path and task_name:
            return flapi.get_task_batch_name(folder_path, task_name)
        return None

    def _get_task_batch(self):
        import ayon_flame.api as flapi

        batch_name = self._get_task_batch_name()
        if not batch_name:
            return None
        return flapi.get_batch_from_workspace(batch_name)


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
