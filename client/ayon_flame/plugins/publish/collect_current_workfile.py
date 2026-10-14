import os

import pyblish.api
from ayon_core.pipeline import registered_host

import ayon_flame.api as flapi


class CollectCurrentWorkfile(pyblish.api.ContextPlugin):
    """Use the saved AYON workfile as 'currentFile' when there is one.

    Flame keeps its work in the project database, so earlier collectors
    set 'currentFile' to a 'Flame/<project>[/<sequence>]' placeholder.
    Batch publishes use the Batch workfile of the current batch group,
    any other publish uses the editorial workfile of the registered host.
    The placeholder is kept when no workfile was saved.
    """

    label = "Collect Current Workfile"
    order = pyblish.api.CollectorOrder - 0.49
    hosts = ["flame"]

    def process(self, context):
        workfile_path = None
        if any(
            instance.data.get("flame_context") == "FlameMenuBatch"
            for instance in context
        ):
            try:
                batch = flapi.get_current_batch()
            except RuntimeError:
                batch = None
            if batch is not None:
                workfile_path = flapi.get_workfile_path(batch)
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
