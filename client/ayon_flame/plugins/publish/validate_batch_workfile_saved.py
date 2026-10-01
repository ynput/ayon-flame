import inspect

import pyblish.api

import ayon_flame.api as flapi
from ayon_core.pipeline.publish import (
    PublishValidationError,
    RepairContextAction,
)


class ValidateBatchWorkfileSaved(pyblish.api.ContextPlugin):
    """Publishing a Batch requires a saved AYON workfile.

    Passes when AYON already has a workfile for the current task. Repair
    saves the Batch as the next available workfile version, the version
    and path being allocated by AYON Core.
    """

    order = pyblish.api.ValidatorOrder - 0.2
    label = "Validate Batch Workfile Saved"
    hosts = ["flame"]
    actions = [RepairContextAction]

    def process(self, context):
        if not flapi.context_has_batch_instance(context):
            return

        try:
            workfiles = flapi.list_batch_workfiles()
        except Exception as error:
            raise PublishValidationError(
                f"Unable to check for a saved Batch workfile: {error}",
                title="Cannot check Batch workfile",
                description=(
                    "AYON could not look up the workfiles of the current "
                    "task, so it cannot tell whether the Batch was saved. "
                    "Check the current folder and task, then publish again."
                ),
            ) from error

        if workfiles:
            return

        batch_name = self._get_batch_name()
        raise PublishValidationError(
            f"The Batch group '{batch_name}' has no saved workfile.",
            title="Batch has no saved workfile",
            description=self._get_description(batch_name),
        )

    @classmethod
    def repair(cls, context):
        """Save the Batch as the next workfile version, using AYON Core."""
        if not flapi.is_batch_tab():
            raise RuntimeError(
                "Switch Flame to the Batch page and run Repair again."
            )

        from ayon_core.pipeline.workfile import save_next_version

        try:
            save_next_version()
        except Exception as error:
            raise RuntimeError(
                f"Unable to save the Batch workfile: {error}"
            ) from error

    @staticmethod
    def _get_batch_name():
        try:
            return flapi.get_current_batch().name.get_value()
        except Exception:
            return "current Batch"

    @staticmethod
    def _get_description(batch_name):
        return inspect.cleandoc(f"""
            ## Batch has no saved workfile

            The Batch group **{batch_name}** has not been saved as an AYON
            workfile for this task, so this publish cannot be linked to a
            workfile version.

            Do one of the following:

            - Save the Batch from the **Workfiles** tool.
            - Click **Repair** to save it now as the next available
              version.
        """)
