""" Collect batch instance from current Flame context.
"""
import pyblish.api


class CollectBatchInstance(pyblish.api.InstancePlugin):
    """Pin the batch workfile product to the AYON workfile version.

    Overrides the studio `follow_workfile_version` setting: the publish
    has to advance with the workfile, or `IntegrateBatchIteration` cannot
    keep a second publish from overwriting the first.
    """

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

        # `CollectBatchVersion` reads the version off the AYON workfile
        # name; core applies the context version from there
        # (collect_anatomy_instance_data.py), falling back to the next
        # available version when there is no workfile to read it from
        instance.data["followWorkfileVersion"] = True
