import os

import pyblish.api
from ayon_core.pipeline import get_current_context, registered_host

import ayon_flame.api as flapi


class CollectCurrentWorkfile(pyblish.api.ContextPlugin):
    """Use the saved AYON workfile as 'currentFile' when there is one.

    Flame keeps its work in the project database, so earlier collectors
    set 'currentFile' to a 'Flame/<project>[/<sequence>]' placeholder.
    Batch publishes use the last Batch workfile of the task of the
    published batch group products, any other publish uses the editorial
    workfile of the registered host.
    The placeholder is kept when no workfile was saved.
    """

    label = "Collect Current Workfile"
    order = pyblish.api.CollectorOrder - 0.49
    hosts = ["flame"]

    def process(self, context):
        workfile_path = None
        batches = flapi.get_instances_batches(context)
        if batches:
            batch = next(iter(batches.values()))
            batch_context = (
                flapi.get_batch_products_context(batch)
                or get_current_context()
            )
            workfile_path = flapi.get_last_batch_workfile(
                batch_context["folder_path"], batch_context["task_name"]
            )
        else:
            workfile_path = registered_host().get_current_workfile()

        if not workfile_path or not os.path.exists(workfile_path):
            self.log.debug(
                "No saved workfile, keeping current file "
                f"'{context.data.get('currentFile')}'."
            )
            return

        context.data["currentFile"] = workfile_path
        self.log.debug(f"Collected current workfile: {workfile_path}")
