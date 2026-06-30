import pyblish.api

import ayon_flame.api as flapi


class CollectBatchVersion(pyblish.api.ContextPlugin):
    """ Collect "version" from current batch if any.
    """

    order = pyblish.api.CollectorOrder
    label = "Collect Batch Version"
    hosts = ["flame"]

    def process(self, context):
        # No need to collect current batch version as "workfile"
        # version if no instance related to batch is found in context.
        for instance in context:
            if instance.data.get("flame_context") == "FlameMenuBatch":
                break
        else:
            self.log.debug("No instances related to batch found in context.")
            return

        # Flame batch as its own iteration management,
        # Note that current iteration might or might not
        # have been published through AYON.
        batch = flapi.get_current_batch()
        context.data["version"] = batch.current_iteration_number
        self.log.debug(
            f"Collected context version: {context.data['version']} "
            f"from batch"
        )
