import pyblish.api
from ayon_core.pipeline import get_current_context

import ayon_flame.api as flapi


class ExtractBatchWorkfileSave(pyblish.api.ContextPlugin):
    """Save each published batch group to its Batch workfile.

    The Batch workfile is the source ('currentFile') of a Batch publish, so
    it has to hold what is published, as Nuke, Maya and Houdini save their
    workfile before extracting. Only the workfile saved or opened for the
    batch group in this Flame session is written. The last workfile of the
    task, used as the source when there is none, is not: it may hold
    another batch group.
    """

    label = "Save Batch Workfile"
    order = pyblish.api.ExtractorOrder - 0.49
    hosts = ["flame"]

    def process(self, context):
        batches = flapi.get_instances_batches(context)
        for batch_name, batch in batches.items():
            batch_context = (
                flapi.get_batch_products_context(batch)
                or get_current_context()
            )
            workfile_path = flapi.get_session_batch_workfile(
                batch,
                batch_context["folder_path"],
                batch_context["task_name"],
            )
            if not workfile_path:
                self.log.warning(
                    f"Batch group '{batch_name}' has no Batch workfile in"
                    " this Flame session, its publish source may not hold"
                    " what is published. Use Work Files > Open or Save As."
                )
                continue

            flapi.write_batch_workfile(batch, workfile_path)
            self.log.info(
                f"Saved batch group '{batch_name}' to {workfile_path}"
            )
