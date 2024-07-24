"""
Basic AYON integration
"""
import os
import contextlib
from copy import deepcopy
from pyblish import api as pyblish

from ayon_core.host import HostBase, IWorkfileHost, ILoadHost, IPublishHost

from ayon_core.lib import Logger
from ayon_core.pipeline import (
    register_loader_plugin_path,
    register_creator_plugin_path,
    deregister_loader_plugin_path,
    deregister_creator_plugin_path,
    AYON_CONTAINER_ID,
)
from ayon_flame import FLAME_ADDON_ROOT
from .lib import (
    set_segment_data_marker,
    set_publish_attribute,
    maintained_segment_selection,
    get_current_sequence,
    reset_segment_selection
)
from .workio import (
    open_file,
    save_file,
    file_extensions,
    has_unsaved_changes,
    work_root,
    current_file,
)


PLUGINS_DIR = os.path.join(FLAME_ADDON_ROOT, "plugins")
PUBLISH_PATH = os.path.join(PLUGINS_DIR, "publish")
LOAD_PATH = os.path.join(PLUGINS_DIR, "load")
CREATE_PATH = os.path.join(PLUGINS_DIR, "create")


log = Logger.get_logger(__name__)


class FlameHost(HostBase, IWorkfileHost, ILoadHost, IPublishHost):
    name = "flame"

    # object variables
    _context = {}

    def open_workfile(self, filepath):
        return open_file(filepath)

    def save_workfile(self, filepath=None):
        return save_file(filepath)

    def work_root(self, session):
        return work_root(session)

    def get_current_workfile(self):
        return current_file()

    def workfile_has_unsaved_changes(self):
        return has_unsaved_changes()

    def get_workfile_extensions(self):
        return file_extensions()

    def get_containers(self):
        return ls()

    def install(self):
        """Installing all requirements for Nuke host"""
        install()

    def get_context_data(self):
        # TODO: find a way to implement this
        return deepcopy(self._context)

    def update_context_data(self, data, changes):
        # TODO: find a way to implement this
        self._context = deepcopy(data)


def install():
    pyblish.register_host("flame")
    pyblish.register_plugin_path(PUBLISH_PATH)
    register_loader_plugin_path(LOAD_PATH)
    register_creator_plugin_path(CREATE_PATH)
    log.info("AYON Flame plug-ins registered ...")

    # register callback for switching publishable
    pyblish.register_callback("instanceToggled", on_pyblish_instance_toggled)

    log.info("AYON Flame host installed ...")


def uninstall():
    pyblish.deregister_host("flame")

    log.info("Deregistering Flame plug-ins..")
    pyblish.deregister_plugin_path(PUBLISH_PATH)
    deregister_loader_plugin_path(LOAD_PATH)
    deregister_creator_plugin_path(CREATE_PATH)

    # register callback for switching publishable
    pyblish.deregister_callback("instanceToggled", on_pyblish_instance_toggled)

    log.info("AYON Flame host uninstalled ...")


def containerise(flame_clip_segment,
                 name,
                 namespace,
                 context,
                 loader=None,
                 data=None):

    data_imprint = {
        "schema": "ayon:container-3.0",
        "id": AYON_CONTAINER_ID,
        "name": str(name),
        "namespace": str(namespace),
        "loader": str(loader),
        "representation": context["representation"]["id"],
    }

    if data:
        for k, v in data.items():
            data_imprint[k] = v

    # TODO: implement also openClip loaded data
    # timeline item imprinted data
    set_segment_data_marker(flame_clip_segment, data_imprint)

    return True


def ls():
    """List available containers.
    """
    return []


def parse_container(tl_segment, validate=True):
    """Return container data from timeline_item's AYON tag.
    """
    # TODO: parse_container
    pass


def update_container(tl_segment, data=None):
    """Update container data to input timeline_item's AYON tag.
    """
    # TODO: update_container
    pass


def on_pyblish_instance_toggled(instance, old_value, new_value):
    """Toggle node passthrough states on instance toggles."""

    log.info("instance toggle: {}, old_value: {}, new_value:{} ".format(
        instance, old_value, new_value))

    # # Whether instances should be passthrough based on new value
    # timeline_item = instance.data["item"]
    # set_publish_attribute(timeline_item, new_value)


def remove_instance(instance):
    """Remove instance marker from track item."""
    # TODO: remove_instance
    pass


def list_instances():
    """List all created instances from current workfile."""
    # TODO: list_instances
    pass


def imprint(segment, data=None):
    """
    Adding AYON data to Flame timeline segment.

    Also including publish attribute into tag.

    Arguments:
        segment (flame.PySegment)): flame api object
        data (dict): Any data which needst to be imprinted

    Examples:
        data = {
            'asset': 'sq020sh0280',
            'productType': 'render',
            'productName': 'productMain'
        }
    """
    data = data or {}

    set_segment_data_marker(segment, data)

    # add publish attribute
    set_publish_attribute(segment, True)


@contextlib.contextmanager
def maintained_selection():
    import flame
    from .lib import CTX

    # check if segment is selected
    if isinstance(CTX.selection[0], flame.PySegment):
        sequence = get_current_sequence(CTX.selection)

        try:
            with maintained_segment_selection(sequence) as selected:
                yield
        finally:
            # reset all selected clips
            reset_segment_selection(sequence)
            # select only original selection of segments
            for segment in selected:
                segment.selected = True
