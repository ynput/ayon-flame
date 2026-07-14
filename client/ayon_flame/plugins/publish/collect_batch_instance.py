""" Collect batch instance from current Flame context.
"""
import pyblish.api

import ayon_flame.api as flapi


class CollectBatchInstance(pyblish.api.InstancePlugin):
    """Collect batch render instances and handle the review attribute."""

    order = pyblish.api.CollectorOrder - 0.48
    label = "Collect Batch instance"
    families = ["workfile"]
    hosts = ["flame"]

    def process(self, instance):
        if instance.data.get("batch_name") is None:
            self.log.info(
                "Instance is not a batch workfile, skipping."
            )
            return

        batch_name = instance.data["batch_name"]
        batch = flapi.get_batch_from_workspace(batch_name)
        if not batch:
            raise ValueError(f"Batch group not found: {batch_name}")

        instance.data["version"] = batch.current_iteration_number
        instance.data["followWorkfileVersion"] = False
        self.log.debug(f"Collected batch version: {instance.data['version']}")
