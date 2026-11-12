import inspect

import pyblish.api
from ayon_core.pipeline import get_current_context
from ayon_core.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError,
)

import ayon_flame.api as flapi


class OpenBatchWorkfilesAction(pyblish.api.Action):
    """Open the Workfiles tool of the Batch menu."""

    label = "Open Work Files..."
    on = "failed"
    icon = "files-o"

    def process(self, context, plugin):
        from ayon_flame.api.menu import show_batch_workfiles

        show_batch_workfiles()


class ValidateBatchWorkfileLatest(
    OptionalPyblishPluginMixin,
    pyblish.api.ContextPlugin
):
    """Validate published batch groups are on the last Batch workfile.

    Batch groups stay on the shared Flame desktop between sessions. A batch
    group opened from an older workfile, or not linked to a workfile in
    this Flame session, may hold older work than the last workfile of its
    task. Available only for Batch menu publishing.
    """

    label = "Validate Batch Workfile Is Latest"
    order = pyblish.api.ValidatorOrder
    hosts = ["flame"]

    optional = True
    active = True

    actions = [OpenBatchWorkfilesAction]

    @classmethod
    def apply_settings(cls, project_settings):
        settings = (
            project_settings["flame"]["publish"].get(cls.__name__) or {}
        )
        cls.optional = settings.get("optional", cls.optional)
        cls.active = settings.get("active", cls.active)
        # Only available for Batch menu publishing.
        cls.enabled = (
            settings.get("enabled", True)
            and flapi.CTX.context == "FlameMenuBatch"
        )

    def process(self, context):
        if not self.is_active(context.data):
            self.log.info("Validation is disabled.")
            return

        issues = []
        for batch in flapi.get_instances_batches(context).values():
            batch_context = (
                flapi.get_batch_products_context(batch)
                or get_current_context()
            )
            issue = flapi.get_batch_workfile_issue(
                batch,
                batch_context["folder_path"],
                batch_context["task_name"],
            )
            if issue:
                issues.append(issue)

        if not issues:
            return

        raise PublishValidationError(
            "Batch group is not on the last workfile: " + " ".join(issues),
            title="Batch workfile is not the latest",
            description=self.get_description(issues),
        )

    def get_description(self, issues):
        lines = "\n".join(f"- {issue}" for issue in issues)
        return inspect.cleandoc("""
            ### Batch workfile is not the latest

            {lines}

            The batch group may hold older work than the last workfile of
            its task. Open the last workfile from **Work Files...** in the
            Batch menu and publish from it, or turn this check off to
            publish this batch group anyway.
        """).format(lines=lines)
