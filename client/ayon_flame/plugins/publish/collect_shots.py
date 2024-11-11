import pyblish
import re

import ayon_flame.api as ayfapi
from ayon_flame.otio import flame_export

# constatns
NUM_PATERN = re.compile(r"([0-9\.]+)")
TXT_PATERN = re.compile(r"([a-zA-Z]+)")


class CollectShot(pyblish.api.InstancePlugin):
    """Collect new shots."""

    order = order = pyblish.api.CollectorOrder - 0.095
    label = "Collect Shots"
    hosts = ["flame"]
    families = ["shot"]

    SHARED_KEYS = (
        "folderPath",
        "fps",
        "handleStart",
        "handleEnd",
        "item",
        "otioClip",
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
    )

    # TODO: add to own plugin for Flame
    # TODO: toggle for marking task which should be used for product parent
    add_tasks = []    

    @classmethod
    def _inject_editorial_shared_data(cls, instance):
        """
        Args:
            instance (obj): The publishing instance.
        """
        context = instance.context
        instance_id = instance.data["instance_id"]

        # Inject folderPath and other creator_attributes to ensure
        # new shots/hierarchy are properly handled.
        creator_attributes = instance.data['creator_attributes']
        instance.data.update(creator_attributes)

        # Inject/Distribute instance shot data as editorialSharedData
        # to make it available for clip/plate/audio products
        # in sub-collectors.
        if not context.data.get("editorialSharedData"):
            context.data["editorialSharedData"] = {}

        context.data["editorialSharedData"][instance_id] = {
            key: value for key, value in instance.data.items()
            if key in cls.SHARED_KEYS
        }

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        instance.data["integrate"] = False  # no representation for shot

        # Adjust instance data from parent otio timeline.
        otio_timeline = instance.context.data["otioTimeline"]
        otio_clip, marker = self.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise RuntimeError("Could not retrieve otioClip for shot %r", instance)

        # Compute fps from creator attribute.
        creator_attrs = instance.data['creator_attributes']
        if creator_attrs["fps"] == "from_selection":
            creator_attrs["fps"] = instance.context.data["fps"]

        # Retrieve AyonData marker for associated clip.
        instance.data["otioClip"] = otio_clip

        # Compute additional data
        for segment_item in instance.context.data["flameSelectedSegments"]:
            data = ayfapi.get_segment_data_marker(segment_item) or {}
            if data.get("clip_index") == instance.data["clip_index"]:
                break

        comment_attributes = self._get_comment_attributes(segment_item)
        instance.data.update(comment_attributes)

        clip_data = ayfapi.get_segment_attributes(segment_item)
        clip_name = clip_data["segment_name"]
        self.log.debug("clip_name: {}".format(clip_name))

        # get file path
        file_path = clip_data["fpath"]
        first_frame = ayfapi.get_frame_from_filename(file_path) or 0

        # get file path
        head, tail = self._get_head_tail(
            clip_data,
            otio_clip,
            creator_attrs["handleStart"],
            creator_attrs["handleEnd"]
        )

        # make sure there is not NoneType rather 0
        if head is None:
            head = 0
        if tail is None:
            tail = 0

        # make sure value is absolute
        if head != 0:
            head = abs(head)
        if tail != 0:
            tail = abs(tail)

        # solve handles length
        creator_attrs["handleStart"] = min(
            creator_attrs["handleStart"], head)
        creator_attrs["handleEnd"] = min(
            creator_attrs["handleEnd"], tail)

        # Adjust info from track_item on timeline
        workfile_start = self._set_workfile_start(creator_attrs)

        instance.data.update({
            "item": segment_item,
            "path": file_path,
            "sourceFirstFrame": int(first_frame),
            "workfileFrameStart": workfile_start,

            #TODO
            "flameAddTasks": self.add_tasks,
            "tasks": {
                task["name"]: {"type": task["type"]}
                for task in self.add_tasks
            },
        })

        self._get_resolution_to_data(instance.data, instance.context)
        self._inject_editorial_shared_data(instance)
        self.log.debug("__ inst_data: {}".format(pformat(inst_data)))

    @staticmethod
    def _set_workfile_start(data):
        include_handles = data.get("includeHandles")
        workfile_start = data["workfileFrameStart"]
        handle_start = data["handleStart"]

        if include_handles:
            workfile_start += handle_start

        return workfile_start

    def _get_comment_attributes(self, segment):
        comment = segment.comment.get_value()

        # try to find attributes
        attributes = {
            "xml_overrides": {
                "pixelRatio": 1.00}
        }
        # search for `:`
        for split in self._split_comments(comment):
            # make sure we ignore if not `:` in key
            if ":" not in split:
                continue

            self._get_xml_preset_attrs(
                attributes, split)

        # add xml overrides resolution to instance data
        xml_overrides = attributes["xml_overrides"]
        if xml_overrides.get("width"):
            attributes.update({
                "resolutionWidth": xml_overrides["width"],
                "resolutionHeight": xml_overrides["height"],
                "pixelAspect": xml_overrides["pixelRatio"]
            })

        return attributes

    def _get_xml_preset_attrs(self, attributes, split):

        # split to key and value
        key, value = split.split(":")

        for attr_data in self.xml_preset_attrs_from_comments:
            a_name = attr_data["name"]
            a_type = attr_data["type"]

            # exclude all not related attributes
            if a_name.lower() not in key.lower():
                continue

            # get pattern defined by type
            pattern = TXT_PATERN
            if a_type in ("number", "float"):
                pattern = NUM_PATERN

            res_goup = pattern.findall(value)

            # raise if nothing is found as it is not correctly defined
            if not res_goup:
                raise ValueError((
                    "Value for `{}` attribute is not "
                    "set correctly: `{}`").format(a_name, split))

            if "string" in a_type:
                _value = res_goup[0]
            if "float" in a_type:
                _value = float(res_goup[0])
            if "number" in a_type:
                _value = int(res_goup[0])

            attributes["xml_overrides"][a_name] = _value

        # condition for resolution in key
        if "resolution" in key.lower():
            res_goup = NUM_PATERN.findall(value)
            # check if axpect was also defined
            # 1920x1080x1.5
            aspect = res_goup[2] if len(res_goup) > 2 else 1

            width = int(res_goup[0])
            height = int(res_goup[1])
            pixel_ratio = float(aspect)
            attributes["xml_overrides"].update({
                "width": width,
                "height": height,
                "pixelRatio": pixel_ratio
            })

    def _split_comments(self, comment_string):
        # first split comment by comma
        split_comments = []
        if "," in comment_string:
            split_comments.extend(comment_string.split(","))
        elif ";" in comment_string:
            split_comments.extend(comment_string.split(";"))
        else:
            split_comments.append(comment_string)

        return split_comments

    def _get_resolution_to_data(self, data, context):
        assert data.get("otioClip"), "Missing `otioClip` data"

        # solve source resolution option
        if data.get("sourceResolution", None):
            otio_clip_metadata = data[
                "otioClip"].media_reference.metadata
            data.update({
                "resolutionWidth": otio_clip_metadata[
                        "ayon.source.width"],
                "resolutionHeight": otio_clip_metadata[
                    "ayon.source.height"],
                "pixelAspect": otio_clip_metadata[
                    "ayon.source.pixelAspect"]
            })
        else:
            otio_tl_metadata = context.data["otioTimeline"].metadata
            data.update({
                "resolutionWidth": otio_tl_metadata["ayon.timeline.width"],
                "resolutionHeight": otio_tl_metadata[
                    "ayon.timeline.height"],
                "pixelAspect": otio_tl_metadata[
                    "ayon.timeline.pixelAspect"]
            })

    def get_marker_from_clip_index(self, otio_timeline, clip_index):
        """
        Return the clip and marker data from clip index.

        Args:
            otio_timeline (dict): otio timeline
            clip_index (str): The clip index.

        Returns:
            dict: otio clip object

        """
        for otio_clip in otio_timeline.find_clips():

            # Retrieve otioClip from parent context otioTimeline
            # See collect_current_project
            for marker in otio_clip.markers:

                if ayfapi.MARKER_NAME not in marker.name:
                    continue

                if marker.metadata.get("clip_index") == clip_index:
                    return otio_clip, marker

        return None, None

    def _get_head_tail(self, clip_data, otio_clip, handle_start, handle_end):
        # calculate head and tail with forward compatibility
        head = clip_data.get("segment_head")
        tail = clip_data.get("segment_tail")
        self.log.debug("__ head: `{}`".format(head))
        self.log.debug("__ tail: `{}`".format(tail))

        # HACK: it is here to serve for versions below 2021.1
        if not any([head, tail]):
            retimed_attributes = get_media_range_with_retimes(
                otio_clip, handle_start, handle_end)
            self.log.debug(
                ">> retimed_attributes: {}".format(retimed_attributes))

            # retimed head and tail
            head = int(retimed_attributes["handleStart"])
            tail = int(retimed_attributes["handleEnd"])

        return head, tail

    def _create_otio_time_range_from_timeline_item_data(self, clip_data):
        frame_start = int(clip_data["record_in"])
        frame_duration = int(clip_data["record_duration"])

        return flame_export.create_otio_time_range(
            frame_start, frame_duration, self.fps)
