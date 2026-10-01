import pyblish.api

import ayon_flame.api as flapi


class CollectCurrentFile(pyblish.api.ContextPlugin):
    """Collect 'currentFile' from the latest AYON workfile of the context.

    The Flame host is a workfile host, so publishing expects the key to be
    set. Flame has no native scene path, therefore the latest existing
    Batch workfile of the current context is used when publishing a Batch,
    and 'None' otherwise. The key is always present.
    """

    order = pyblish.api.CollectorOrder - 0.5
    label = "Collect Current File"
    hosts = ["flame"]

    def process(self, context):
        context.data["currentFile"] = None
        if not flapi.context_has_batch_instance(context):
            return

        try:
            workfiles = flapi.list_batch_workfiles()
        except Exception:
            self.log.warning(
                "Could not list workfiles of the current context.",
                exc_info=True,
            )
            return

        available = [workfile for workfile in workfiles if workfile.available]
        if not available:
            return

        latest = max(available, key=lambda item: item.version or -1)
        context.data["currentFile"] = latest.filepath
        self.log.debug(f"Collected current file: {latest.filepath}")
