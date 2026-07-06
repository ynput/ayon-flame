""" Publish current content without opening the UI.
"""
from qtpy import QtWidgets

from ayon_core.tools.utils.host_tools import (
    get_tool_by_name,
    show_publisher,
)

import ayon_flame.api as ayfapi


_MAIN_WINDOW = None


def _get_main_window():
    global _MAIN_WINDOW
    if _MAIN_WINDOW is None:
        _MAIN_WINDOW = next(
            (
                obj
                for obj in QtWidgets.QApplication.topLevelWidgets()
                if isinstance(obj, QtWidgets.QMainWindow)
            ),
            None
        )
    return _MAIN_WINDOW


def publish_current_batch_content():
    """ Publish the current batch content.
    """
    ayfapi.CTX.context = "FlameMenuBatch"

    show_publisher(
        tab="publish",
        parent=_get_main_window()
    )
    window = get_tool_by_name("publisher")
    window.set_current_tab("publish")
    controller = window.controller

    def on_ready_to_publish(_=None):
        # Limit callback execution to this first call only.
        if getattr(on_ready_to_publish, "done", False):
            return  # already executed
        on_ready_to_publish.done = True

        controller.save_changes()
        if not controller.publish_is_running():
            controller.publish()

    if window.isVisible() and not window._reset_on_show:
        on_ready_to_publish()
    else:
        controller.register_event_callback(
            "controller.reset.finished",
            on_ready_to_publish
        )

    window.hide()
