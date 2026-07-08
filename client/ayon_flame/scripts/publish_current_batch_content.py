""" Publish current content without opening the UI.
"""
from qtpy import QtWidgets

from ayon_core.tools.publisher.control import PublisherController


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

    controller = PublisherController()
    controller.reset()
    controller.publish()
