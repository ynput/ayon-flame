import pyblish

import ayon_flame.api as ayfapi


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

        instance.data["families"].append("clip")

        # Build otio timeline and otio clip from clip item.
        instance.data["otioClip"] = otio_clip

        SHARED_KEYS = (
            "folderPath",
            "fps",
            "handleStart",
            "handleEnd",
            "item",
            "resolutionWidth",
            "resolutionHeight",
            "retimedHandles",
            "retimedFramerange",
            "path",
            "pixelAspect",
            "sourceFirstFrame",
            "versionData",
            "workfileFrameStart",
            "xml_overrides",
            "failing",
        )

        # TODO solve reviewable options
        #review_switch = instance.data["creator_attributes"].get(
        #    "review")
        #if review_switch is True:
        #    instance.data["families"].append("review")

        segment_item = instance.data["item"]
        sequence = ayfapi.get_current_sequence(ayfapi.CTX.selection)
        with ayfapi.maintained_segment_selection(sequence):
            clip_data = ayfapi.get_segment_attributes(segment_item)

        version_data = instance.data.setdefault("versionData", {})
        version_data["colorSpace"] = clip_data["colour_space"]
        instance.data["colorspace"] = clip_data["colour_space"]
