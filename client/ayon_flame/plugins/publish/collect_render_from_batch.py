"""Collect render instances from batch Write File nodes."""
import pyblish.api


class CollectRenderFromBatch(pyblish.api.InstancePlugin):
    """Collect batch render instances and handle the review attribute."""

    order = pyblish.api.CollectorOrder + 0.49
    label = "Collect Render from Batch"
    hosts = ["flame"]
    families = ["render"]

    def process(self, instance):
        if (
            instance.data.get("flame_context") != "FlameMenuBatch"
            or not instance.data.get("write_node_name")
        ):
            self.log.debug("No valid batch render instance, skipping.")
            return

        if instance.data.get("creator_attributes", {}).get("review"):
            instance.data["families"].append("review")
            self.log.debug(
                f"Review enabled for render instance '{instance.name}'."
            )

        self.log.debug(
            f"Collected render instance '{instance.name}' "
            f"from Write File node '{instance.data.get('write_node_name')}'. "
            f"Families: {instance.data['families']}"
        )
