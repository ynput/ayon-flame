import os
import re
import shutil
from copy import deepcopy
from xml.etree import ElementTree as ET

import qargparse

from ayon_core.lib import Logger, StringTemplate
from ayon_core.pipeline.create import CreatorError
from ayon_core.pipeline import LoaderPlugin, HiddenCreator
from ayon_core.pipeline import Creator
from ayon_core.pipeline.colorspace import get_remapped_colorspace_to_native
from ayon_core.settings import get_current_project_settings

from . import lib as flib


log = Logger.get_logger(__name__)


class HiddenFlameCreator(HiddenCreator):
    """HiddenCreator class wrapper
    """
    settings_category = "flame"

    def collect_instances(self):
        pass

    def update_instances(self, update_list):
        pass

    def remove_instances(self, instances):
        pass


class FlameEditorialCreator(Creator):
    """Creator class wrapper
    """
    settings_category = "flame"

    def __init__(self, *args, **kwargs):
        super(Creator, self).__init__(*args, **kwargs)
        self.presets = get_current_project_settings()[
            "flame"]["create"].get(self.__class__.__name__, {})

    def create(self, product_name, instance_data, pre_create_data):
        """Prepare data for new instance creation.

        Args:
            product_name(str): Product name of created instance.
            instance_data(dict): Base data for instance.
            pre_create_data(dict): Data based on pre creation attributes.
                Those may affect how creator works.
        """
        # adding basic current context resolve objects
        self.project = flib.get_current_project()
        self.sequence = flib.get_current_sequence(flib.CTX.selection)

        selected = pre_create_data.get("use_selection", False)
        self.selected = flib.get_sequence_segments(
            self.sequence,
            selected=selected
        )


class FlameReelCreator(Creator):
    """Creator class wrapper
    """
    settings_category = "flame"

    def __init__(self, *args, **kwargs):
        super(Creator, self).__init__(*args, **kwargs)
        self.presets = get_current_project_settings()[
            "flame"]["create"].get(self.__class__.__name__, {})

    def create(self, product_name, instance_data, pre_create_data):
        """Prepare data for new instance creation.

        Args:
            product_name(str): Product name of created instance.
            instance_data(dict): Base data for instance.
            pre_create_data(dict): Data based on pre creation attributes.
                Those may affect how creator works.
        """
        # adding basic current context resolve objects
        self.project = flib.get_current_project()

        selected = pre_create_data.get("use_selection", False)
        self.selected = flib.get_clips_in_reels(
            self.project,
            selected=selected
        )

class PublishableClip:
    """
    Convert a segment to publishable instance

    Args:
        segment (flame.PySegment): flame api object
        kwargs (optional): additional data needed for rename=True (presets)

    Returns:
        flame.PySegment: flame api object
    """
    vertical_clip_match = {}
    vertical_clip_used = {}
    marker_data = {}
    types = {
        "shot": "shot",
        "folder": "folder",
        "episode": "episode",
        "sequence": "sequence",
        "track": "sequence",
    }

    # parents search pattern
    parents_search_pattern = r"\{([a-z]*?)\}"

    # default templates for non-ui use
    rename_default = False
    hierarchy_default = "{_folder_}/{_sequence_}/{_track_}"
    clip_name_default = "shot_{_trackIndex_:0>3}_{_clipIndex_:0>4}"
    review_source_default = None
    base_product_variant_default = "<track_name>"
    product_type_default = "plate"
    count_from_default = 10
    count_steps_default = 10
    vertical_sync_default = False
    driving_layer_default = ""
    index_from_segment_default = False
    use_shot_name_default = False
    include_handles_default = False
    retimed_handles_default = True
    retimed_framerange_default = True

    def __init__(self,
            segment,
            pre_create_data=None,
            data=None,
            product_type=None,
            rename_index=None,
            log=None,
        ):
        self.rename_index = rename_index
        self.product_type = product_type
        self.log = log
        self.pre_create_data = pre_create_data or {}

        # get main parent objects
        self.current_segment = segment
        sequence_name = flib.get_current_sequence([segment]).name.get_value()
        self.sequence_name = str(sequence_name).replace(" ", "_")
        self.clip_data = flib.get_segment_attributes(segment)

        # segment (clip) main attributes
        self.cs_name = self.clip_data["segment_name"]
        self.cs_index = int(self.clip_data["segment"])
        self.shot_name = self.clip_data["shot_name"]

        # get track name and index
        self.track_index = int(self.clip_data["track"])
        track_name = self.clip_data["track_name"]
        self.track_name = (
            # make sure no space and other special characters are in track name
            # default track name is `*`
            str(track_name)
            .replace(" ", "_")
            .replace("*", f"noname{self.track_index}")
        )

        # add publish attribute to marker data
        self.marker_data.update({"active": True})

        # adding input data if any
        if data:
            self.marker_data.update(data)

        # populate default data before we get other attributes
        self._populate_segment_default_data()

        # use all populated default data to create all important attributes
        self._populate_attributes()

        # create parents with correct types
        self._create_parents()

    @classmethod
    def restore_all_caches(cls):
        cls.vertical_clip_match = {}
        cls.vertical_clip_used = {}

    def convert(self):

        # solve segment data and add them to marker data
        self._convert_to_marker_data()

        # if track name is in review track name and also if driving track name
        # is not in review track name: skip tag creation
        if (self.track_name in self.reviewable_source) and (
                self.driving_layer not in self.reviewable_source):
            return

        # deal with clip name
        new_name = self.marker_data.pop("newClipName")
        hierarchy_filled = self.marker_data["hierarchy"]

        if self.rename and not self.use_shot_name:
            # rename segment
            self.current_segment.name = str(new_name)
            self.marker_data.update({
                "folderName": str(new_name),
                "folderPath": f"/{hierarchy_filled}/{new_name}"
            })

        elif self.use_shot_name:
            if not self.shot_name:
                raise CreatorError(
                    f"Shot name is not set on segment: {self.cs_name}")
            self.marker_data.update({
                "folderName": self.shot_name,
                "folderPath": f"/{hierarchy_filled}/{self.shot_name}",
                "hierarchyData": {
                    "shot": self.shot_name
                }
            })
        else:
            self.marker_data.update({
                "folderName": self.cs_name,
                "folderPath": f"/{hierarchy_filled}/{self.cs_name}",
                "hierarchyData": {
                    "shot": self.cs_name
                }
            })

        return self.current_segment

    def _populate_segment_default_data(self):
        """ Populate default formatting data from segment. """

        self.current_segment_default_data = {
            "_folder_": "shots",
            "_sequence_": self.sequence_name,
            "_track_": self.track_name,
            "_clip_": self.cs_name,
            "_trackIndex_": self.track_index,
            "_clipIndex_": self.cs_index
        }

    def _populate_attributes(self):
        """ Populate main object attributes. """
        # segment frame range and parent track name for vertical sync check
        self.clip_in = int(self.clip_data["record_in"])
        self.clip_out = int(self.clip_data["record_out"])

        # define ui inputs if non gui mode was used
        self.shot_num = self.cs_index
        self.log.debug(f"____ self.shot_num: {self.shot_num}")

        # Use pre-create data or default values if gui was not used
        self.rename = self.pre_create_data.get(
            "clipRename") or self.rename_default
        self.use_shot_name = self.pre_create_data.get(
            "useShotName") or self.use_shot_name_default
        self.clip_name = self.pre_create_data.get(
            "clipName") or self.clip_name_default
        self.hierarchy = self.pre_create_data.get(
            "hierarchy") or self.hierarchy_default
        self.hierarchy_data = self.pre_create_data.get(
            "hierarchyData") or self.current_segment_default_data.copy()
        self.index_from_segment = self.pre_create_data.get(
            "segmentIndex") or self.index_from_segment_default
        self.count_from = self.pre_create_data.get(
            "countFrom") or self.count_from_default
        self.count_steps = self.pre_create_data.get(
            "countSteps") or self.count_steps_default
        self.base_product_variant = self.pre_create_data.get(
            "clipVariant") or self.base_product_variant_default
        self.product_type = (
            self.pre_create_data.get("productType")
            or self.product_type_default
        )
        self.vertical_sync = self.pre_create_data.get(
            "vSyncOn") or self.vertical_sync_default
        self.driving_layer = self.pre_create_data.get(
            "vSyncTrack") or self.driving_layer_default
        self.review_source = self.pre_create_data.get(
            "reviewableSource") or self.review_source_default
        self.audio = self.pre_create_data.get("audio") or False
        self.include_handles = self.pre_create_data.get(
            "includeHandles") or self.include_handles_default
        self.retimed_handles = (
            self.pre_create_data.get("retimedHandles")
            or self.retimed_handles_default
        )
        self.retimed_framerange = (
            self.pre_create_data.get("retimedFramerange")
            or self.retimed_framerange_default
        )

        # build product name from layer name
        if self.base_product_variant == "<track_name>":
            self.variant = self.track_name
        else:
            self.variant = self.base_product_variant

        # create product for publishing
        self.product_name = (
            self.product_type + self.variant.capitalize()
        )

        self.hierarchy_data = {
            key: self.pre_create_data.get(key)
            for key in ["folder", "episode", "sequence", "track", "shot"]
        }

    def _replace_hash_to_expression(self, name, text):
        """ Replace hash with number in correct padding. """
        _spl = text.split("#")
        _len = (len(_spl) - 1)
        _repl = "{{{0}:0>{1}}}".format(name, _len)
        return text.replace(("#" * _len), _repl)

    def _convert_to_marker_data(self):
        """ Convert internal data to marker data.

        Populating the marker data into internal variable self.marker_data
        """
        # define vertical sync attributes
        hero_track = True
        self.reviewable_source = ""

        if (
            self.vertical_sync and
            self.track_name not in self.driving_layer
        ):
            # if it is not then define vertical sync as None
            hero_track = False

        # increasing steps by index of rename iteration
        if not self.index_from_segment:
            self.count_steps *= self.rename_index

        hierarchy_formatting_data = {}
        hierarchy_data = deepcopy(self.hierarchy_data)
        _data = self.current_segment_default_data.copy()

        if self.pre_create_data:

            # backward compatibility for reviewableSource (2024.12.02)
            if "reviewTrack" in self.pre_create_data:
                _value = self.marker_data.pop("reviewTrack")
                self.marker_data["reviewableSource"] = _value

            # driving layer is set as positive match
            if hero_track or self.vertical_sync:
                # mark review layer
                if self.review_source and (
                        self.review_source != self.review_source_default):
                    # if review layer is defined and not the same as default
                    self.reviewable_source  = self.review_source

                # shot num calculate
                if self.index_from_segment:
                    # use clip index from timeline
                    self.shot_num = self.count_steps * self.cs_index
                else:
                    if self.rename_index == 0:
                        self.shot_num = self.count_from
                    else:
                        self.shot_num = self.count_from + self.count_steps

            # clip name sequence number
            _data.update({"shot": self.shot_num})

            # solve # in test to pythonic expression
            for _k, _v in hierarchy_data.items():
                if "#" not in _v:
                    continue
                hierarchy_data[_k] = self._replace_hash_to_expression(_k, _v)

            # fill up pythonic expresisons in hierarchy data
            for k, _v in hierarchy_data.items():
                hierarchy_formatting_data[k] = str(_v).format(**_data)
        else:
            # if no gui mode then just pass default data
            hierarchy_formatting_data = hierarchy_data

        tag_instance_data = self._solve_tag_instance_data(
            hierarchy_formatting_data)

        tag_instance_data.update({"heroTrack": True})
        if hero_track and self.vertical_sync:
            self.vertical_clip_match.update({
                (self.clip_in, self.clip_out): tag_instance_data
            })

        if not hero_track and self.vertical_sync:
            # driving layer is set as negative match
            for (hero_in, hero_out), hero_data in self.vertical_clip_match.items():  # noqa
                """ Iterate over all clips in vertical sync match

                If clip frame range is outside of hero clip frame range
                then skip this clip and do not add to hierarchical shared
                metadata to them.
                """

                if self.clip_in < hero_in or self.clip_out > hero_out:
                    continue

                _distrib_data = deepcopy(hero_data)
                _distrib_data["heroTrack"] = False

                # form used clip unique key
                data_product_name = hero_data["productName"]
                new_clip_name = hero_data["newClipName"]

                # get used names list for duplicity check
                used_names_list = self.vertical_clip_used.setdefault(
                    f"{new_clip_name}{data_product_name}", []
                )
                self.log.debug(
                    f">> used_names_list: {used_names_list}"
                )
                clip_product_name = self.product_name
                variant = self.variant
                self.log.debug(
                    f">> clip_product_name: {clip_product_name}")

                # in case track name and product name is the same then add
                if self.variant == self.track_name:
                    clip_product_name = self.product_name

                # add track index in case duplicity of names in hero data
                # INFO: this is for case where hero clip product name
                #    is the same as current clip product name
                if clip_product_name in data_product_name:
                    clip_product_name = (
                        f"{clip_product_name}{self.track_index}")
                    variant = f"{variant}{self.track_index}"

                # in case track clip product name had been already used
                # then add product name with clip index
                if clip_product_name in used_names_list:
                    _clip_product_name = (
                        f"{clip_product_name}{self.cs_index}"
                    )
                    # just in case lets validate if new name is not used
                    # in case the track_index is the same as clip_index
                    if _clip_product_name in used_names_list:
                        _clip_product_name = (
                            f"{clip_product_name}"
                            f"{self.track_index}{self.cs_index}"
                        )
                    clip_product_name = _clip_product_name
                    variant = f"{variant}{self.cs_index}"

                self.log.debug(
                    f">> clip_product_name: {clip_product_name}")
                _distrib_data["productName"] = clip_product_name
                _distrib_data["variant"] = variant
                # assign data to return hierarchy data to tag
                tag_instance_data = _distrib_data

                # add used product name to used list to avoid duplicity
                used_names_list.append(clip_product_name)
                break

        # add data to return data dict
        self.marker_data.update(tag_instance_data)

        # add review track only to hero track
        if hero_track and self.reviewable_source:
            self.marker_data["reviewTrack"] = self.reviewable_source
        else:
            self.marker_data["reviewTrack"] = None

        # add only review related data if reviewable source is set
        if self.reviewable_source:
            review_switch = True
            reviewable_source = self.reviewable_source

            if self.vertical_sync and not hero_track:
                review_switch = False
                reviewable_source = False

            if review_switch:
                self.marker_data["review"] = True
            else:
                self.marker_data.pop("review", None)

            self.marker_data["reviewableSource"] = reviewable_source

    def _solve_tag_instance_data(self, hierarchy_formatting_data):
        """ Solve marker data from hierarchy data and templates. """
        # fill up clip name and hierarchy keys
        hierarchy_filled = self.hierarchy.format(**hierarchy_formatting_data)
        clip_name_filled = self.clip_name.format(**hierarchy_formatting_data)

        # remove shot from hierarchy data: is not needed anymore
        hierarchy_formatting_data.pop("shot")

        return {
            "newClipName": clip_name_filled,
            "hierarchy": hierarchy_filled,
            "parents": self.parents,
            "hierarchyData": hierarchy_formatting_data,
            "productName": self.product_name,
            "productType": self.product_type_default,
            "variant": self.variant,
        }

    def _convert_to_entity(self, src_type, template):
        """ Converting input key to key with type. """
        # convert to entity type
        folder_type = self.types.get(src_type, None)

        assert folder_type, "Missing folder type for `{}`".format(
            src_type
        )

        # first collect formatting data to use for formatting template
        formatting_data = {}
        for _k, _v in self.hierarchy_data.items():
            value = str(_v).format(
                **self.current_segment_default_data)
            formatting_data[_k] = value

        return {
            "folder_type": folder_type,
            "entity_name": template.format(
                **formatting_data
            )
        }

    def _create_parents(self):
        """ Create parents and return it in list. """
        self.parents = []

        pattern = re.compile(self.parents_search_pattern)

        par_split = [(pattern.findall(t).pop(), t)
                     for t in self.hierarchy.split("/")]

        for type, template in par_split:
            parent = self._convert_to_entity(type, template)
            self.parents.append(parent)


# Publishing plugin functions

# Loader plugin functions
class ClipLoader(LoaderPlugin):
    """A basic clip loader for Flame

    This will implement the basic behavior for a loader to inherit from that
    will containerize the reference and will implement the `remove` and
    `update` logic.

    """
    log = log

    options = [
        qargparse.Boolean(
            "handles",
            label="Set handles",
            default=0,
            help="Also set handles to clip as In/Out marks"
        )
    ]

    _mapping = None
    _host_settings = None

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

        print(">>> We have preset for {}".format(plugin_name))
        for option, value in plugin_settings.items():
            if option == "enabled" and value is False:
                print("  - is disabled by preset")
            elif option == "representations":
                continue
            else:
                print("  - setting `{}`: `{}`".format(option, value))
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
            str: native colorspace name defined in mapping or None
        """
        # TODO: rewrite to support only pipeline's remapping
        if not cls._host_settings:
            cls._host_settings = get_current_project_settings()["flame"]

        # [Deprecated] way of remapping
        if not cls._mapping:
            mapping = (
                cls._host_settings["imageio"]["profilesMapping"]["inputs"])
            cls._mapping = {
                input["ocioName"]: input["flameName"]
                for input in mapping
            }

        native_name = cls._mapping.get(input_colorspace)

        if not native_name:
            native_name = get_remapped_colorspace_to_native(
                input_colorspace, "flame", cls._host_settings["imageio"])

        return native_name


class OpenClipSolver(flib.MediaInfoFile):
    create_new_clip = False

    log = log

    def __init__(self, openclip_file_path, feed_data, logger=None):
        self.out_file = openclip_file_path

        # replace log if any
        if logger:
            self.log = logger

        # new feed variables:
        feed_path = feed_data.pop("path")

        # initialize parent class
        super(OpenClipSolver, self).__init__(
            feed_path,
            logger=logger
        )

        # get other metadata
        self.feed_version_name = feed_data["version"]
        self.feed_colorspace = feed_data.get("colorspace")
        self.log.debug("feed_version_name: {}".format(self.feed_version_name))

        # layer rename variables
        self.layer_rename_template = feed_data["layer_rename_template"]
        self.layer_rename_patterns = feed_data["layer_rename_patterns"]
        self.context_data = feed_data["context_data"]

        # derivate other feed variables
        self.feed_basename = os.path.basename(feed_path)
        self.feed_dir = os.path.dirname(feed_path)
        self.feed_ext = os.path.splitext(self.feed_basename)[1][1:].lower()
        self.log.debug("feed_ext: {}".format(self.feed_ext))
        self.log.debug("out_file: {}".format(self.out_file))
        if not self._is_valid_tmp_file(self.out_file):
            self.create_new_clip = True

    def _is_valid_tmp_file(self, file):
        # check if file exists
        if os.path.isfile(file):
            # test also if file is not empty
            with open(file) as f:
                lines = f.readlines()

            if len(lines) > 2:
                return True

            # file is probably corrupted
            os.remove(file)
            return False

    def make(self):

        if self.create_new_clip:
            # New openClip
            self._create_new_open_clip()
        else:
            self._update_open_clip()

    def _clear_handler(self, xml_object):
        for handler in xml_object.findall("./handler"):
            self.log.info("Handler found")
            xml_object.remove(handler)

    def _create_new_open_clip(self):
        self.log.info("Building new openClip")

        for tmp_xml_track in self.clip_data.iter("track"):
            # solve track (layer) name
            self._rename_track_name(tmp_xml_track)

            tmp_xml_feeds = tmp_xml_track.find('feeds')
            tmp_xml_feeds.set('currentVersion', self.feed_version_name)

            for tmp_feed in tmp_xml_track.iter("feed"):
                tmp_feed.set('vuid', self.feed_version_name)

                # add colorspace if any is set
                if self.feed_colorspace:
                    self._add_colorspace(tmp_feed, self.feed_colorspace)

                self._clear_handler(tmp_feed)

        tmp_xml_versions_obj = self.clip_data.find('versions')
        tmp_xml_versions_obj.set('currentVersion', self.feed_version_name)
        for xml_new_version in tmp_xml_versions_obj:
            xml_new_version.set('uid', self.feed_version_name)
            xml_new_version.set('type', 'version')

        self._clear_handler(self.clip_data)
        self.log.info("Adding feed version: {}".format(self.feed_basename))

        self.write_clip_data_to_file(self.out_file, self.clip_data)

    def _get_xml_track_obj_by_uid(self, xml_data, uid):
        # loop all tracks of input xml data
        for xml_track in xml_data.iter("track"):
            track_uid = xml_track.get("uid")
            self.log.debug(
                ">> track_uid:uid: {}:{}".format(track_uid, uid))

            # get matching uids
            if uid == track_uid:
                return xml_track

    def _rename_track_name(self, xml_track_data):
        layer_uid = xml_track_data.get("uid")
        name_obj = xml_track_data.find("name")
        layer_name = name_obj.text

        if (
            self.layer_rename_patterns
            and not any(
                re.search(lp_.lower(), layer_name.lower())
                for lp_ in self.layer_rename_patterns
            )
        ):
            return

        formatting_data = self._update_formatting_data(
            layerName=layer_name,
            layerUID=layer_uid
        )
        name_obj.text = StringTemplate(
            self.layer_rename_template
        ).format(formatting_data)

    def _update_formatting_data(self, **kwargs):
        """ Updating formatting data for layer rename

        Attributes:
            key=value (optional): will be included to formatting data
                                  as {key: value}
        Returns:
            dict: anatomy context data for formatting
        """
        self.log.debug(">> self.clip_data: {}".format(self.clip_data))
        clip_name_obj = self.clip_data.find("name")
        data = {
            "originalBasename": clip_name_obj.text
        }
        # include version context data
        data.update(self.context_data)
        # include input kwargs data
        data.update(kwargs)
        return data

    def _update_open_clip(self):
        self.log.info("Updating openClip ..")

        out_xml = ET.parse(self.out_file)
        out_xml = out_xml.getroot()

        self.log.debug(">> out_xml: {}".format(out_xml))
        # loop tmp tracks
        updated_any = False
        for tmp_xml_track in self.clip_data.iter("track"):
            # solve track (layer) name
            self._rename_track_name(tmp_xml_track)

            # get tmp track uid
            tmp_track_uid = tmp_xml_track.get("uid")
            self.log.debug(">> tmp_track_uid: {}".format(tmp_track_uid))

            # get out data track by uid
            out_track_element = self._get_xml_track_obj_by_uid(
                out_xml, tmp_track_uid)
            self.log.debug(
                ">> out_track_element: {}".format(out_track_element))

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
                tmp_xml_feed.set('vuid', self.feed_version_name)
                self._clear_handler(tmp_xml_feed)

                # update fps from MediaInfoFile class
                if self.fps is not None:
                    tmp_feed_fps_obj = tmp_xml_feed.find(
                        "startTimecode/rate")
                    tmp_feed_fps_obj.text = str(self.fps)

                # update start_frame from MediaInfoFile class
                if self.start_frame is not None:
                    tmp_feed_nb_ticks_obj = tmp_xml_feed.find(
                        "startTimecode/nbTicks")
                    tmp_feed_nb_ticks_obj.text = str(self.start_frame)

                # update drop_mode from MediaInfoFile class
                if self.drop_mode is not None:
                    tmp_feed_drop_mode_obj = tmp_xml_feed.find(
                        "startTimecode/dropMode")
                    tmp_feed_drop_mode_obj.text = str(self.drop_mode)

                # add colorspace if any is set
                if self.feed_colorspace is not None:
                    self._add_colorspace(tmp_xml_feed, self.feed_colorspace)

                # then append/update feed to correct track in output
                if out_track_element:
                    self.log.debug("updating track element ..")
                    # update already present track
                    out_feeds = out_track_element.find('feeds')
                    out_feeds.set('currentVersion', self.feed_version_name)
                    out_feeds.append(tmp_xml_feed)

                    self.log.info(
                        "Appending new feed: {}".format(
                            self.feed_version_name))
                else:
                    self.log.debug("adding new track element ..")
                    # create new track as it doesn't exist yet
                    # set current version to feeds on tmp
                    tmp_xml_feeds = tmp_xml_track.find('feeds')
                    tmp_xml_feeds.set('currentVersion', self.feed_version_name)
                    out_tracks = out_xml.find("tracks")
                    out_tracks.append(tmp_xml_track)

                updated_any = True

        if updated_any:
            # Append vUID to versions
            out_xml_versions_obj = out_xml.find('versions')
            out_xml_versions_obj.set(
                'currentVersion', self.feed_version_name)
            new_version_obj = ET.Element(
                "version", {"type": "version", "uid": self.feed_version_name})
            out_xml_versions_obj.insert(0, new_version_obj)

            self._clear_handler(out_xml)

            # fist create backup
            self._create_openclip_backup_file(self.out_file)

            self.log.info("Adding feed version: {}".format(
                self.feed_version_name))

            self.write_clip_data_to_file(self.out_file, out_xml)

            self.log.debug("OpenClip Updated: {}".format(self.out_file))

    def _feed_exists(self, xml_data, path):
        # loop all available feed paths and check if
        # the path is not already in file
        for src_path in xml_data.iter('path'):
            if path == src_path.text:
                self.log.warning(
                    "Not appending file as it already is in .clip file")
                return True

    def _create_openclip_backup_file(self, file):
        bck_file = "{}.bak".format(file)
        # if backup does not exist
        if not os.path.isfile(bck_file):
            shutil.copy2(file, bck_file)
        else:
            # in case it exists and is already multiplied
            created = False
            for _i in range(1, 99):
                bck_file = "{name}.bak.{idx:0>2}".format(
                    name=file,
                    idx=_i)
                # create numbered backup file
                if not os.path.isfile(bck_file):
                    shutil.copy2(file, bck_file)
                    created = True
                    break
            # in case numbered does not exists
            if not created:
                bck_file = "{}.bak.last".format(file)
                shutil.copy2(file, bck_file)

    def _add_colorspace(self, feed_obj, profile_name):
        feed_storage_obj = feed_obj.find("storageFormat")
        feed_clr_obj = feed_storage_obj.find("colourSpace")
        if feed_clr_obj is not None:
            feed_clr_obj = ET.Element(
                "colourSpace", {"type": "string"})
            feed_clr_obj.text = profile_name
            feed_storage_obj.append(feed_clr_obj)
