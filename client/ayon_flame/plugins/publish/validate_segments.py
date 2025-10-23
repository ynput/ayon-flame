import pyblish.api
from ayon_core.pipeline.publish import PublishValidationError


class ValidateSegments(pyblish.api.ContextPlugin):
    """Validate segments attributes."""

    label = "Validate Segments"
    order = pyblish.api.ValidateOrder

    def process(self, context):
        failed_segments = context.data["failedSegments"]

        if not failed_segments:
            return

        msg = "Timeline Clips failing validation:"
        msg_html = "## Following clips are failing validation:"
        for segment in failed_segments:
            shot_name = segment.shot_name.get_value()
            segment_name = segment.name.get_value()
            clip_msg = (
                f"Clip name: {segment_name} with shot name: {shot_name}")
            msg += f"\n{clip_msg}"

            msg_html += f"<br> - {clip_msg}"

        raise PublishValidationError(
            title="Missing correctsegments attributes",
            message=msg,
            description=msg_html
        )
