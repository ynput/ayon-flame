import inspect
import os

import pyblish.api
from ayon_core.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError,
    RepairContextAction,
)

import ayon_flame.api as flapi


class OpenBatchWorkfilesAction(pyblish.api.Action):
    """Open the Workfiles tool of the Batch menu."""

    label = "Open Batch Work Files..."
    on = "failed"
    icon = "files-o"

    def process(self, context, plugin):
        flapi.show_batch_workfiles()


class ValidateBatchWorkfileSaved(
    OptionalPyblishPluginMixin,
    pyblish.api.ContextPlugin
):
    """Validate the current Batch group was saved as a workfile.

    Runs only if publishing instances created from the Batch menu.
    """

    label = "Validate Batch Workfile Saved"
    order = pyblish.api.ValidatorOrder - 0.2
    hosts = ["flame"]
    settings_category = "flame"

    optional = True
    active = True

    actions = [RepairContextAction, OpenBatchWorkfilesAction]

    def process(self, context):
        if not self.is_active(context.data):
            self.log.info("Validation is disabled.")
            return

        if not any(
            instance.data.get("flame_context") == "FlameMenuBatch"
            and instance.data.get("publish", True)
            and instance.data.get("active", True)
            for instance in context
        ):
            self.log.debug("No active Batch instance, skipping.")
            return

        batch = flapi.get_current_batch()
        workfile_path = flapi.get_workfile_path(batch)
        if workfile_path and os.path.exists(workfile_path):
            self.log.debug(f"Batch workfile found: {workfile_path}")
            return

        self.log.info(f"Stored Batch workfile path: {workfile_path}")
        batch_name = batch.name.get_value()
        raise PublishValidationError(
            f"Batch group '{batch_name}' has no saved workfile.",
            title="Batch has no saved workfile",
            description=self.get_description(),
        )

    @classmethod
    def repair(cls, context):
        flapi.save_next_batch_workfile_version()

    def get_description(self):
        return inspect.cleandoc("""
            ### Batch has no saved workfile

            The current Batch group was not saved as an AYON workfile, or
            its workfile no longer exists on disk.

            Save it from **Batch menu > AYON > Work Files...** or click
            **Repair** to save the next workfile version now.
        """)
