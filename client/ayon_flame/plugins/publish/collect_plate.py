import pyblish
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
        # Retrieve instance data from parent instance shot instance.
        parent_instance_id = instance.data["parent_instance_id"]
        edit_shared_data = instance.context.data["editorialSharedData"]
        parent_shot_instance_data = edit_shared_data[parent_instance_id]
        parent_shot_creator_attrs = parent_shot_instance_data[
            "creator_attributes"]

        instance.data.update(
            parent_shot_instance_data
        )
        # add also shot's creator attributes for missing linked media clips
        # it needs frame range and clip ranges which are usually processed
        # from collect_otio_frame_ranges but without clip link the
        # otio_clip is missing reference with available frame ranges
        instance.data["shotCreatorAttrs"] = parent_shot_creator_attrs

        clip_data = instance.data["clipData"]
        instance.data["families"].append("clip")

        # Adjust instance data from parent otio timeline.
        otio_timeline = instance.context.data["otioTimeline"]
        otio_clip, marker = utils.get_marker_from_clip_index(
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


        version_data = instance.data.setdefault("versionData", {})
        version_data["colorSpace"] = clip_data["colour_space"]
        instance.data["colorspace"] = clip_data["colour_space"]

        instance.data["shotDurationFromSource"] = instance.data.get(
            "retimedFramerange")
