import pyblish.api

from ayon_flame.otio import utils


class CollectBatchgroup(pyblish.api.InstancePlugin):
    """Collect Shot related batchgroup workfile products."""

    order = pyblish.api.CollectorOrder - 0.47
    label = "Collect Batchgroup"
    hosts = ["flame"]
    families = ["workfile"]

    def process(self, instance):
        creator_identifier = instance.data["creator_identifier"]

        if creator_identifier != "io.ayon.creators.flame.batchgroup":
            # only interested in flame batchgroup
            return

        # Retrieve instance data from parent instance shot instance.
        parent_instance_id = instance.data["parent_instance_id"]
        edit_shared_data = instance.context.data["editorialSharedData"]
        instance.data.update(
            edit_shared_data[parent_instance_id]
        )

        # Adjust instance data from parent otio timeline.
        otio_timeline = instance.context.data["otioTimeline"]
        otio_clip, marker = utils.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise RuntimeError(
                f"Could not retrieve otioClip for shot {instance}")

        instance.data["otioClip"] = otio_clip

        clip_src = instance.data["otioClip"].source_range
        clip_src_in = clip_src.start_time.to_frames()
        clip_src_out = clip_src_in + clip_src.duration.to_frames()
        instance.data.update({
            "clipInH": clip_src_in,
            "clipOutH": clip_src_out,
            "families": ["batchgroup"]
        })
        self.log.info(
            f"Collected batchgroup workfile products for shot {instance}")
