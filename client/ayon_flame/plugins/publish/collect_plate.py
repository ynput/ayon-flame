import pyblish

import ayon_flame.api as ayfapi


class CollectPlate(pyblish.api.InstancePlugin):
    """Collect new plates."""

    order = order = pyblish.api.CollectorOrder - 0.094
    label = "Collect Plate"
    hosts = ["flame"]
    families = ["plate"]

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        instance.data["families"].append("clip")

        # Retrieve instance data from parent instance shot instance.
        parent_instance_id = instance.data["parent_instance_id"]
        edit_shared_data = instance.context.data["editorialSharedData"]

        instance.data.update(
            edit_shared_data[parent_instance_id]
        )

        segment_item = instance.data["item"]
        clip_data = ayfapi.get_segment_attributes(segment_item)
        version_data = instance.data.setdefault("versionData", {})
        version_data["colorSpace"] = clip_data["colour_space"]
        instance.data["colorspace"] = clip_data["colour_space"]

        instance.data["shotDurationFromSource"] = instance.data.get("retimedFramerange")
