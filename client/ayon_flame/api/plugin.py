from __future__ import annotations

import logging
import os
import re
import shutil
import uuid
from copy import deepcopy
from typing import Any, Optional
from xml.etree import ElementTree as ET

import ayon_api
import flame
from ayon_core.lib import BoolDef, Logger, StringTemplate
from ayon_core.lib.transcoding import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from ayon_core.pipeline import (
    Creator,
    HiddenCreator,
    LoaderPlugin,
)
from ayon_core.pipeline.colorspace import get_remapped_colorspace_to_native
from ayon_core.pipeline.context_tools import get_current_project_settings
from ayon_core.pipeline.load import LoadError

from ayon_editorial.shots.clip import ClipInfo

from . import lib as flib

log = Logger.get_logger(__name__)


class HiddenFlameCreator(HiddenCreator):
    """HiddenCreator class wrapper
    """
    skip_discovery = True
    settings_category = "flame"

    def collect_instances(self):
        pass

    def update_instances(self, update_list):
        pass

    def remove_instances(self, instances):
        pass


class FlameCreator(Creator):
    """Creator class wrapper
    """
    skip_discovery = True
    settings_category = "flame"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = flib.get_current_project()

    def create(self, product_name, instance_data, pre_create_data):
        """Prepare data for new instance creation.

        Args:
            product_name(str): Product name of created instance.
            instance_data(dict): Base data for instance.
            pre_create_data(dict): Data based on pre creation attributes.
                Those may affect how creator works.
        """
        instance_data["flame_context"] = flib.CTX.context
        selected = pre_create_data.get("use_selection", False)
        self.selected = flib.get_clips_in_reels(
            self.project,
            selected=selected
        )


class FlameEditorialCreator(FlameCreator):
    """Creator class wrapper for Editorial usage.
    """
    skip_discovery = True

    def create(self, product_name, instance_data, pre_create_data):
        """Prepare data for new instance creation.

        Args:
            product_name(str): Product name of created instance.
            instance_data(dict): Base data for instance.
            pre_create_data(dict): Data based on pre creation attributes.
                Those may affect how creator works.
        """
        super().create(product_name, instance_data, pre_create_data)
        self.sequence = flib.get_current_sequence(flib.CTX.selection)
        selected = pre_create_data.get("use_selection", False)
        self.selected = flib.get_sequence_segments(
            self.sequence,
            selected=selected,
        )


def clip_info_from_segment(segment, sequence) -> ClipInfo:
    """Read a Flame segment into the plain `ClipInfo` of ayon-editorial.

    Args:
        segment (flame.PySegment): The segment.
        sequence (flame.PySequence): The sequence the segment is on.

    Returns:
        ClipInfo: `uid` is a new unique clip index, to be stored in the
            segment marker as `clip_index`.
    """
    clip_data = flib.get_segment_attributes(segment)
    track_index = int(clip_data["track"])
    return ClipInfo(
        uid=str(uuid.uuid4()),
        name=clip_data["segment_name"],
        index=int(clip_data["segment"]),
        track_name=str(clip_data["track_name"]),
        track_index=track_index,
        sequence_name=str(sequence.name.get_value()),
        timeline_in=int(clip_data["record_in"]),
        timeline_out=int(clip_data["record_out"]),
        source_in=clip_data["source_in"],
        source_out=clip_data["source_out"],
        shot_name=clip_data.get("shot_name") or "",
    )


# Loader plugin functions
class ClipLoader(LoaderPlugin):
    """A basic clip loader for Flame leveraging native OpenClip API.
    """
    log = log

    product_base_types = {
        "render2d", "source", "plate", "render", "review"
    }
    representations = {"*"}
    extensions = set(
        ext.lstrip(".") for ext in IMAGE_EXTENSIONS.union(VIDEO_EXTENSIONS)
    )

    options = [
        BoolDef(
            "handles",
            label="Set handles",
            default=False,
            tooltip="Also set handles to clip as In/Out marks"
        )
    ]

    @classmethod
    def apply_settings(cls, project_settings):

        plugin_type_settings = (
            project_settings
            .get("flame", {})
            .get("load", {})
        )

        if not plugin_type_settings:
            return

        plugin_name = cls.__name__

        plugin_settings = None
        # Look for plugin settings in host specific settings
        if plugin_name in plugin_type_settings:
            plugin_settings = plugin_type_settings[plugin_name]

        if not plugin_settings:
            return

        log.debug(">>> We have preset for {}".format(plugin_name))
        for option, value in plugin_settings.items():
            if option == "enabled" and value is False:
                log.debug("  - is disabled by preset")
            elif option == "representations":
                continue
            else:
                log.debug("  - setting `{}`: `{}`".format(option, value))
            setattr(cls, option, value)

    def get_colorspace(self, context):
        """Get colorspace name

        Look either to version data or representation data.

        Args:
            context (dict): version context data

        Returns:
            str: colorspace name or None
        """
        version_entity = context["version"]
        version_attributes = version_entity["attrib"]
        colorspace = version_attributes.get("colorSpace")

        if (
            not colorspace
            or colorspace == "Unknown"
        ):
            colorspace = context["representation"]["data"].get(
                "colorspace")

        return colorspace

    @classmethod
    def get_native_colorspace(cls, input_colorspace):
        """Return native colorspace name.

        Args:
            input_colorspace (str | None): colorspace name

        Returns:
            str: native colorspace name defined in remapping or None
        """
        imageio_settings = get_current_project_settings()["flame"]["imageio"]
        return get_remapped_colorspace_to_native(
            input_colorspace,
            "flame",
            imageio_settings
        )

    def _get_clip_name_format_data(self, context, _) -> dict[str, str]:
        """ Get formatting data for the clip name template.
        """
        format_data = deepcopy(context["representation"]["context"])
        folder_entity = context["folder"]
        product_entity = context["product"]
        format_data.update({
            "asset": folder_entity["name"],
            "folder": {
                "name": folder_entity["name"],
            },
            "subset": product_entity["name"],
            "family": product_entity["productType"],
            "product": {
                "name": product_entity["name"],
                "type": product_entity["productType"],
                "basetype": product_entity["productBaseType"],
            }
        })

        if not format_data.get("output"):
            format_data["output"] = format_data["representation"]

        return format_data

    def load(self, context, name, namespace, options):
        """
        From a specific clip representation, load it with all of
        its versions, connecting to Flame native OpenClip version support.

        Args:
            context (dict): Context to update the container to.
            name (str): Name of the clip to load.
            namespace (str): Namespace of the clip to load.
            options (dict): Options for loading the clip.

        Raises:
            LoadError: If unsupported file type is encountered.
        """
        fproject = flame.project.current_project
        self.fpd = fproject.current_workspace.desktop

        # Build clip name from current clip,
        # using settings template and representation context.
        clip_name = StringTemplate(self.clip_name_template).format(
            self._get_clip_name_format_data(context, options)
        )

        # Flame OpenClip is a file-based format,
        # prepare clip file in work directory.
        workfile_dir = os.environ["AYON_WORKDIR"]
        openclip_dir = os.path.join(workfile_dir, clip_name)
        openclip_path = os.path.join(
            openclip_dir, clip_name + ".clip"
        )
        os.makedirs(openclip_dir, exist_ok=True)

        # Find all versions for the clip.
        project_name = context["project"]["name"]
        product_id =  context["version"]["productId"]
        all_versions = list(
            ayon_api.get_versions(
                project_name,
                product_ids=[product_id],
            )
        )

        # Find all representations per version.
        repres_by_version_id = {}
        for repre_entity in ayon_api.get_representations(
             project_name,
             representation_names={context["representation"]["name"]},
             version_ids=[version["id"] for version in all_versions],
         ):
             repre_version_id = repre_entity["versionId"]
             repres_by_version_id[repre_version_id] = repre_entity

        if not repres_by_version_id:
            raise RuntimeError(
                "Could not find any representations named '{}' for product "
                "'{}' in project '{}' while preparing OpenClip feeds. "
                "Current version id: '{}'. Checked {} version(s).".format(
                    context["representation"]["name"],
                    product_id,
                    project_name,
                    context["version"]["id"],
                    len(all_versions),
                )
            )
        # Prepare OpenClip object.
        clip_solver = OpenClipSolver(
            openclip_path,
            self.layer_rename_patterns
        )

        # Resolve each version as new OpenClip feed.
        for version_id, representation in repres_by_version_id.items():
            version = next(v for v in all_versions if v["id"] == version_id)
            version_context = deepcopy(context)
            version_context["version"] = version
            version_context["representation"] = representation
            version_name = version["name"]

            # in case output is not in context replace key to representation
            layer_rename_template = self.layer_rename_template
            if not representation["context"].get("output"):
                layer_rename_template = self.layer_rename_template.replace(
                    "output", "representation"
                )

            # Gather colorspace from incoming version data.
            colorspace = self.get_colorspace(version_context)
            # If Flame < 2026, convert incoming OCIO colorspace
            # to syncolor using settings remapping.
            if int(flame.get_version_major()) < 2026:
                colorspace = self.get_native_colorspace(colorspace)

            # prepare clip data from context ad send it to openClipLoader
            path = self.filepath_from_context(version_context)

            try:
                clip_solver.add_feed(
                    path,
                    version_name,
                    colorspace,
                    representation["context"],
                    layer_rename_template,
                )
            except RuntimeError as exc:
                msg = (
                    "Unsupported Input: "
                    f"Flame does not support incoming media path {path}"
                )
                raise LoadError(msg) from exc



        version_entity = context["version"]
        clip_solver.set_current_version(
            f"v{version_entity['version']:03}"
        )
        clip_solver.write()

        # prepare Reel group in actual desktop
        opc = self._get_clip(clip_name, openclip_path)
        opc.name = clip_name

        return opc

    def _get_clip(self, name, clip_path):
        reel = self._get_reel()
        # with maintained openclip as opc
        for cl in reel.clips:
            if cl.name.get_value().startswith(name):
                return cl

        created_clips = flame.import_clips(str(clip_path), reel)
        return created_clips.pop()

    def _get_reel(self):
        """ Retrieve/Create expected reel for current clip.
        """
        raise NotImplementedError(
            "To be implemented by public loader subclass."
        )

    def update(self, container, context):
        """ AYON native version management.
        """
        raise NotImplementedError(
            "Version management rely on Flame "
            "native implementation through OpenClip."
        )

    def remove(self, container):
        """ AYON native version management.
        """
        raise NotImplementedError(
            "Version management rely on Flame "
            "native implementation through OpenClip."
        )


class OpenClipSolver:

    def __init__(
        self,
        openclip_file_path: str,
        layer_rename_patterns: str,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.out_file = openclip_file_path
        # layer rename variables
        self.layer_rename_patterns = layer_rename_patterns

        # replace log if any
        self.log = logger if logger else log
        self.out_clip_data = None
        if self._is_valid_tmp_file(self.out_file):
            self.out_clip_data = ET.parse(self.out_file).getroot()

    def _is_valid_tmp_file(self, file):
        # check if file exists
        if os.path.isfile(file):
            # test also if file is not empty
            with open(file) as f:
                lines = sum(1 for _ in f)

            if lines > 2:
                return True

            # file is probably corrupted
            os.remove(file)
            return False

    def add_feed(
        self,
        path: str,
        version_name: str,
        colorspace: Optional[str],
        context_data: dict[str, Any],
        layer_rename_template: str,
    ) -> None:
        try:
            clip = flib.MediaInfoFile(path, self.log)
        except ET.ParseError as error:
            self.log.error(f"Error adding feed: {error}")
            raise RuntimeError(
                f"Unsupported input media: {path}"
            ) from error

        if self.out_clip_data is None:
            self.out_clip_data = clip.clip_data
            self._create_new_open_clip(
                clip.clip_data,
                version_name,
                colorspace,
                context_data,
                layer_rename_template,
            )
            self.out_clip_data.find("name").text = os.path.basename(
                self.out_file
            )
        else:
            self._update_open_clip(
                clip,
                version_name,
                colorspace,
                context_data,
                layer_rename_template,
            )

    def _clear_handler(self, xml_object):
        for handler in xml_object.findall("./handler"):
            self.log.info("Handler found")
            xml_object.remove(handler)

    def _create_new_open_clip(
        self,
        clip_data: ET.Element,
        feed_version_name: str,
        feed_colorspace: Optional[str],
        context_data: dict[str, Any],
        layer_rename_template: str,
    ) -> None:
        self.log.info("Building new openClip")

        for tmp_xml_track in clip_data.iter("track"):
            # solve track (layer) name
            self._rename_track_name(
                tmp_xml_track,
                clip_data.find("name").text,
                context_data,
                layer_rename_template,
            )

            tmp_xml_feeds = tmp_xml_track.find('feeds')
            tmp_xml_feeds.set('currentVersion', feed_version_name)

            for tmp_feed in tmp_xml_track.iter("feed"):
                tmp_feed.set('vuid', feed_version_name)
                tmp_feed.set('uid', feed_version_name)

                # add colorspace if any is set
                if feed_colorspace:
                    self._add_colorspace(tmp_feed, feed_colorspace)

                self._clear_handler(tmp_feed)

        tmp_xml_versions_obj = clip_data.find('versions')
        tmp_xml_versions_obj.set('currentVersion', feed_version_name)
        for xml_new_version in tmp_xml_versions_obj:
            xml_new_version.set('uid', feed_version_name)

        self._clear_handler(clip_data)
        self.log.info("Adding feed version: {}".format(feed_version_name))

    def _get_xml_track_obj_by_uid(self, xml_data, uid):
        # loop all tracks of input xml data
        for xml_track in xml_data.iter("track"):
            track_uid = xml_track.get("uid")
            self.log.debug(
                ">> track_uid:uid: {}:{}".format(track_uid, uid))

            # get matching uids
            if uid == track_uid:
                return xml_track

    def _rename_track_name(
        self,
        xml_track_data: ET.Element,
        basename: str,
        context_data: dict[str, Any],
        layer_rename_template: str,
    ) -> None:
        layer_uid = xml_track_data.get("uid")
        name_obj = (
            xml_track_data.find("name") or xml_track_data.find("sourceName")
        )
        layer_name = name_obj.text if name_obj else None

        if (
            self.layer_rename_patterns
            and layer_name
            and not any(
                re.search(lp_.lower(), layer_name.lower())
                for lp_ in self.layer_rename_patterns
            )
        ):
            return

        formatting_data = dict(
            layerName=layer_name,
            layerUID=layer_uid,
            originalBasename=basename,
        )
        formatting_data.update(context_data)
        name_obj.text = StringTemplate(
            layer_rename_template
        ).format(formatting_data)

    def _update_open_clip(
        self,
        clip: flib.MediaInfoFile,
        feed_version_name: str,
        feed_colorspace: Optional[str],
        context_data: dict[str, Any],
        layer_rename_template: str,
    ) -> None:
        self.log.info("Updating openClip ..")
        clip_data = clip.clip_data

        out_xml_versions_obj = self.out_clip_data.find('versions')

        # loop tmp tracks
        for tmp_xml_track in clip_data.iter("track"):
            # solve track (layer) name
            self._rename_track_name(
                tmp_xml_track,
                clip_data.find("name").text,
                context_data,
                layer_rename_template,
            )

            # get tmp track uid
            tmp_track_uid = tmp_xml_track.get("uid")
            self.log.debug(">> tmp_track_uid: {}".format(tmp_track_uid))

            # get out data track by uid
            out_track_element = self._get_xml_track_obj_by_uid(
                self.out_clip_data, tmp_track_uid)
            self.log.debug(
                ">> out_track_element: {}".format(out_track_element))

            feeds = []
            # loop tmp feeds
            for tmp_xml_feed in tmp_xml_track.iter("feed"):
                new_path_obj = tmp_xml_feed.find(
                    "spans/span/path")
                new_path = new_path_obj.text
                # check if feed path already exists in track's feeds
                if (
                    out_track_element is not None
                    and self._feed_exists(out_track_element, new_path)
                ):
                    continue

                # rename versions on feeds
                tmp_xml_feed.set('vuid', feed_version_name)
                tmp_xml_feed.set('uid', feed_version_name)
                self._clear_handler(tmp_xml_feed)

                # update fps from MediaInfoFile class
                if clip.fps is not None:
                    tmp_feed_fps_obj = tmp_xml_feed.find(
                        "startTimecode/rate")
                    fps = clip.fps
                    tmp_feed_fps_obj.text = (
                        str(int(fps)) if fps == int(fps) else str(fps)
                    )

                # update start_frame from MediaInfoFile class
                if clip.start_frame is not None:
                    tmp_feed_nb_ticks_obj = tmp_xml_feed.find(
                        "startTimecode/nbTicks")
                    tmp_feed_nb_ticks_obj.text = str(clip.start_frame)

                # update drop_mode from MediaInfoFile class
                if clip.drop_mode is not None:
                    tmp_feed_drop_mode_obj = tmp_xml_feed.find(
                        "startTimecode/dropMode")
                    tmp_feed_drop_mode_obj.text = str(clip.drop_mode)

                # add colorspace if any is set
                if feed_colorspace is not None:
                    self._add_colorspace(tmp_xml_feed, feed_colorspace)

                feeds.append(tmp_xml_feed)

                new_version_obj = ET.Element(
                    "version", {"uid": feed_version_name}
                )
                out_xml_versions_obj.append(new_version_obj)

                self.log.info(
                    f"Adding feed version: {feed_version_name}"
                )

            # then append/update feed to correct track in output
            if out_track_element:
                self.log.debug("updating track element ..")
                # update already present track
                out_feeds = out_track_element.find('feeds')
                out_feeds.extend(feeds)

            else:
                self.log.debug("adding new track element ..")
                # create new track as it doesn't exist yet
                # set current version to feeds on tmp
                out_tracks = self.out_clip_data.find("tracks")
                out_tracks.append(tmp_xml_track)

        # sort versions
        out_xml_versions_obj[:] = sorted(
            out_xml_versions_obj, key=lambda child: child.get("uid")
        )

    def set_current_version(self, version_name: str) -> None:
        if self.out_clip_data is None:
            raise ValueError(
                "Cannot set current version: No clip data available"
            )

        # Adjust current version in xml versions slot.
        out_xml_versions_obj = self.out_clip_data.find("versions")
        out_xml_versions_obj.set("currentVersion", version_name)

        # Adjust current version in xml feeds.
        for out_xml_track in self.out_clip_data.iter("track"):
            out_feeds = out_xml_track.find("feeds")
            for feed in out_feeds.iter("feed"):
                if feed.get("vuid") == version_name:
                    out_feeds.set("currentVersion", version_name)
                    break

    def write(self):
        # first create backup
        self._clear_handler(self.out_clip_data)
        self._create_openclip_backup_file(self.out_file)

        flib.MediaInfoFile.write_clip_data_to_file(
            self.out_file, self.out_clip_data
        )

        self.log.debug("OpenClip Updated: {}".format(self.out_file))

    def _feed_exists(self, xml_data, path):
        # loop all available feed paths and check if
        # the path is not already in file
        for src_path in xml_data.iter('path'):
            if path == src_path.text:
                self.log.warning(
                    "Not appending file as it already is in .clip file")
                return True
        return False

    def _create_openclip_backup_file(self, file):
        if not os.path.isfile(file):
            return
        bck_file = "{}.bak".format(file)
        # if backup does not exist
        if not os.path.isfile(bck_file):
            shutil.copy2(file, bck_file)
        else:
            # in case it exists and is already multiplied
            idx = 1
            while True:
                bck_file = f"{file}.bak.{idx:0>2}"
                # create numbered backup file
                if not os.path.isfile(bck_file):
                    shutil.copy2(file, bck_file)
                    break
                idx += 1

    def _add_colorspace(self, feed_obj, profile_name):
        feed_storage_obj = feed_obj.find("storageFormat")
        feed_clr_obj = feed_storage_obj.find("colourSpace")
        if feed_clr_obj is None:
            feed_clr_obj = ET.Element(
                "colourSpace", {"type": "string"})
            feed_storage_obj.append(feed_clr_obj)
        feed_clr_obj.text = profile_name
