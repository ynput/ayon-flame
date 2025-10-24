import inspect

import ayon_flame.api as ayfapi
import pyblish.api
from ayon_core.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError,
)


class ShowSegments(pyblish.api.Action):

    label = "Show Segments"
    icon = "files-o"
    on = "failed"

    def process(self, context, plugin):
        failed_segments = context.data["failedSegments"]

        if not failed_segments:
            return

        sequence = ayfapi.get_current_sequence(ayfapi.CTX.selection)
        with ayfapi.maintained_segment_selection(sequence):
            for segment in failed_segments:
                shot_name = segment.shot_name.get_value()
                segment_name = segment.name.get_value()
                segment.color = (1.0, 0.0, 0.0)
                clip_msg = (
                    f"Clip name: {segment_name} with shot name: {shot_name}")
                self.log.info(clip_msg)


class ValidateSegments(
    OptionalPyblishPluginMixin,
    pyblish.api.ContextPlugin
):
    """Validate segments attributes."""

    label = "Validate Segments"
    order = pyblish.api.ValidatorOrder
    settings_category = "flame"

    optional = False
    active = True

    actions = [ShowSegments]

    def process(self, context):
        failed_segments = context.data["failedSegments"]

        if not failed_segments:
            return

        msg = "Timeline Clips failing validation:"
        msg_html = self.get_description()
        for segment in failed_segments:
            shot_name = segment.shot_name.get_value()
            segment_name = segment.name.get_value()
            clip_msg = (
                f"Clip name: '{segment_name}' with shot name: '{shot_name}'")
            msg += f"\n{clip_msg}"

            msg_html += f"<br/> - {clip_msg}"

        raise PublishValidationError(
            title="Missing correct segments attributes",
            message=msg,
            description=msg_html
        )

    def get_description(self):
        return inspect.cleandoc("""
            ## Following clips are failing validation:
            <br/>
            Make sure your clips on timeline are not converted to BatchFX
            or are not Hard Commited. This way they will lose their link to
            the original Media source file path and we are not able
            to publish them anymore.
            <br/><br/>
            <b>Following clips are failing validation:</b>
        """)
