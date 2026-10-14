import inspect
import os

import pyblish.api
from ayon_core.pipeline import registered_host
from ayon_core.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError,
    RepairContextAction,
)

import ayon_flame.api as flapi


class OpenWorkfilesAction(pyblish.api.Action):
    """Open the editorial Workfiles tool of the Flame main menu."""

    label = "Open Work Files..."
    on = "failed"
    icon = "files-o"

    def process(self, context, plugin):
        from ayon_core.tools.utils import host_tools

        host_tools.show_workfiles()


class ValidateEditorialWorkfileSaved(
    OptionalPyblishPluginMixin,
    pyblish.api.ContextPlugin
):
    """Validate the editorial workfile was saved.

    Available only for editorial (Timeline, Media Panel) publishing, Batch
    menu publishing has no editorial workfile.
    """

    label = "Validate Editorial Workfile Saved"
    order = pyblish.api.ValidatorOrder - 0.1
    hosts = ["flame"]

    optional = True
    active = True

    actions = [RepairContextAction, OpenWorkfilesAction]

    @classmethod
    def apply_settings(cls, project_settings):
        settings = (
            project_settings["flame"]["publish"].get(cls.__name__) or {}
        )
        cls.optional = settings.get("optional", cls.optional)
        cls.active = settings.get("active", cls.active)
        # Never available for Batch menu publishing.
        cls.enabled = (
            settings.get("enabled", True)
            and flapi.CTX.context != "FlameMenuBatch"
        )

    def process(self, context):
        if not self.is_active(context.data):
            self.log.info("Validation is disabled.")
            return

        workfile_path = registered_host().get_current_workfile()
        if workfile_path and os.path.exists(workfile_path):
            self.log.debug(f"Editorial workfile found: {workfile_path}")
            return

        raise PublishValidationError(
            "Editorial workfile is not saved.",
            title="Editorial workfile not saved",
            description=self.get_description(),
        )

    @classmethod
    def repair(cls, context):
        from ayon_core.pipeline.workfile import save_next_version

        save_next_version()

    def get_description(self):
        return inspect.cleandoc("""
            ### Editorial workfile not saved

            No editorial workfile was saved or opened in this Flame
            session, so the publish cannot point to its source.

            Save it from **AYON > 2 - Work Files...** in the Flame main
            menu or click **Repair** to save the next workfile version now.
        """)
