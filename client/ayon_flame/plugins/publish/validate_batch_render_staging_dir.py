import os

import pyblish.api
from ayon_core.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError,
    RepairAction,
)

import ayon_flame.api as flapi


class ValidateBatchRenderStagingDir(
    OptionalPyblishPluginMixin,
    pyblish.api.InstancePlugin
):
    """Validate Write File node renders into the custom staging dir."""

    label = "Validate Batch Render Custom Staging Dir"
    order = pyblish.api.ValidatorOrder
    families = ["render"]
    hosts = ["flame"]
    settings_category = "flame"

    optional = True
    actions = [RepairAction]

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        if not instance.data.get("stagingDir_is_custom"):
            self.log.debug(
                "Current batch render instance does not "
                "use custom staging directory."
            )
            return

        write_node = instance.data["transientData"].get("writeNode")
        if write_node is None:
            raise ValueError("Could not find write node from instance.")

        # Ensure current stagingDir match write_node output path.
        expected = os.path.normpath(instance.data["stagingDir"])
        current = os.path.normpath(
            os.path.dirname(write_node.get_resolved_media_path())
        )
        if current != expected:
            raise PublishValidationError(
                f"Write File node '{write_node.name.get_value()}' renders "
                f"to '{current}' instead of '{expected}'.",
                title="Wrong Write File output path",
            )

    @classmethod
    def repair(cls, instance):
        write_node = instance.data["transientData"]["writeNode"]
        flapi.set_write_node_output_dir(
            write_node, instance.data["stagingDir"]
        )
