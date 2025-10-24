import inspect

import ayon_flame.api as ayfapi
import pyblish.api
from ayon_core.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError,
)


class ShowSegmentsRed(pyblish.api.Action):

    label = "Show Segments with Red Colour"
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
                segment.colour = (1.0, 0.0, 0.0)
                clip_msg = (
                    f"Clip name: {segment_name} with shot name: {shot_name}")
                self.log.info(clip_msg)


class ValidateFailingProducts(
    OptionalPyblishPluginMixin,
    pyblish.api.InstancePlugin
):
    """Validate Product attributes."""

    label = "Validate Product Attributes"
    order = pyblish.api.ValidatorOrder
    settings_category = "flame"

    optional = True
    active = True

    actions = [ShowSegmentsRed]

    def process(self, instance):
        is_failed = instance.data.get("failing")

        if not is_failed:
            return

        segment = instance.data["item"]
        otio_clip = instance.data["otioClip"]
        reference_name = otio_clip.media_reference.name

        msg = "Product is failing validation due following reason:"
        msg_html = self.get_description()

        shot_name = segment.shot_name.get_value()
        segment_name = segment.name.get_value()
        clip_msg = (
            f"Clip name: '{segment_name}' with shot name: '{shot_name}'\n"
            f"Problem: '{reference_name}'"
        )
        msg += f"\n{clip_msg}"

        msg_html += f"{clip_msg}"

        raise PublishValidationError(
            title="Failing Product Validation",
            message=msg,
            description=msg_html
        )

    def get_description(self):
        return inspect.cleandoc("""
            ## Product is failing validation:
            <br/>
            Make sure your clips on timeline are not converted to BatchFX<br/>
            or are not Hard Commited. This way they will lose their link <br/>
            to the original Media source file path and we are not able<br/>
            to publish them anymore.
            <br/><br/>
            Also make sure timeline clip is having standart name.
            <br/><br/>
            <b>Validation problem:</b>
            <br/>
        """)
