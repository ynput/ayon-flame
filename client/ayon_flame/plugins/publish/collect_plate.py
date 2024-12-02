import pyblish

import ayon_flame.api as ayfapi
from ayon_flame.otio import utils


class CollectPlate(pyblish.api.InstancePlugin):
    """Collect new plates."""

    order = order = pyblish.api.CollectorOrder - 0.48
    label = "Collect Plate"
    hosts = ["flame"]
    families = ["plate"]

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        instance.data["families"].append("clip")

        # Adjust instance data from parent otio timeline.
        otio_timeline = instance.context.data["otioTimeline"]
        otio_clip, marker = utils.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise RuntimeError("Could not retrieve otioClip for shot %r", instance)

        instance.data["otioClip"] = otio_clip

        review_switch = instance.data["creator_attributes"].get(
            "review")
        reviewable_source = instance.data["creator_attributes"].get(
            "reviewableSource")

        if review_switch:
            if reviewable_source == "clip_media":
                instance.data["families"].append("review")
            else:
                instance.data["reviewTrack"] = reviewable_source

        # remove review keys from instance data
        instance.data.pop("reviewableSource", None)
        instance.data.pop("review", None)

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
