# TODO:
#   - [x] abstracting clip processing part which is sharable for all
#   - [ ] Implement missing_media_link_export_preset_process method
#   - [ ] Implement thumbnail_preset_process method
#   - [ ] refactor additional_representation_export_process method
#
from __future__ import annotations

import os
import re
from pathlib import Path

import flame
import pyblish.api
from ayon_core.pipeline import publish
from ayon_core.pipeline.colorspace import get_remapped_colorspace_from_native
from ayon_core.pipeline.editorial import get_media_range_with_retimes
from ayon_flame import api as ayfapi
from ayon_flame.api import MediaInfoFile


class ExtractProductResources(
    publish.Extractor,
    publish.ColormanagedPyblishPluginMixin
):
    """Extractor for transcoding files from Flame clip
    """

    label = "Extract product resources"
    order = pyblish.api.ExtractorOrder
    families = ["clip"]
    hosts = ["flame"]

    settings_category = "flame"

    # hide publisher during exporting
    hide_ui_on_process = True

    # settings
    missing_media_link_export_preset: dict
    additional_representation_export: dict
    thumbnail_preset: dict

    def process(self, instance):
        # create staging dir path
        staging_dir = self.staging_dir(instance)

        # append staging dir for later cleanup
        instance.context.data["cleanupFullPaths"].append(staging_dir)

        clip_data = self.get_clip_data(instance)
        if not clip_data["clip_path"]:
            # render missing media and add `clip_data["clip_path"]`
            clip_data = self.missing_media_link_export_preset_process(
                instance, clip_data, staging_dir)

        self.thumbnail_preset_process(instance, clip_data, staging_dir)
        self.additional_representation_export_process(
            instance, clip_data, staging_dir)

    def get_clip_data(self, instance: pyblish.api.Instance) -> dict:
        """Extract and prepare all clip-related data for export processing.

        Args:
            instance (Instance): Instance object.

        Returns:
            Dict[str, Any]: A dictionary containing all extracted clip data
                with at least these keys:
                * `segment` (flame.Segment): The flame segment object.
                * `folder_path` (str): Path to the folder.
                * `segment_name` (str): Name of the segment.
                * `clip_path` (Optional[str]): Path to the clip
                    (None if not linked media).
                * `sequence_clip` (flame.Clip): The flame sequence clip object.
                * `s_track_name` (str): Parent track name of the segment.
                * `frame_start` (int): Configured workfile frame start.
                * `source_first_frame` (int): Media source first frame.
                * `clip_in` (int): Timeline in point of segment.
                * `clip_out` (int): Timeline out point of segment.
                * `retimed_data` (dict): Dictionary of retimed attributes.
                * `retimed_handle_start` (int): Retimed handle start value.
                * `retimed_handle_end` (int): Retimed handle end value.
                * `retimed_source_duration` (int): Retimed source duration.
                * `retimed_speed` (float): Retimed speed factor.
                * `handle_start` (int): Handle start value.
                * `handle_end` (int): Handle end value.
                * `handles` (int): Maximum of handle_start and handle_end.
                * `include_handles` (bool): Whether to include handles.
                * `retimed_handles` (bool): Whether handles are retimed.
                * `source_start_handles` (int): Source start with handles.
                * `source_end_handles` (int): Source end with handles.
                * `frame_start_handle` (int): Frame start with handles applied.
                * `repre_frame_start` (int): Representation frame start.
                * `source_duration_handles` (int): Source duration including
                    handles.
                * `version_frame_start` (int): Version data frame start.

        """
        # flame objects
        segment = instance.data["item"]
        folder_path = instance.data["folderPath"]
        segment_name = segment.name.get_value()
        # clip_path will be None if not linked media
        clip_path = instance.data["path"]
        sequence_clip = instance.context.data["flameSequence"]

        # segment's parent track name
        s_track_name = segment.parent.name.get_value()

        # get configured workfile frame start/end (handles excluded)
        frame_start = instance.data["frameStart"]
        # get media source first frame
        source_first_frame = instance.data["sourceFirstFrame"]

        self.log.debug("_ frame_start: %s", frame_start)
        self.log.debug("_ source_first_frame: %s", source_first_frame)

        # get timeline in/out of segment
        clip_in = instance.data["clipIn"]
        clip_out = instance.data["clipOut"]

        # get retimed attributres
        retimed_data = self._get_retimed_attributes(instance)

        # get individual keys
        retimed_handle_start = retimed_data["handle_start"]
        retimed_handle_end = retimed_data["handle_end"]
        retimed_source_duration = retimed_data["source_duration"]
        retimed_speed = retimed_data["speed"]

        # get handles value - take only the max from both
        handle_start = instance.data["handleStart"]
        handle_end = instance.data["handleEnd"]
        handles = max(handle_start, handle_end)
        include_handles = instance.data.get("includeHandles")
        retimed_handles = instance.data.get("retimedHandles")

        # get media source range with handles
        source_start_handles = instance.data["sourceStartH"]
        source_end_handles = instance.data["sourceEndH"]

        # retime if needed
        if retimed_speed != 1.0:
            if retimed_handles:
                # handles are retimed
                source_start_handles = (
                    instance.data["sourceStart"] - retimed_handle_start)
                source_end_handles = (
                    source_start_handles
                    + (retimed_source_duration - 1)
                    + retimed_handle_start
                    + retimed_handle_end
                )

            else:
                # handles are not retimed
                source_end_handles = (
                    source_start_handles
                    + (retimed_source_duration - 1)
                    + handle_start
                    + handle_end
                )

        # get frame range with handles for representation range
        frame_start_handle = frame_start - handle_start
        repre_frame_start = frame_start_handle
        if include_handles:
            if retimed_speed == 1.0 or not retimed_handles:
                frame_start_handle = frame_start
            else:
                frame_start_handle = (
                    frame_start - handle_start) + retimed_handle_start

        self.log.debug("_ frame_start_handle: %s", frame_start_handle)
        self.log.debug("_ repre_frame_start: %s", repre_frame_start)

        # calculate duration with handles
        source_duration_handles = (
            source_end_handles - source_start_handles) + 1

        self.log.debug("_ source_duration_handles: %s", source_duration_handles)

        if not instance.data.get("versionData"):
            instance.data["versionData"] = {}

        # set versiondata if any retime
        version_data = retimed_data.get("version_data")
        self.log.debug("_ version_data: %s", version_data)

        if version_data:
            instance.data["versionData"].update(version_data)

        # version data start frame
        version_frame_start = frame_start
        if include_handles:
            version_frame_start = frame_start_handle
        if retimed_speed != 1.0:
            if retimed_handles:
                instance.data["versionData"].update({
                    "frameStart": version_frame_start,
                    "frameEnd": (
                        (version_frame_start + source_duration_handles - 1)
                        - (retimed_handle_start + retimed_handle_end)
                    )
                })
            else:
                instance.data["versionData"].update({
                    "handleStart": handle_start,
                    "handleEnd": handle_end,
                    "frameStart": version_frame_start,
                    "frameEnd": (
                        (version_frame_start + source_duration_handles - 1)
                        - (handle_start + handle_end)
                    )
                })
        self.log.debug("_ version_data: {}".format(
            instance.data["versionData"]
        ))

        # Return all extracted data as a dictionary
        return {
            "segment": segment,
            "folder_path": folder_path,
            "segment_name": segment_name,
            "clip_path": clip_path,
            "sequence_clip": sequence_clip,
            "s_track_name": s_track_name,
            "frame_start": frame_start,
            "source_first_frame": source_first_frame,
            "clip_in": clip_in,
            "clip_out": clip_out,
            "retimed_data": retimed_data,
            "retimed_handle_start": retimed_handle_start,
            "retimed_handle_end": retimed_handle_end,
            "retimed_source_duration": retimed_source_duration,
            "retimed_speed": retimed_speed,
            "handle_start": handle_start,
            "handle_end": handle_end,
            "handles": handles,
            "include_handles": include_handles,
            "retimed_handles": retimed_handles,
            "source_start_handles": source_start_handles,
            "source_end_handles": source_end_handles,
            "frame_start_handle": frame_start_handle,
            "repre_frame_start": repre_frame_start,
            "source_duration_handles": source_duration_handles,
            "version_frame_start": version_frame_start,
        }

    def missing_media_link_export_preset_process(
            self, instance, clip_data, staging_dir) -> dict:

        unique_name = "missing_media_link"
        extension = self.missing_media_link_export_preset["ext"]

        # Process preset export
        export_dir_path, imageio_colorspace = self._process_preset_export(
            instance,
            self.missing_media_link_export_preset,
            clip_data,
            unique_name,
            staging_dir,
        )

        repre_staging_dir, repre_files, repr_name = (
            self._process_exported_files(
                export_dir_path,
                extension,
                unique_name
            )
        )
        # Extract only needed data from clip_data dictionary
        source_duration_handles = clip_data["source_duration_handles"]
        repre_frame_start = clip_data["repre_frame_start"]

        # create representation data
        representation_data = self._create_representation_data(
            repr_name=repr_name,
            repre_files=repre_files,
            extension=extension,
            repre_staging_dir=repre_staging_dir,
            repre_tags=[],
            preset_config=self.missing_media_link_export_preset,
            repre_frame_start=repre_frame_start,
            source_duration_handles=source_duration_handles,
            instance=instance,
            imageio_colorspace=imageio_colorspace,
        )

        instance.data["representations"].append(representation_data)

        clip_data["clip_path"] = repre_staging_dir / repre_files[0]

        return clip_data

    def thumbnail_preset_process(
            self, instance, clip_data, staging_dir):
        if (
            not self.thumbnail_preset["enabled"]
        ):
            self.log.debug("thumbnail_preset is set")
            return
        unique_name = "thumbnail"
        # Process preset export
        export_dir_path, imageio_colorspace = self._process_preset_export(
            instance,
            self.missing_media_link_export_preset,
            clip_data,
            unique_name,
            staging_dir,
        )

    def additional_representation_export_process(
            self, instance, clip_data, staging_dir):
        ad_repre_settings = self.additional_representation_export
        if not ad_repre_settings["keep_original_representation"]:
            # remove previeous representation if not needed
            instance.data["representations"] = []

        ad_repre_settings = self.additional_representation_export
        additional_export_presets: list[dict] = ad_repre_settings[
            "export_presets_mapping"]

        # Extract only needed data from clip_data dictionary
        clip_path = clip_data["clip_path"]
        source_duration_handles = clip_data["source_duration_handles"]
        repre_frame_start = clip_data["repre_frame_start"]

        # loop all preset names and
        for preset_config in additional_export_presets:
            unique_name = preset_config["name"]
            enabled = preset_config["enabled"]
            extension = preset_config["ext"]

            if not enabled:
                continue

            # skipping based on clip name regex filtering
            if self._should_skip(preset_config, clip_path, unique_name):
                continue

            # Process preset export
            export_dir_path, imageio_colorspace = self._process_preset_export(
                instance, preset_config, clip_data, unique_name, staging_dir
            )
            repre_staging_dir, repre_files, repr_name = (
                self._process_exported_files(
                    export_dir_path, extension, unique_name
                )
            )

            # get preset attributes for representation
            export_type = preset_config["export_type"]
            repre_tags = preset_config.get("representation_tags", [])

            # create representation data
            representation_data = self._create_representation_data(
                repr_name=repr_name,
                repre_files=repre_files,
                extension=extension,
                repre_staging_dir=repre_staging_dir,
                repre_tags=repre_tags,
                preset_config=preset_config,
                repre_frame_start=repre_frame_start,
                source_duration_handles=source_duration_handles,
                instance=instance,
                imageio_colorspace=imageio_colorspace,
            )

            instance.data["representations"].append(representation_data)

            # add review family if found in tags
            if "review" in repre_tags:
                instance.data["families"].append("review")

            self.log.info("Added representation: %s", representation_data)

            if export_type == "Sequence Publish":
                publish_clips = flame.find_by_name(
                    f"{exporting_clip.name.get_value()}_publish",
                    parent=exporting_clip.parent
                )
                for publish_clip in publish_clips:
                    flame.delete(publish_clip)
                # at the end remove the duplicated clip
                flame.delete(exporting_clip)

    def _get_retimed_attributes(self, instance):
        handle_start = instance.data["handleStart"]
        handle_end = instance.data["handleEnd"]

        # get basic variables
        otio_clip = instance.data["otioClip"]

        # get available range trimmed with processed retimes
        retimed_attributes = get_media_range_with_retimes(
            otio_clip, handle_start, handle_end)
        self.log.debug(
            ">> retimed_attributes: %s", retimed_attributes)

        r_media_in = int(retimed_attributes["mediaIn"])
        r_media_out = int(retimed_attributes["mediaOut"])
        version_data = retimed_attributes.get("versionData")

        return {
            "version_data": version_data,
            "handle_start": int(retimed_attributes["handleStart"]),
            "handle_end": int(retimed_attributes["handleEnd"]),
            "source_duration": (
                (r_media_out - r_media_in) + 1
            ),
            "speed": float(retimed_attributes["speed"])
        }

    def _process_preset_export(
        self,
        instance,
        preset_config,
        clip_data,
        unique_name,
        staging_dir
    ):
        """Process and export a single preset configuration.

        Args:
            instance: The publish instance
            preset_config: Configuration for the preset
            clip_data: Dictionary containing clip data
            unique_name: Unique name for the preset
            staging_dir: Staging directory path

        Returns:
            tuple: (export_dir_path, imageio_colorspace)

        Raises:
            ValueError: If the clip data is missing required keys
        """
        # Extract clip data
        clip_path = clip_data["clip_path"]
        sequence_clip = clip_data["sequence_clip"]
        segment_name = clip_data["segment_name"]
        s_track_name = clip_data["s_track_name"]
        clip_in = clip_data["clip_in"]
        clip_out = clip_data["clip_out"]
        handles = clip_data["handles"]
        source_start_handles = clip_data["source_start_handles"]
        source_first_frame = clip_data["source_first_frame"]
        source_duration_handles = clip_data["source_duration_handles"]
        folder_path = clip_data["folder_path"]
        repre_frame_start = clip_data["repre_frame_start"]

        modify_xml_data = {}

        # get all presets attributes
        extension = preset_config["ext"]
        preset_file = preset_config["xml_preset_file"]
        preset_dir = preset_config["xml_preset_dir"]
        export_type = preset_config["export_type"]
        parsed_comment_attrs = preset_config["parsed_comment_attrs"]

        self.log.info(
            "Processing `%s` as `%s` to `%s` type...", preset_file, export_type, extension
        )

        exporting_clip = None
        name_pattern_xml = f"<name>_{unique_name}."

        if export_type == "Sequence Publish":
            # change export clip to sequence
            exporting_clip = flame.duplicate(sequence_clip)

            # only keep visible layer where instance segment is child
            self.hide_others(
                exporting_clip, segment_name, s_track_name)

            # change name pattern
            name_pattern_xml = (
                f"<segment name>_<shot name>_{unique_name}.")

            # only for h264 with baked retime
            in_mark = clip_in
            out_mark = clip_out + 1
            modify_xml_data.update({
                "exportHandles": True,
                "nbHandles": handles
            })
        else:
            in_mark = (source_start_handles - source_first_frame) + 1
            out_mark = in_mark + source_duration_handles
            exporting_clip = self.import_clip(clip_path)
            exporting_clip.name.set_value(f"{folder_path}_{segment_name}")

        flame_colour = exporting_clip.get_colour_space()
        self.log.debug(flame_colour)
        context = instance.context
        host_name = context.data["hostName"]
        project_settings = context.data["project_settings"]
        host_imageio_settings = project_settings["flame"]["imageio"]
        imageio_colorspace = get_remapped_colorspace_from_native(
            flame_colour,
            host_name,
            host_imageio_settings,
        )
        self.log.debug(imageio_colorspace)
        # add xml tags modifications
        modify_xml_data.update({
            # enum position low start from 0
            "frameIndex": 0,
            "startFrame": repre_frame_start,
            "namePattern": name_pattern_xml
        })

        if parsed_comment_attrs:
            # add any xml overrides collected form segment.comment
            modify_xml_data.update(instance.data["xml_overrides"])

        self.log.debug("_ in_mark: %s", in_mark)
        self.log.debug("_ out_mark: %s", out_mark)

        export_kwargs = {}
        # validate xml preset file is filled
        if preset_file == "":
            raise ValueError(
                f"Check Settings for {unique_name} preset: "
                    "`XML preset file` is not filled"
            )

        # resolve xml preset dir if not filled
        if preset_dir == "":
            preset_dir = ayfapi.get_preset_path_by_xml_name(
                preset_file)

            if not preset_dir:
                raise ValueError(
                    f"Check Settings for {unique_name} preset: "
                        f"`XML preset file` {preset_file} is not found"
                )

        # create preset path
        preset_orig_xml_path = (Path(preset_dir) / preset_file).as_posix()

        # define kwargs based on preset type
        if "thumbnail" in unique_name:
            modify_xml_data.update({
                "video/posterFrame": True,
                "video/useFrameAsPoster": 1,
                "namePattern": "__thumbnail"
            })
            thumb_frame_number = int(in_mark + (
                (out_mark - in_mark + 1) / 2))

            self.log.debug("__ thumb_frame_number: %s", thumb_frame_number)

            export_kwargs["thumb_frame_number"] = thumb_frame_number
        else:
            export_kwargs.update({
                "in_mark": in_mark,
                "out_mark": out_mark
            })

        preset_path = ayfapi.modify_preset_file(
            preset_orig_xml_path, staging_dir, modify_xml_data)

        # get and make export dir paths
        export_dir_path = (Path(staging_dir) / unique_name).as_posix()
        Path(export_dir_path).mkdir(parents=True, exist_ok=True)

        # export
        ayfapi.export_clip(
            export_dir_path, exporting_clip, preset_path, **export_kwargs)

        return export_dir_path, imageio_colorspace

    def _process_exported_files(self, export_dir_path, extension, unique_name):
        """Process exported files and prepare representation data.

        Args:
            export_dir_path: Path to the export directory
            preset_config: Preset configuration dictionary
            unique_name: Unique name for the preset

        Returns:
            tuple: (repre_staging_dir, repre_files, repr_name, extension)

        Raises:
            ValueError: If export directory doesn't exist or contains no files
        """
        repre_staging_dir = export_dir_path
        export_dir_p = Path(export_dir_path)
        if not export_dir_p.exists():
            raise ValueError(
                f"Export directory does not exist: {export_dir_path}")

        rendered_files = list(export_dir_p.iterdir())

        if not rendered_files:
            raise ValueError(
                f"No files found in export directory: {export_dir_path}")

        # make sure no nested folders inside
        n_stage_dir, n_files = self._unfolds_nested_folders(
            export_dir_path, rendered_files, extension)

        # fix representation in case of nested folders
        if n_stage_dir:
            repre_staging_dir = n_stage_dir
        if n_files:
            rendered_files = n_files

        repr_name = unique_name
        # add files to representation but add
        # imagesequence as list
        if (
            # first check if path in files is not mov extension
            [
                f for f in rendered_files
                if f.suffix == ".mov"
            ]
            # then try if thumbnail is not in unique name
            or repr_name == "thumbnail"
        ):
            repre_files = rendered_files.pop().name
        else:
            repre_files = [f.name for f in rendered_files]

        # make sure only first segment is used if underscore in name
        # HACK: `ftrackreview_withLUT` will result only in `ftrackreview`
        if (
            "thumbnail" in unique_name
            or "ftrackreview" in unique_name
        ):
            self.log.debug("Unique name: %s", unique_name)
            repr_name = unique_name.split("_")[0]

        return repre_staging_dir, repre_files, repr_name

    def _create_representation_data(
        self,
        repr_name,
        repre_files,
        extension,
        repre_staging_dir,
        repre_tags,
        preset_config,
        repre_frame_start,
        source_duration_handles,
        instance,
        imageio_colorspace
    ):
        """Create representation data dictionary.

        Args:
            repr_name (str): Representation name
            repre_files (list): List of representation files
            extension (str): File extension
            repre_staging_dir (str): Staging directory path
            repre_tags (list): List of tags
            preset_config (dict): Preset configuration
            repre_frame_start (int): Start frame number
            source_duration_handles (int): Duration with handles
            instance: Pyblish instance
            imageio_colorspace (str): Colorspace name

        Returns:
            dict: Representation data dictionary
        """
        # create representation data
        representation_data = {
            "name": repr_name,
            "files": repre_files,
            "outputName": repr_name,
            "ext": extension,
            "stagingDir": repre_staging_dir,
            "tags": repre_tags,
            "load_to_batch_group": preset_config.get(
                "load_to_batch_group"),
            "batch_group_loader_name": preset_config.get(
                "batch_group_loader_name") or None
        }

        # add frame range
        representation_add_range = preset_config.get(
            "representation_add_range", False)
        if (
            representation_add_range
            and repre_frame_start is not None
            and source_duration_handles is not None
        ):
            representation_data.update({
                "frameStart": repre_frame_start,
                "frameEnd": (
                    repre_frame_start + source_duration_handles) - 1,
                "fps": instance.data["fps"]
            })

        self.set_representation_colorspace(
            representation_data,
            instance.context,
            colorspace=imageio_colorspace,
        )

        return representation_data

    def _should_skip(self, preset_config, clip_path, unique_name):
        # get activating attributes
        filter_path_regex = preset_config.get("filter_path_regex")

        self.log.info(
            "Preset `%s` with filter `%s`", unique_name, filter_path_regex
        )

        # exclude by regex filter if any
        if (
            filter_path_regex
            and not re.search(filter_path_regex, clip_path)
        ):
            return True
        return None

    def _unfolds_nested_folders(self, stage_dir, files_list, ext):
        """Unfolds nested folders

        Args:
            stage_dir (str): path string with directory
            files_list (list[Path]): list of file names
            ext (str): extension (jpg)[without dot]

        Raises:
            IOError: in case no files were collected form any directory

        Returns:
            str, list: new staging dir path, new list of file names
            or
            None, None: In case single file in `files_list`
        """
        # exclude single files which are having extension
        # the same as input ext attr
        if (
            # only one file in list
            len(files_list) == 1
            # file is having extension as input
            and ext in files_list[0].suffix
        ) or (
            # more then one file in list
            len(files_list) >= 1
            # extension is correct
            and ext in files_list[0].suffix
            # test file exists
            and (Path(stage_dir) / files_list[0].name).exists()
        ):
            return None, None

        new_stage_dir = None
        new_files_list: list[Path] = []
        for file in files_list:
            search_path = Path(stage_dir) / file.name
            if not search_path.is_dir():
                continue
            for root, _dirs, files in os.walk(search_path):
                for _file in files:
                    file_path = Path(_file)
                    _ext = file_path.suffix
                    if ext.lower() != _ext[1:].lower():
                        continue
                    new_file_p = Path(root) / file_path.name
                    new_files_list.append(new_file_p)
                    if not new_stage_dir:
                        new_stage_dir = root

        if not new_stage_dir:
            raise AssertionError(
                f"Files in `{files_list}` are not correct! Check `{stage_dir}`"
            )

        return new_stage_dir, new_files_list

    def hide_others(self, sequence_clip, segment_name, track_name):
        """Helper method used only if sequence clip is used

        Args:
            sequence_clip (flame.Clip): sequence clip
            segment_name (str): segment name
            track_name (str): track name
        """
        # create otio tracks and clips
        for ver in sequence_clip.versions:
            for track in ver.tracks:
                if len(track.segments) == 0 and track.hidden.get_value():
                    continue

                # hide tracks which are not parent track
                if track.name.get_value() != track_name:
                    track.hidden = True
                    continue

                # hidde all other segments
                for segment in track.segments:
                    if segment.name.get_value() != segment_name:
                        segment.hidden = True

    def import_clip(self, path):
        """Import clip from path
        """
        path_p = Path(path)
        dir_path = path_p.parent
        media_info = MediaInfoFile(path, logger=self.log)
        file_pattern = media_info.file_pattern
        self.log.debug("__ file_pattern: %s", file_pattern)

        # rejoin the pattern to dir path
        new_path = (dir_path / file_pattern).as_posix()

        clips = flame.import_clips(new_path)
        self.log.info("Clips [%s] imported from `%s`", clips, path)

        if not clips:
            self.log.warning("Path `%s` is not having any clips", path)
            return None
        if len(clips) > 1:
            self.log.warning(
                "Path `%s` is containing more that one clip", path
            )
        return clips[0]
