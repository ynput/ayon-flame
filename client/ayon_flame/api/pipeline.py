"""
Basic AYON integration
"""
import contextlib
import os
from copy import deepcopy
import flame

from ayon_core.host import (
    HostBase,
    ILoadHost,
    IPublishHost,
    IWorkfileHost,
)
from ayon_core.lib import Logger
from ayon_core.pipeline import (
    AYON_CONTAINER_ID,
    deregister_creator_plugin_path,
    deregister_loader_plugin_path,
    register_creator_plugin_path,
    register_loader_plugin_path,
)
from pyblish import api as pyblish

from ayon_flame import FLAME_ADDON_ROOT

from .workfile import get_flame_workfile_host
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

# AYON Core publish plugins that react to a host being an 'IWorkfileHost'
# and must stay inactive for Flame (class name -> defining file stem):
# - 'ValidateCurrentSaveFile' would block publishing from tabs that cannot
#   be saved as a workfile; the Flame Batch validator replaces it.
# - 'CollectSceneVersion' would parse the version from the workfile name and
#   compete with 'CollectBatchVersion' over 'context.data["version"]'.
_INACTIVE_CORE_PLUGINS = {
    "ValidateCurrentSaveFile": "validate_file_saved",
    "CollectSceneVersion": "collect_scene_version",
}


log = Logger.get_logger(__name__)


class FlameHost(HostBase, ILoadHost, IPublishHost, IWorkfileHost):
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

    # IWorkfileHost: the implementation depends on the active Flame tab,
    # so it is resolved on every call.
    def save_workfile(self, dst_path=None):
        get_flame_workfile_host().save_workfile(dst_path)

    def open_workfile(self, filepath):
        get_flame_workfile_host().open_workfile(filepath)

    def get_current_workfile(self):
        return get_flame_workfile_host().get_current_workfile()

    def workfile_has_unsaved_changes(self):
        return get_flame_workfile_host().workfile_has_unsaved_changes()

    def get_workfile_extensions(self):
        return get_flame_workfile_host().get_workfile_extensions()

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

def _is_inactive_core_plugin(plugin):
    """Return whether the plugin is one of 'AYON Core' plugins to disable."""
    stem = _INACTIVE_CORE_PLUGINS.get(plugin.__name__)
    if stem is None:
        return False

    source = getattr(plugin, "__file__", None) or plugin.__module__
    name = source.replace("\\", "/").split("/")[-1]
    if name.endswith(".py"):
        name = name[:-3]
    else:
        name = name.rsplit(".", 1)[-1]
    return name == stem


def _filter_core_workfile_plugins(plugins):
    """Pyblish discovery filter, drops plugins in place."""
    plugins[:] = [
        plugin for plugin in plugins
        if not _is_inactive_core_plugin(plugin)
    ]


def install():
    pyblish.register_host("flame")
    pyblish.register_plugin_path(PUBLISH_PATH)
    if _filter_core_workfile_plugins not in (
        pyblish.registered_discovery_filters()
    ):
        pyblish.register_discovery_filter(_filter_core_workfile_plugins)
    register_loader_plugin_path(LOAD_PATH)
    register_creator_plugin_path(CREATE_PATH)
    log.info("AYON Flame plug-ins registered.")
    log.info("AYON Flame host installed.")


def uninstall():
    pyblish.deregister_host("flame")

    log.info("Deregistering Flame plug-ins.")
    pyblish.deregister_plugin_path(PUBLISH_PATH)
    if _filter_core_workfile_plugins in pyblish.registered_discovery_filters():
        pyblish.deregister_discovery_filter(_filter_core_workfile_plugins)
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
