import os

import pyblish.api
from ayon_core.pipeline import get_current_context

import ayon_flame.api as flapi


class ExtractBatchWorkfileSave(pyblish.api.ContextPlugin):
    """Save the published batch group to its Batch workfile.

    The Batch workfile is the source ('currentFile') of a Batch publish, so
    it has to hold what is published, as Nuke, Maya and Houdini save their
    workfile before extracting. The source is written only when it is the
    Batch workfile saved or opened for the batch group in this Flame
    session. The last workfile of the task, used as the source when there
    is none, is not: it may hold another batch group.

    Follows the setting 'flame/update_batch_workfile', like a Flame project
    save.
    """

    label = "Save Batch Workfile"
    order = pyblish.api.ExtractorOrder - 0.49
    hosts = ["flame"]

    settings_category = "flame"
    update_batch_workfile = True

    @classmethod
    def apply_settings(cls, project_settings):
        cls.update_batch_workfile = (
            project_settings["flame"]
            .get("update_batch_workfile", {})
            .get("enabled", True)
        )

    def process(self, context):
        batches = flapi.get_instances_batches(context)
        if not batches:
            return

        if not self.update_batch_workfile:
            self.log.info(
                "Updating Batch workfiles is disabled, the publish source"
                " may not hold what is published."
            )
            return

        current_file = context.data.get("currentFile")
        # The source follows the first published batch group, see
        # 'CollectCurrentWorkfile'.
        batch_name, batch = next(iter(batches.items()))
        batch_context = (
            flapi.get_batch_products_context(batch)
            or get_current_context()
        )
        workfile_path = flapi.get_session_batch_workfile(
            batch,
            batch_context["folder_path"],
            batch_context["task_name"],
        )
        if (
            not workfile_path
            or not current_file
            or not os.path.exists(workfile_path)
            or os.path.normpath(workfile_path)
            != os.path.normpath(current_file)
        ):
            self.log.warning(
                f"Batch group '{batch_name}' has no Batch workfile in this"
                " Flame session, the publish source may not hold what is"
                " published. Use Work Files > Open or Save As."
            )
            return

        flapi.write_batch_workfile(batch, workfile_path)
        self.log.info(f"Saved batch group '{batch_name}' to {workfile_path}")
