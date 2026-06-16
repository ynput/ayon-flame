""" Offer to iterate after a successful batch publish."""
import pyblish.api

from ayon_core.pipeline.publish import OptionalPyblishPluginMixin

import ayon_flame.api as flapi


class IntegrateBatchIteration(
    pyblish.api.InstancePlugin,
    OptionalPyblishPluginMixin,
):
    """Offer to save batch as new iteration after publishing is done.
    """

    label = "Iterate Batch After Publish"
    order = pyblish.api.IntegratorOrder + 0.5
    families = ["workfile"]
    hosts = ["flame"]
    optional = True
    active = True

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        if instance.data.get("batch_name") is None:
            self.log.info(
                "Instance is not a batch workfile, skipping."
            )
            return

        batch_name = instance.data.get("batch_name")
        batch = flapi.get_batch_from_workspace(batch_name)
        if not batch:
            raise ValueError(f"Batch group not found: {batch_name}")

        batch.iterate()
        self.log.info(
            f"Created new batch iteration after publish "
            f"(total: {len(batch.batch_iterations)})."
        )
