from pprint import pformat

import pyblish

from ayon_flame.otio import utils


class CollectTimelinePlate(pyblish.api.InstancePlugin):
    """Collect new plates from Timeline."""

    order = order = pyblish.api.CollectorOrder - 0.48
    label = "Collect Plate from Timeline"
    hosts = ["flame"]
    families = ["plate"]

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        if (
            instance.data.get("flame_context")
            and instance.data["flame_context"] != "FlameMenuTimeline"
        ):
            # Plate instance could also come from Reel and Media panel clips.
            self.log.debug("Current plate instance is not part of a timeline.")
            return

        instance.data["families"].append("clip")

        # Adjust instance data from parent otio timeline.
        otio_timeline = instance.context.data["otioTimeline"]
        otio_clip, _ = utils.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise RuntimeError(
                f"Could not retrieve otioClip for shot {instance}")

        instance.data["otioClip"] = otio_clip

        # solve reviewable options
        review_switch = instance.data["creator_attributes"].get(
            "review")
        reviewable_source = instance.data["creator_attributes"].get(
            "reviewableSource")

        if review_switch is True:
            if reviewable_source == "clip_media":
                instance.data["families"].append("review")
                instance.data.pop("reviewTrack", None)
            else:
                instance.data["reviewTrack"] = reviewable_source

        # remove creator-specific review keys from instance data
        instance.data.pop("reviewableSource", None)
        instance.data.pop("review", None)

        # Retrieve instance data from parent instance shot instance.
        parent_instance_id = instance.data["parent_instance_id"]
        edit_shared_data = instance.context.data["editorialSharedData"]

        instance.data.update(
            edit_shared_data[parent_instance_id]
        )

        clip_data = instance.data["clipData"]
        version_data = instance.data.setdefault("versionData", {})
        version_data["colorSpace"] = clip_data["colour_space"]
        instance.data["colorspace"] = clip_data["colour_space"]

        instance.data["shotDurationFromSource"] = instance.data.get(
            "retimedFramerange")

        self.log.debug(f"__ inst_data: {pformat(instance.data)}")
