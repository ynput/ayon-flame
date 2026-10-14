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
    """Validate the published Batch groups were saved as workfiles.

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

        batches = flapi.get_instances_batches(context)
        if not batches:
            self.log.debug("No active Batch instance, skipping.")
            return

        unsaved = self.get_unsaved_batch_names(batches)
        if not unsaved:
            return

        names = ", ".join(f"'{name}'" for name in unsaved)
        raise PublishValidationError(
            f"Batch group {names} has no saved workfile.",
            title="Batch has no saved workfile",
            description=self.get_description(),
        )

    @classmethod
    def get_unsaved_batch_names(cls, batches):
        unsaved = []
        for batch_name, batch in batches.items():
            workfile_path = flapi.get_workfile_path(batch)
            if workfile_path and os.path.exists(workfile_path):
                cls.log.debug(
                    f"Batch '{batch_name}' workfile found: {workfile_path}"
                )
            else:
                unsaved.append(batch_name)
        return unsaved

    @classmethod
    def repair(cls, context):
        batches = flapi.get_instances_batches(context)
        for batch_name in cls.get_unsaved_batch_names(batches):
            # The Batch workfile host saves the current batch group.
            if flapi.get_current_batch().name.get_value() != batch_name:
                batches[batch_name].open()
            flapi.save_next_batch_workfile_version()

    def get_description(self):
        return inspect.cleandoc("""
            ### Batch has no saved workfile

            The published Batch group was not saved as an AYON workfile,
            or its workfile no longer exists on disk.

            Save it from **AYON > 4 - Work Files...** in the Batch menu
            or click **Repair** to save the next workfile version now.
        """)
