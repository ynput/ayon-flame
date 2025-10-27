import inspect

import pyblish.api
from ayon_core.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError,
)


class DeactivatePublishing(pyblish.api.Action):

    label = "Deactivate publishing"
    icon = "files-o"
    on = "failed"

    def process(self, context, plugin):
        # Get the errored instances
        failed = []
        for result in context.data["results"]:
            if (result["error"] is not None and result["instance"] is not None
               and result["instance"] not in failed):
                failed.append(result["instance"])

        # Apply pyblish.logic to get the instances for the plug-in
        instances = pyblish.api.instances_by_plugin(failed, plugin)
        create_context = context.data["create_context"]

        for instance in instances:
            instance_id = instance.data["instance_id"]
            ci = create_context.get_instance_by_id(instance_id)
            ci["active"] = False

        create_context.save_changes()


class ValidateProductsAttributes(
    OptionalPyblishPluginMixin,
    pyblish.api.InstancePlugin
):
    """Validate Product attributes."""

    label = "Validate Product Attributes"
    order = pyblish.api.ValidatorOrder
    settings_category = "flame"

    optional = True
    active = True

    actions = [DeactivatePublishing]

    def detect_failing_instance(self, instance):
        is_failed = instance.data.get("failing")

        if not is_failed:
            return

        return is_failed

    def process(self, instance):
        if not self.detect_failing_instance(instance):
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
