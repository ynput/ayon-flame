import os
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

        # solve reviewable options
        review_switch = instance.data["creator_attributes"].get(
            "review")
        reviewable_source = instance.data["creator_attributes"].get(
            "reviewableSource")

        if review_switch is True:
            if reviewable_source == "clip_media":
                instance.data["families"].append("review")
                instance.data.pop("reviewTrack", None)

                # Retrieve source clip media from otio clip.
                # image sequence
                if hasattr(otio_clip.media_reference, "target_url_for_image_number"):
                    file_url = otio_clip.media_reference.target_url_for_image_number(0)
                    sequence_length = (
                        otio_clip.media_reference.end_frame()
                        - otio_clip.media_reference.start_frame
                    )
                    file_names = [
                        os.path.basename(
                            otio_clip.media_reference.target_url_for_image_number(frame)
                        )
                        for frame in range(0, sequence_length)
                    ]

                # movie
                else:
                    file_url = otio_clip.media_reference.target_url
                    file_names = os.path.basename(file_url)

                _, ext = os.path.splitext(file_url)

                repre = {
                    "name": ext[1:],
                    "ext": ext[1:],
                    "files": file_names,
                    "stagingDir": os.path.dirname(file_url),
                    "tags": ["review", "delete"]
                }
                instance.data["representations"].append(repre)

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

        segment_item = instance.data["item"]
        clip_data = ayfapi.get_segment_attributes(segment_item)
        version_data = instance.data.setdefault("versionData", {})
        version_data["colorSpace"] = clip_data["colour_space"]
        instance.data["colorspace"] = clip_data["colour_space"]

        instance.data["shotDurationFromSource"] = instance.data.get("retimedFramerange")
