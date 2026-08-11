""" Iterate the batch group after a successful batch publish."""
import pyblish.api

import ayon_flame.api as flapi


class IntegrateBatchIteration(pyblish.api.InstancePlugin):
    """Save the batch as a new iteration once publishing is done.

    Not optional: the published version is pinned to the workfile version
    by `CollectBatchInstance`, so the workfile has to advance after every
    publish. Without it, a second publish would overwrite the first.
    """

    label = "Iterate Batch After Publish"
    order = pyblish.api.IntegratorOrder + 0.5
    families = ["workfile"]
    hosts = ["flame"]

    def process(self, instance):
        if instance.data.get("batch_name") is None:
            self.log.info(
                "Instance is not a batch workfile, skipping."
            )
            return

        batch_name = instance.data.get("batch_name")
        batch = flapi.get_batch_from_workspace(batch_name)
        if not batch:
            raise ValueError(f"Batch group not found: {batch_name}")

        # `batch_setup_iterated_post` fires here too, and that hook is what
        # saves the next AYON workfile version, bumping again would make
        # a publish produce two of them
        batch.iterate()
        self.log.info("Created new batch iteration after publish.")
