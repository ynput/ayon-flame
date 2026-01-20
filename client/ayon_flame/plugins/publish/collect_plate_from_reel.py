import pyblish
from pprint import pformat

import opentimelineio as otio

from ayon_flame.otio import flame_export
from ayon_flame.api import lib


class CollectReelPlate(pyblish.api.InstancePlugin):
    """Collect new plates from Reel."""

    order = order = pyblish.api.CollectorOrder - 0.48
    label = "Collect Plate from Reel"
    hosts = ["flame"]
    families = ["plate"]

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        if (instance.data.get("flame_context") != "FlameMenuUniversal"):
            # Plate instance could also come from Timeline.
            self.log.debug("Current plate instance is part of a timeline.")
            return

        # Adjust instance families
        instance.data["families"].append("clip")
        if instance.data["creator_attributes"].get("review"):
            instance.data["families"].append("review")

        clip_data = instance.data["clip_data"]
        version_data = instance.data.setdefault("versionData", {})
        version_data["colorSpace"] = clip_data["colour_space"]

        instance_clip_data = {
            "clipIn": clip_data["record_in"],
            "clipOut": clip_data["record_out"],
            "colorspace": clip_data["colour_space"],
            "fps": clip_data["fps"],
            "frameStart": clip_data["record_in"],
            "frameEnd": clip_data["record_out"],
            "handleStart": 0,
            "handleEnd": 0,
            "item": instance.data["transientData"]["clip_item"],
            "path": clip_data["fpath"],
            "resolutionWidth": clip_data["width"],
            "resolutionHeight": clip_data["height"],
            "sourceFirstFrame": clip_data["source_in"],
            "xml_overrides": {},
        }

        # Build otio timeline and otio clip from clip item.
        flame_export.OtioExportCTX.set_fps(instance_clip_data["fps"])

        clip_data["PySegment"] = lib.get_clip_segment(
            instance_clip_data["item"]
        )
        otio_clip = flame_export.create_otio_clip(clip_data)
        otio_timeline = otio.schema.Timeline(
            tracks=[otio.schema.Track(children=[otio_clip])]
        )

        instance_clip_data.update({
            "otioClip": otio_clip,
            "otioTimeline": otio_timeline,
        })

        self.log.debug(f">>> Clip data: {pformat(instance_clip_data)}")
        instance.data.update(instance_clip_data)
