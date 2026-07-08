""" Publish current content without opening the UI.
"""
from ayon_core.tools.publisher.control import PublisherController

import ayon_flame.api as ayfapi


def publish_current_batch_content():
    """ Publish the current batch content.
    """
    ayfapi.CTX.context = "FlameMenuBatch"

    controller = PublisherController()
    controller.reset()
    controller.publish()
