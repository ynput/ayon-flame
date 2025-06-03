from copy import deepcopy
import uuid

import ayon_flame.api as ayfapi
from ayon_flame.api import plugin, lib, pipeline
from ayon_flame.otio import flame_export

from ayon_core.pipeline.create import CreatorError, CreatedInstance
from ayon_core.lib import BoolDef, EnumDef, TextDef, UILabelDef, NumberDef


# Used as a key by the creators in order to
# retrieve the instances data into clip markers.
_CONTENT_ID = "flame_sub_products"


# Shot attributes
CLIP_ATTR_DEFS = [
    EnumDef(
        "fps",
        items=[
            {"value": "from_selection", "label": "From selection"},
            {"value": 23.997, "label": "23.976"},
            {"value": 24, "label": "24"},
            {"value": 25, "label": "25"},
            {"value": 29.97, "label": "29.97"},
            {"value": 30, "label": "30"}
        ],
        label="FPS"
    ),
    NumberDef(
        "workfileFrameStart",
        default=1001,
        label="Workfile start frame"
    ),
    NumberDef(
        "handleStart",
        default=0,
        label="Handle start"
    ),
    NumberDef(
        "handleEnd",
        default=0,
        label="Handle end"
    ),
    NumberDef(
        "frameStart",
        default=0,
        label="Frame start",
        disabled=True,
    ),
    NumberDef(
        "frameEnd",
        default=0,
        label="Frame end",
        disabled=True,
    ),
    NumberDef(
        "clipIn",
        default=0,
        label="Clip in",
        disabled=True,
    ),
    NumberDef(
        "clipOut",
        default=0,
        label="Clip out",
        disabled=True,
    ),
    NumberDef(
        "clipDuration",
        default=0,
        label="Clip duration",
        disabled=True,
    ),
    NumberDef(
        "sourceIn",
        default=0,
        label="Media source in",
        disabled=True,
    ),
    NumberDef(
        "sourceOut",
        default=0,
        label="Media source out",
        disabled=True,
    ),
    BoolDef(
        "includeHandles",
        label="Include handles",
        default=False,
    ),
    BoolDef(
        "retimedHandles",
        label="Retimed handles",
        default=True,
    ),
    BoolDef(
        "retimedFramerange",
        label="Retimed framerange",
        default=True,
    ),
]


class _FlameInstanceCreator(plugin.HiddenFlameCreator):
    """Wrapper class for clip types products.
    """

    def create(self, instance_data, _):
        """Return a new CreateInstance for new shot from Flame.

        Args:
            instance_data (dict): global data from original instance

        Return:
            CreatedInstance: The created instance object for the new shot.
        """
        instance_data.update({
            "newHierarchyIntegration": True,
            # Backwards compatible (Deprecated since 24/06/06)
            "newAssetPublishing": True,
        })

        new_instance = CreatedInstance(
            self.product_type,
            instance_data["productName"],
            instance_data,
            self
        )
        self._add_instance_to_context(new_instance)
        new_instance.transient_data["has_promised_context"] = True
        return new_instance

    def update_instances(self, update_list):
        """Store changes of existing instances so they can be recollected.

        Args:
            update_list(List[UpdateData]): Gets list of tuples. Each item
                contain changed instance and it's changes.
        """
        for created_inst, _changes in update_list:
            segment_item = created_inst.transient_data["segment_item"]
            marker_data = ayfapi.get_segment_data_marker(segment_item)

            # Backwards compatible (Deprecated since 24/09/05)
            # ignore instance if no existing marker data
            if marker_data is None:
                continue

            try:
                instances_data = marker_data[_CONTENT_ID]

            # Backwards compatible (Deprecated since 24/09/05)
            except KeyError:
                marker_data[_CONTENT_ID] = {}
                instances_data = marker_data[_CONTENT_ID]

            instances_data[self.identifier] = created_inst.data_to_store()
            pipeline.imprint(
                segment_item,
                data=  {
                    _CONTENT_ID: instances_data,
                    "clip_index": marker_data["clip_index"],
                }
            )

    def remove_instances(self, instances):
        """Remove instance marker from track item.

        Args:
            instance(List[CreatedInstance]): Instance objects which should be
                removed.
        """
        for instance in instances:
            segment_item = instance.transient_data["segment_item"]
            marker_data = ayfapi.get_segment_data_marker(segment_item)

            instances_data = marker_data.get(_CONTENT_ID, {})
            instances_data.pop(self.identifier, None)
            self._remove_instance_from_context(instance)

            pipeline.imprint(
                segment_item,
                data=  {
                    _CONTENT_ID: instances_data,
                    "clip_index": marker_data["clip_index"],
                }
            )


class FlameShotInstanceCreator(_FlameInstanceCreator):
    """Shot product type creator class"""
    identifier = "io.ayon.creators.flame.shot"
    product_type = "shot"
    label = "Editorial Shot"

    def get_instance_attr_defs(self):
        instance_attributes = CLIP_ATTR_DEFS
        instance_attributes.append(
            BoolDef(
                "useSourceResolution",
                label="Set shot resolution from plate",
                tooltip="Is resolution taken from timeline or source?",
                default=False,
            )
        )
        return instance_attributes


class _FlameInstanceClipCreatorBase(_FlameInstanceCreator):
    """ Base clip product creator.
    """

    def register_callbacks(self):
        self.create_context.add_value_changed_callback(self._on_value_change)

    def _on_value_change(self, event):
        for item in event["changes"]:
            instance = item["instance"]
            if (
                instance is None
                or instance.creator_identifier != self.identifier
            ):
                continue

            changes = item["changes"].get("creator_attributes", {})
            if "review" not in changes:
                continue

            attr_defs = instance.creator_attributes.attr_defs
            review_value = changes["review"]
            reviewable_source = next(
                attr_def
                for attr_def in attr_defs
                if attr_def.key == "reviewableSource"
            )
            reviewable_source.enabled = review_value

            instance.set_create_attr_defs(attr_defs)

    def get_attr_defs_for_instance(self, instance):

        current_sequence = lib.get_current_sequence(lib.CTX.selection)
        if current_sequence is not None:
            gui_tracks = [
                {"value": tr_name, "label": f"Track: {tr_name}"}
                for tr_name in get_video_track_names(current_sequence)
            ]
        else:
            gui_tracks = []

        instance_attributes = [
            TextDef(
                "parentInstance",
                label="Linked to",
                disabled=True,
            )
        ]

        if self.product_type == "plate":
            current_review = instance.creator_attributes.get("review", False)
            instance_attributes.extend(
                [
                    BoolDef(
                        "review",
                        label="Review",
                        tooltip="Switch to reviewable instance",
                        default=False,
                    ),
                    EnumDef(
                        "reviewableSource",
                        label="Reviewable Source",
                        tooltip=("Selecting source for reviewable files."),
                        items=(
                            [
                                {
                                    "value": "clip_media",
                                    "label": "[ Clip's media ]",
                                },
                            ]
                            + gui_tracks
                        ),
                        disabled=not current_review,
                    ),
                ]
            )

        return instance_attributes


class EditorialPlateInstanceCreator(_FlameInstanceClipCreatorBase):
    """Plate product type creator class"""
    identifier = "io.ayon.creators.flame.plate"
    product_type = "plate"
    label = "Editorial Plate"

    def create(self, instance_data, _):
        """Return a new CreateInstance for new shot from Resolve.

        Args:
            instance_data (dict): global data from original instance

        Return:
            CreatedInstance: The created instance object for the new shot.
        """
        return super().create(instance_data, None)


class EditorialAudioInstanceCreator(_FlameInstanceClipCreatorBase):
    """Audio product type creator class"""
    identifier = "io.ayon.creators.flame.audio"
    product_type = "audio"
    label = "Editorial Audio"


class CreateShotClip(plugin.FlameCreator):
    """Publishable clip"""

    identifier = "io.ayon.creators.flame.clip"
    label = "Create Publishable Clip"
    product_type = "editorial"
    icon = "film"
    defaults = ["Main"]

    detailed_description = """
Publishing clips/plate, audio for new shots to project
or updating already created from Flame. Publishing will create
OTIO file.
"""

    create_allow_thumbnail = False

    shot_instances = {}

    def get_pre_create_attr_defs(self):

        def header_label(text):
            return f"<br><b>{text}</b>"

        tokens_help = """\nUsable tokens:
    {_clip_}: name of used clip
    {_track_}: name of parent track layer
    {_sequence_}: name of parent sequence (timeline)"""

        current_sequence = lib.get_current_sequence(lib.CTX.selection)
        if current_sequence is not None:
            gui_tracks = [
                {"value": tr_name, "label": f"Track: {tr_name}"}
                for tr_name in get_video_track_names(current_sequence)
            ]
        else:
            gui_tracks = []

        # Project settings might be applied to this creator via
        # the inherited `Creator.apply_settings`
        presets = self.presets

        return [

            BoolDef("use_selection",
                    label="Use only selected clip(s).",
                    tooltip=(
                        "When enabled it restricts create process "
                        "to selected clips."
                    ),
                    default=True),

            # renameHierarchy
            UILabelDef(
                label=header_label("Shot Hierarchy And Rename Settings")
            ),
            TextDef(
                "hierarchy",
                label="Shot Parent Hierarchy",
                tooltip="Parents folder for shot root folder, "
                        "Template filled with *Hierarchy Data* section",
                default=presets.get("hierarchy", "{folder}/{sequence}"),
            ),
            BoolDef(
                "useShotName",
                label="Use shot name",
                tooltip="Use name form Shot name clip attribute.",
                default=presets.get("useShotName", True),
            ),
            BoolDef(
                "clipRename",
                label="Rename clips",
                tooltip="Renaming selected clips on fly",
                default=presets.get("clipRename", False),
            ),
            TextDef(
                "clipName",
                label="Clip Name Template",
                tooltip="template for creating shot names, used for "
                        "renaming (use rename: on)",
                default=presets.get("clipName", "{sequence}{shot}"),
            ),
            BoolDef(
                "segmentIndex",
                label="Segment Index",
                tooltip="Take number from segment index",
                default=presets.get("segmentIndex", True),
            ),
            NumberDef(
                "countFrom",
                label="Count sequence from",
                tooltip="Set where the sequence number starts from",
                default=presets.get("countFrom", 10),
            ),
            NumberDef(
                "countSteps",
                label="Stepping number",
                tooltip="What number is adding every new step",
                default=presets.get("countSteps", 10),
            ),

            # hierarchyData
            UILabelDef(
                label=header_label("Shot Template Keywords")
            ),
            TextDef(
                "folder",
                label="{folder}",
                tooltip="Name of folder used for root of generated shots.\n"
                        f"{tokens_help}",
                default=presets.get("folder", "shots"),
            ),
            TextDef(
                "episode",
                label="{episode}",
                tooltip=f"Name of episode.\n{tokens_help}",
                default=presets.get("episode", "ep01"),
            ),
            TextDef(
                "sequence",
                label="{sequence}",
                tooltip=f"Name of sequence of shots.\n{tokens_help}",
                default=presets.get("sequence", "sq01"),
            ),
            TextDef(
                "track",
                label="{track}",
                tooltip=f"Name of timeline track.\n{tokens_help}",
                default=presets.get("track", "{_track_}"),
            ),
            TextDef(
                "shot",
                label="{shot}",
                tooltip="Name of shot. '#' is converted to padded number."
                        f"\n{tokens_help}",
                default=presets.get("shot", "sh###"),
            ),

            # verticalSync
            UILabelDef(
                label=header_label("Vertical Synchronization Of Attributes")
            ),
            BoolDef(
                "vSyncOn",
                label="Enable Vertical Sync",
                tooltip="Switch on if you want clips above "
                        "each other to share its attributes",
                default=presets.get("vSyncOn", True),
            ),
            EnumDef(
                "vSyncTrack",
                label="Hero track",
                tooltip="Select driving track name which should "
                        "be mastering all others",
                items=gui_tracks or ["<nothing to select>"],
            ),

            # publishSettings
            UILabelDef(
                label=header_label("Publish Settings")
            ),
            EnumDef(
                "clipVariant",
                label="Product Variant",
                tooltip="Chose variant which will be then used for "
                        "product name, if <track_name> "
                        "is selected, name of track layer will be used",
                items=['<track_name>', 'main', 'bg', 'fg', 'bg', 'animatic'],
            ),
            EnumDef(
                "productType",
                label="Product Type",
                tooltip="How the product will be used",
                items=['plate', 'take'],
            ),
            EnumDef(
                "reviewableSource",
                label="Reviewable Source",
                tooltip="Select source for reviewable files.",
                items=[
                    {"value": None, "label": "< none >"},
                    {"value": "clip_media", "label": "[ Clip's media ]"},
                ]
                + gui_tracks,
            ),
            BoolDef(
                "export_audio",
                label="Include audio",
                tooltip="Process subsets with corresponding audio",
                default=presets.get("export_audio", False),
            ),
            BoolDef(
                "sourceResolution",
                label="Source resolution",
                tooltip="Is resolution taken from timeline or source?",
                default=presets.get("sourceResolution", False),
            ),

            # shotAttr
            UILabelDef(
                label=header_label("Shot Attributes"),
            ),
            NumberDef(
                "workfileFrameStart",
                label="Workfiles Start Frame",
                tooltip="Set workfile starting frame number",
                default=presets.get("workfileFrameStart", 1001),
            ),
            NumberDef(
                "handleStart",
                label="Handle start (head)",
                tooltip="Handle at start of clip",
                default=presets.get("handleStart", 0),
            ),
            NumberDef(
                "handleEnd",
                label="Handle end (tail)",
                tooltip="Handle at end of clip",
                default=presets.get("handleEnd", 0),
            ),
            BoolDef(
                "includeHandles",
                label="Include handles",
                tooltip="Should the handles be included?",
                default=presets.get("includeHandles", True),
            ),
            BoolDef(
                "retimedHandles",
                label="Retimed handles",
                tooltip="Should the handles be retimed?",
                default=presets.get("retimedHandles", True),
            ),
            BoolDef(
                "retimedFramerange",
                label="Retimed framerange",
                tooltip="Should the framerange be retimed?",
                default=presets.get("retimedFramerange", True),
            ),
        ]

    def create(self, product_name, instance_data, pre_create_data):
        super().create(
            product_name,
            instance_data,
            pre_create_data)

        if len(self.selected) < 1:
            return

        self.log.info(self.selected)
        self.log.debug(f"Selected: {self.selected}")

        audio_clips = [
            audio_track.selected_segments
            for audio_track in self.sequence.audio_tracks
        ]

        if not any(audio_clips) and pre_create_data.get("export_audio"):
            raise CreatorError(
                "You must have audio in your active "
                "timeline in order to export audio."
            )

        instance_data.update(pre_create_data)
        instance_data["task"] = None

        # sort selected trackItems by
        v_sync_track = pre_create_data.get("vSyncTrack", "")

        # sort selected trackItems by
        sorted_selected_segments = []
        unsorted_selected_segments = []
        for _segment in self.selected:
            if _segment.parent.name.get_value() in v_sync_track:
                sorted_selected_segments.append(_segment)
            else:
                unsorted_selected_segments.append(_segment)

        sorted_selected_segments.extend(unsorted_selected_segments)

        # detect enabled creators for review, plate and audio
        shot_creator_id = "io.ayon.creators.flame.shot"
        plate_creator_id = "io.ayon.creators.flame.plate"
        audio_creator_id = "io.ayon.creators.flame.audio"
        all_creators = {
            shot_creator_id: True,
            plate_creator_id: True,
            audio_creator_id: True,
        }
        instances = []

        for idx, segment in enumerate(sorted_selected_segments):

            clip_index = str(uuid.uuid4())
            segment_instance_data = deepcopy(instance_data)
            segment_instance_data["clip_index"] = clip_index

            # convert track item to timeline media pool item
            publish_clip = ayfapi.PublishableClip(
                segment,
                log=self.log,
                pre_create_data=pre_create_data,
                data=segment_instance_data,
                product_type=self.product_type,
                rename_index=idx,
            )

            segment = publish_clip.convert()
            if segment is None:
                # Ignore input clips that do not convert into a track item
                # from `PublishableClip.convert`
                continue

            segment_instance_data.update(publish_clip.marker_data)
            self.log.info(
                "Processing track item data: {} (index: {})".format(
                    segment, idx)
            )

            # Delete any existing instances previously generated for the clip.
            prev_tag_data = lib.get_segment_data_marker(segment)
            if prev_tag_data:
                for creator_id, inst_data in prev_tag_data.get(
                        _CONTENT_ID, {}).items():
                    creator = self.create_context.creators[creator_id]
                    prev_instance = self.create_context.instances_by_id.get(
                        inst_data["instance_id"]
                    )
                    if prev_instance is not None:
                        creator.remove_instances([prev_instance])

            # Create new product(s) instances.
            clip_instances = {}
            # disable shot creator if heroTrack is not enabled
            all_creators[shot_creator_id] = segment_instance_data.get(
                "heroTrack", False)
            # disable audio creator if audio is not enabled
            all_creators[audio_creator_id] = (
                segment_instance_data.get("heroTrack", False) and
                pre_create_data.get("export_audio", False)
            )

            enabled_creators = tuple(
                cre for cre, enabled in all_creators.items() if enabled)
            clip_instances = {}
            shot_folder_path = segment_instance_data["folderPath"]
            shot_instances = self.shot_instances.setdefault(
                shot_folder_path, {})

            for creator_id in enabled_creators:
                creator = self.create_context.creators[creator_id]
                sub_instance_data = deepcopy(segment_instance_data)
                creator_attributes = sub_instance_data.setdefault(
                    "creator_attributes", {}
                )
                shot_folder_path = sub_instance_data["folderPath"]

                # Shot creation
                if creator_id == shot_creator_id:
                    segment_data = flame_export.get_segment_attributes(segment)
                    segment_duration = int(segment_data["record_duration"])
                    workfileFrameStart = sub_instance_data[
                        "workfileFrameStart"]
                    sub_instance_data.update(
                        {
                            "variant": "main",
                            "productType": "shot",
                            "productName": "shotMain",
                            "creator_attributes": {
                                "workfileFrameStart": workfileFrameStart,
                                "handleStart": sub_instance_data[
                                    "handleStart"],
                                "handleEnd": sub_instance_data["handleEnd"],
                                "frameStart": workfileFrameStart,
                                "frameEnd": (
                                    workfileFrameStart + segment_duration),
                                "clipIn": int(segment_data["record_in"]),
                                "clipOut": int(segment_data["record_out"]),
                                "clipDuration": segment_duration,
                                "sourceIn": int(segment_data["source_in"]),
                                "sourceOut": int(segment_data["source_out"]),
                                "includeHandles": pre_create_data[
                                    "includeHandles"],
                                "retimedHandles": pre_create_data[
                                    "retimedHandles"],
                                "retimedFramerange": pre_create_data[
                                    "retimedFramerange"
                                ],
                                "useSourceResolution": sub_instance_data[
                                    "sourceResolution"],
                            },
                            "label": f"{shot_folder_path} shot",
                        }
                    )

                # Plate,
                # insert parent instance data to allow
                # metadata recollection as publish time.
                elif creator_id == plate_creator_id:
                    parenting_data = shot_instances[shot_creator_id]
                    sub_instance_data.update(
                        {
                            "parent_instance_id": parenting_data[
                                "instance_id"],
                            "label": (
                                f"{sub_instance_data['folderPath']} "
                                f"{sub_instance_data['productName']}"
                            ),
                        }
                    )
                    creator_attributes["parentInstance"] = parenting_data[
                        "label"]
                    if sub_instance_data.get("reviewableSource"):
                        creator_attributes.update(
                            {
                                "review": True,
                                "reviewableSource": sub_instance_data[
                                    "reviewableSource"
                                ],
                            }
                        )

                # Audio
                # insert parent instance data
                elif creator_id == audio_creator_id:
                    sub_instance_data["variant"] = "main"
                    sub_instance_data["productType"] = "audio"
                    sub_instance_data["productName"] = "audioMain"

                    parenting_data = shot_instances[shot_creator_id]
                    sub_instance_data.update(
                        {
                            "parent_instance_id": parenting_data[
                                "instance_id"],
                            "label": (
                                f"{sub_instance_data['folderPath']} "
                                f"{sub_instance_data['productName']}"
                            )
                        }
                    )
                    creator_attributes["parentInstance"] = parenting_data[
                        "label"]

                    if sub_instance_data.get("reviewableSource"):
                        creator_attributes["review"] = True

                instance = creator.create(sub_instance_data, None)
                instance.transient_data["segment_item"] = segment
                self._add_instance_to_context(instance)

                instance_data_to_store = instance.data_to_store()
                shot_instances[creator_id] = instance_data_to_store
                clip_instances[creator_id] = instance_data_to_store

            pipeline.imprint(
                segment,
                data={
                    _CONTENT_ID: clip_instances,
                    "clip_index": clip_index,
                }
            )
            instances.append(instance)

        self.shot_instances = {}
        ayfapi.PublishableClip.restore_all_caches()

        return instances

    def _create_and_add_instance(
            self, data, creator_id, segment, instances):
        """
        Args:
            data (dict): The data to re-recreate the instance from.
            creator_id (str): The creator id to use.
            segment (obj): The associated segment item.
            instances (list): Result instance container.

        Returns:
            CreatedInstance: The newly created instance.
        """
        creator = self.create_context.creators[creator_id]
        instance = creator.create(data, None)
        instance.transient_data["segment_item"] = segment
        self._add_instance_to_context(instance)
        instances.append(instance)
        return instance

    def _collect_legacy_instance(self, segment, marker_data):
        """ Create some instances from legacy marker data.

        Args:
            segment (object): The segment associated to the marker.
            marker_data (dict): The marker data.

        Returns:
            list. All of the created legacy instances.
        """
        instance_data = marker_data
        instance_data["task"] = None

        clip_index = str(uuid.uuid4())
        instance_data["clip_index"] = clip_index
        clip_instances = {}

        # Create parent shot instance.
        sub_instance_data = instance_data.copy()
        segment_data = flame_export.get_segment_attributes(segment)
        segment_duration = int(segment_data["record_duration"])
        workfileFrameStart = sub_instance_data["workfileFrameStart"]
        sub_instance_data.update({
            "creator_attributes": {
                "workfileFrameStart": workfileFrameStart,
                "handleStart": sub_instance_data["handleStart"],
                "handleEnd": sub_instance_data["handleEnd"],
                "frameStart": workfileFrameStart,
                "frameEnd": (
                    workfileFrameStart + segment_duration),
                "clipIn": int(segment_data["record_in"]),
                "clipOut": int(segment_data["record_out"]),
                "clipDuration": segment_duration,
                "sourceIn": int(segment_data["source_in"]),
                "sourceOut": int(segment_data["source_out"]),
                "includeHandles": sub_instance_data["includeHandles"],
                "retimedHandles": sub_instance_data["retimedHandles"],
                "retimedFramerange": sub_instance_data["retimedFramerange"],
                "useSourceResolution": sub_instance_data["sourceResolution"],
            },
            "label": (
                f"{sub_instance_data['folderPath']} shot"
            ),
        })

        shot_creator_id = "io.ayon.creators.flame.shot"
        creator = self.create_context.creators[shot_creator_id]
        instance = creator.create(sub_instance_data, None)
        instance.transient_data["segment_item"] = segment
        self._add_instance_to_context(instance)
        clip_instances[shot_creator_id] = instance.data_to_store()
        parenting_data = instance

        # Create plate/audio instance
        sub_creators = ["io.ayon.creators.flame.plate"]
        if instance_data["audio"]:
            sub_creators.append(
                "io.ayon.creators.flame.audio"
            )

        for sub_creator_id in sub_creators:
            sub_instance_data = deepcopy(instance_data)
            creator = self.create_context.creators[sub_creator_id]
            sub_instance_data.update({
                "parent_instance_id": parenting_data["instance_id"],
                "label": (
                    f"{sub_instance_data['folderPath']} "
                    f"{creator.product_type}"
                ),
                "creator_attributes": {
                    "parentInstance": parenting_data["label"],
                }
            })

            # add reviewable source to plate if shot has it
            if sub_instance_data.get("reviewableSource") != "< none >":
                sub_instance_data["creator_attributes"].update({
                    "reviewableSource": sub_instance_data[
                        "reviewTrack"],
                    "review": True,
                })

            instance = creator.create(sub_instance_data, None)
            instance.transient_data["segment_item"] = segment
            self._add_instance_to_context(instance)
            clip_instances[sub_creator_id] = instance.data_to_store()

        # Adjust clip tag to match new publisher
        pipeline.imprint(
            segment,
            data={
                _CONTENT_ID: clip_instances,
                "clip_index": clip_index,
            }
        )
        return clip_instances.values()

    def collect_instances(self):
        """Collect all created instances from current timeline."""
        current_sequence = lib.get_current_sequence(lib.CTX.selection)

        for segment in lib.get_sequence_segments(current_sequence):
            instances = []

            # attempt to get AYON tag data
            marker_data = lib.get_segment_data_marker(segment)
            if not marker_data:
                continue

            # Legacy instances handling
            if _CONTENT_ID not in marker_data:
                instances.extend(
                    self._collect_legacy_instance(segment, marker_data)
                )
                continue

            for creator_id, data in marker_data[_CONTENT_ID].items():
                self._create_and_add_instance(
                    data, creator_id, segment, instances)

        return instances

    def update_instances(self, update_list):
        """Never called, update is handled via _FlameInstanceCreator."""
        pass

    def remove_instances(self, instances):
        """Never called, update is handled via _FlameInstanceCreator."""
        pass


def get_video_track_names(sequence):
    """ Get video track names.

    Args:
        sequence (object): The sequence object.

    Returns:
        list. The track names.
    """
    track_names = []
    for ver in sequence.versions:
        for track in ver.tracks:
            track_names.append(track.name.get_value())

    return track_names
