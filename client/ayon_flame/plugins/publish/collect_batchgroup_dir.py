import pyblish.api


class CollectBatchgroupDir(pyblish.api.InstancePlugin):
    """Collect Batchgroup Directory."""

    order = pyblish.api.CollectorOrder + 0.496
    label = "Collect Batchgroup Directory"
    hosts = ["flame"]
    families = ["batchgroup"]

    def process(self, instance):
        publish_folder = instance.data["publishDir"]
        resources_folder = instance.data["resourcesDir"]

        self.log.info(f"Publish folder: {publish_folder}")
        self.log.info(f"Resources folder: {resources_folder}")
