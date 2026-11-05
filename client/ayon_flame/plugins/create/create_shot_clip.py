import uuid
from copy import deepcopy

from ayon_core.pipeline.create import CreatorError, CreatedInstance

from ayon_editorial.create.mixins import (
    ClipCreatorMixin,
    ClipInstanceCreatorMixin,
    ShotInstanceCreatorMixin,
)
from ayon_editorial.shots.instances import link_parent_instance
from ayon_editorial.shots.vertical_sync import VerticalSync
from ayon_editorial.shots.hierarchy import ShotHierarchySolver

import ayon_flame.api as ayfapi
from ayon_flame.api import plugin, lib, pipeline

try:
    from ayon_core.pipeline.create import ParentFlags
except ImportError:
    # Parenting was added with 'https://github.com/ynput/ayon-core/pull/1395'
    ParentFlags = None

# Used as a key by the creators in order to
# retrieve the instances data into clip markers.
_CONTENT_ID = "flame_sub_products"


class _FlameInstanceCreator(plugin.HiddenFlameCreator):
    """Wrapper class for clip types products.
    """
    skip_discovery = True

    def _add_instance_to_context(self, instance):
        parent_id = instance.get("parent_instance_id")
        if parent_id is not None and ParentFlags is not None:
            instance.set_parent(
                parent_id,
                # Disable if a parent is disabled and delete if a parent
                #   is deleted
                ParentFlags.share_active | ParentFlags.parent_lifetime
            )
        super()._add_instance_to_context(instance)

    def create(self, instance_data):
        """Return a new CreateInstance for new shot from Flame.

        Args:
            instance_data (dict): global data from original instance

        Return:
            CreatedInstance: The created instance object for the new shot.

        """
        instance_data["newHierarchyIntegration"] = True

        product_type = instance_data.get("productType")
        if not product_type:
            product_type = self.product_base_type
        new_instance = CreatedInstance(
            product_base_type=self.product_base_type,
            product_type=product_type,
            product_name=instance_data["productName"],
            data=instance_data,
            creator=self,
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
                data=marker_data
            )


class FlameShotInstanceCreator(
    ShotInstanceCreatorMixin, _FlameInstanceCreator
):
    """Shot product type creator class"""
    host_name = "flame"
    identifier = "io.ayon.creators.flame.shot"
    product_base_type = "shot"
    product_type = product_base_type
    label = "Editorial Shot"


class _FlameInstanceClipCreatorBase(
    ClipInstanceCreatorMixin, _FlameInstanceCreator
):
    """ Base clip product creator.
    """
    host_name = "flame"

    def get_video_track_names(self):
        return get_current_video_track_names()


class EditorialPlateInstanceCreator(_FlameInstanceClipCreatorBase):
    """Plate product type creator class"""
    identifier = "io.ayon.creators.flame.plate"
    product_base_type = "plate"
    product_type = product_base_type
    label = "Editorial Plate"


class EditorialAudioInstanceCreator(_FlameInstanceClipCreatorBase):
    """Audio product type creator class"""
    identifier = "io.ayon.creators.flame.audio"
    product_base_type = "audio"
    product_type = product_base_type
    label = "Editorial Audio"


class CreateShotClip(ClipCreatorMixin, plugin.FlameEditorialCreator):
    """Publishable clip"""

    host_name = "flame"
    identifier = "io.ayon.creators.flame.clip"
    label = "Create Publishable Clip"
    product_base_type = "editorial"
    product_type = product_base_type
    icon = "film"
    defaults = ["Main"]

    detailed_description = """
Publishing clips/plate, audio for new shots to project
or updating already created from Flame. Publishing will create
OTIO file.
"""

    create_allow_thumbnail = False

    shot_instances = {}

    @property
    def creator_ids(self):
        return {
            "shot": FlameShotInstanceCreator.identifier,
            "plate": EditorialPlateInstanceCreator.identifier,
            "audio": EditorialAudioInstanceCreator.identifier,
        }

    def get_video_track_names(self):
        return get_current_video_track_names()

    def apply_settings(self, project_settings):
        super().apply_settings(project_settings)
        # Disable if not in timeline context.
        self.enabled = lib.CTX.context == "FlameMenuTimeline"

    def create(self, product_name, instance_data, pre_create_data):
        super().create(product_name, instance_data, pre_create_data)

        if len(self.selected) < 1:
            return

        self.log.debug(f"Selected: {self.selected}")

        options = self.prepare_pre_create_data(pre_create_data)

        audio_clips = [
            audio_track.selected_segments
            for audio_track in self.sequence.audio_tracks
        ]

        if not any(audio_clips) and options.get("export_audio"):
            raise CreatorError(
                "You must have audio in your active "
                "timeline in order to export audio."
            )

        instance_data = deepcopy(instance_data)
        instance_data.update(options)
        instance_data["task"] = None

        # hero (vertical sync) track segments go first
        v_sync_track = options.get("vSyncTrack", "")
        sorted_selected_segments = []
        unsorted_selected_segments = []
        for _segment in self.selected:
            if _segment.parent.name.get_value() in v_sync_track:
                sorted_selected_segments.append(_segment)
            else:
                unsorted_selected_segments.append(_segment)

        sorted_selected_segments.extend(unsorted_selected_segments)

        sequence_name = self.sequence.name.get_value()
        solver = ShotHierarchySolver(
            options,
            sequence_name,
            self.get_video_track_names(),
            VerticalSync(),
        )

        self.shot_instances = {}
        shot_creator_id = self.creator_ids["shot"]
        for idx, segment in enumerate(sorted_selected_segments):
            clip = plugin.clip_info_from_segment(segment, self.sequence)

            try:
                solution = solver.solve(clip, idx)
            except ValueError as exc:
                raise CreatorError(str(exc)) from exc
            if solution is None:
                # Ignore clips that only are a reviewable source
                continue

            if solution.new_clip_name:
                segment.name = str(solution.new_clip_name)

            self.log.info(
                f"Processing track item data: {segment} (index: {idx})"
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

            solution_data = deepcopy(instance_data)
            solution_data.update(solution.data)
            clip_data = self.make_clip_instances(
                clip, solution_data, options)

            folder_path = solution_data["folderPath"]
            shot_instances = self.shot_instances.setdefault(folder_path, {})
            clip_instances = {}
            for creator_id, sub_instance_data in clip_data.items():
                creator = self.create_context.creators[creator_id]
                if creator_id != shot_creator_id:
                    parent_data = shot_instances.get(shot_creator_id)
                    if parent_data is None:
                        raise CreatorError(
                            f"No shot instance for '{folder_path}', "
                            f"clip '{clip.name}' is not in the range of "
                            "a hero track clip."
                        )
                    link_parent_instance(sub_instance_data, parent_data)

                instance = creator.create(sub_instance_data)
                instance.transient_data["segment_item"] = segment

                stored = instance.data_to_store()
                shot_instances[creator_id] = stored
                clip_instances[creator_id] = stored

            pipeline.imprint(
                segment,
                data={
                    _CONTENT_ID: clip_instances,
                    "clip_index": clip.uid,
                }
            )

        self.shot_instances = {}

    def _create_and_add_instance(
        self, data, creator_id, segment
    ):
        """
        Args:
            data (dict): The data to re-recreate the instance from.
            creator_id (str): The creator id to use.
            segment (obj): The associated segment item.

        Returns:
            CreatedInstance: The newly created instance.

        """
        creator = self.create_context.creators[creator_id]
        instance = creator.create(data)
        instance.transient_data["segment_item"] = segment
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
        segment_data = lib.get_segment_attributes(segment)
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

        shot_creator_id = FlameShotInstanceCreator.identifier
        creator = self.create_context.creators[shot_creator_id]
        instance = creator.create(sub_instance_data)
        instance.transient_data["segment_item"] = segment
        clip_instances[shot_creator_id] = instance.data_to_store()
        parenting_data = instance

        # Create plate/audio instance
        sub_creators = [EditorialPlateInstanceCreator.identifier]
        if instance_data["audio"]:
            sub_creators.append(
                EditorialAudioInstanceCreator.identifier
            )

        for sub_creator_id in sub_creators:
            sub_instance_data = deepcopy(instance_data)
            creator = self.create_context.creators[sub_creator_id]
            sub_instance_data.update({
                "parent_instance_id": parenting_data["instance_id"],
                "label": (
                    f"{sub_instance_data['folderPath']} "
                    f"{creator.product_base_type}"
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

            instance = creator.create(sub_instance_data)
            instance.transient_data["segment_item"] = segment
            clip_instances[sub_creator_id] = instance.data_to_store()

        # Adjust clip tag to match new publisher
        pipeline.imprint(
            segment,
            data={
                _CONTENT_ID: clip_instances,
                "clip_index": clip_index,
            }
        )

    def collect_instances(self):
        """Collect all created instances from current timeline."""
        # get selection only of sequence clip segments
        create_settings = self.project_settings[
            "flame"]["create"]["CollectShotClip"]
        restrict_to_selection = create_settings[
            "collectSelectedInstance"]

        selection = lib.CTX.selection or []
        current_sequence = lib.get_current_sequence(selection)

        # only get selected segments if user selected any
        # and settings are enabled
        segments = lib.get_sequence_segments(
            current_sequence, selected=restrict_to_selection
        )

        if not segments:
            # get all segments if user didn't select any
            segments = lib.get_sequence_segments(current_sequence)

        for segment in segments:
            # attempt to get AYON tag data
            marker_data = lib.get_segment_data_marker(segment)
            if not marker_data:
                continue

            # Legacy instances handling
            if _CONTENT_ID not in marker_data:
                self._collect_legacy_instance(segment, marker_data)
                continue

            for creator_id, data in marker_data[_CONTENT_ID].items():
                self._create_and_add_instance(
                    data, creator_id, segment
                )

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


def get_current_video_track_names():
    """Get video track names of the current sequence, empty if none."""
    current_sequence = lib.get_current_sequence(lib.CTX.selection)
    if current_sequence is None:
        return []
    return get_video_track_names(current_sequence)
