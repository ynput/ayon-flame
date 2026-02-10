
import pyblish




class IntegrateBatchgroup(pyblish.api.InstancePlugin):
    """Extract + Integrate Batchgroup Product data."""

    label = "Integrate Batchgroup"
    hosts = ["flame"]
    families = ["batchgroup"]

    def process(self, instance):
        self.log.info("Batchgroup: %r.", instance.data["extracted_batchgroup"])
        self.log.info("TODO load clip in there and re-publish.")
