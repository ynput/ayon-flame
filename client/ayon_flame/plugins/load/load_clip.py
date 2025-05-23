from copy import deepcopy
import os
import flame
from pprint import pformat
import ayon_flame.api as ayfapi
from ayon_core.lib import StringTemplate
from ayon_core.lib.transcoding import (
    VIDEO_EXTENSIONS,
    IMAGE_EXTENSIONS
)


class LoadClip(ayfapi.ClipLoader):
    """Load a product to timeline as clip

    Place clip to timeline on its asset origin timings collected
    during conforming to project
    """

    product_types = {"render2d", "source", "plate", "render", "review"}
    representations = {"*"}
    extensions = set(
        ext.lstrip(".") for ext in IMAGE_EXTENSIONS.union(VIDEO_EXTENSIONS)
    )

    label = "Load as clip"
    order = -10
    icon = "code-fork"
    color = "orange"

    # settings
    reel_group_name = "AYON_Reels"
    reel_name = "Loaded"
    clip_name_template = "{folder[name]}_{product[name]}<_{output}>"

    """ Anatomy keys from version context data and dynamically added:
        - {layerName} - original layer name token
        - {layerUID} - original layer UID token
        - {originalBasename} - original clip name taken from file
    """
    layer_rename_template = "{folder[name]}_{product[name]}<_{output}>"
    layer_rename_patterns = []

    def load(self, context, name, namespace, options):

        # get flame objects
        fproject = flame.project.current_project
        self.fpd = fproject.current_workspace.desktop

        # load clip to timeline and get main variables
        version_entity = context["version"]
        version_attributes = version_entity["attrib"]
        version_name = version_entity["version"]
        colorspace = self.get_colorspace(context)

        # in case output is not in context replace key to representation
        if not context["representation"]["context"].get("output"):
            self.clip_name_template = self.clip_name_template.replace(
                "output", "representation")
            self.layer_rename_template = self.layer_rename_template.replace(
                "output", "representation")

        formatting_data = deepcopy(context["representation"]["context"])
        clip_name = StringTemplate(self.clip_name_template).format(
            formatting_data)

        # convert colorspace with ocio to flame mapping
        # in imageio flame section
        colorspace = self.get_native_colorspace(colorspace)
        self.log.info("Loading with colorspace: `{}`".format(colorspace))

        # create workfile path
        workfile_dir = os.environ["AYON_WORKDIR"]
        openclip_dir = os.path.join(
            workfile_dir, clip_name
        )
        openclip_path = os.path.join(
            openclip_dir, clip_name + ".clip"
        )
        if not os.path.exists(openclip_dir):
            os.makedirs(openclip_dir)

        # prepare clip data from context ad send it to openClipLoader
        path = self.filepath_from_context(context)
        loading_context = {
            "path": path.replace("\\", "/"),
            "colorspace": colorspace,
            "version": "v{:0>3}".format(version_name),
            "layer_rename_template": self.layer_rename_template,
            "layer_rename_patterns": self.layer_rename_patterns,
            "context_data": formatting_data
        }
        self.log.debug(pformat(
            loading_context
        ))
        self.log.debug(openclip_path)

        # make AYON clip file
        ayfapi.OpenClipSolver(
            openclip_path, loading_context, logger=self.log).make()

        # prepare Reel group in actual desktop
        opc = self._get_clip(
            clip_name,
            openclip_path
        )

        # add additional metadata from the version to imprint basic
        # folder attributes
        add_keys = [
            "frameStart", "frameEnd", "source", "author",
            "fps", "handleStart", "handleEnd"
        ]

        # move all version data keys to tag data
        data_imprint = {
            key: version_attributes.get(key, str(None))
            for key in add_keys
        }

        # add variables related to version context
        data_imprint.update({
            "version": version_name,
            "colorspace": colorspace,
            "objectName": clip_name
        })

        # TODO: finish the containerisation
        # opc_segment = ayfapi.get_clip_segment(opc)

        # return ayfapi.containerise(
        #     opc_segment,
        #     name, namespace, context,
        #     self.__class__.__name__,
        #     data_imprint)

        return opc

    def _get_clip(self, name, clip_path):
        reel = self._get_reel()
        # with maintained openclip as opc
        matching_clip = [cl for cl in reel.clips
                         if cl.name.get_value() == name]
        if matching_clip:
            return matching_clip.pop()
        else:
            created_clips = flame.import_clips(str(clip_path), reel)
            return created_clips.pop()

    def _get_reel(self):

        matching_rgroup = [
            rg for rg in self.fpd.reel_groups
            if rg.name.get_value() == self.reel_group_name
        ]

        if not matching_rgroup:
            reel_group = self.fpd.create_reel_group(str(self.reel_group_name))
            for _r in reel_group.reels:
                if "reel" not in _r.name.get_value().lower():
                    continue
                self.log.debug("Removing: {}".format(_r.name))
                flame.delete(_r)
        else:
            reel_group = matching_rgroup.pop()

        matching_reel = [
            re for re in reel_group.reels
            if re.name.get_value() == self.reel_name
        ]

        if not matching_reel:
            reel_group = reel_group.create_reel(str(self.reel_name))
        else:
            reel_group = matching_reel.pop()

        return reel_group

    def _get_segment_from_clip(self, clip):
        # unwrapping segment from input clip
        pass

    # def switch(self, container, context):
    #     self.update(container, context)

    # def update(self, container, context):
    #     """ Updating previously loaded clips
    #     """
    #     # load clip to timeline and get main variables
    #     repre_entity = context['representation']
    #     name = container['name']
    #     namespace = container['namespace']
    #     track_item = phiero.get_track_items(
    #         track_item_name=namespace)
    #     version = io.find_one({
    #         "type": "version",
    #         "id": repre_entity["versionId"]
    #     })
    #     version_data = version.get("data", {})
    #     version_name = version.get("name", None)
    #     colorspace = version_data.get("colorSpace", None)
    #     object_name = "{}_{}".format(name, namespace)
    #     file = get_representation_path(repre_entity).replace("\\", "/")
    #     clip = track_item.source()

    #     # reconnect media to new path
    #     clip.reconnectMedia(file)

    #     # set colorspace
    #     if colorspace:
    #         clip.setSourceMediaColourTransform(colorspace)

    #     # add additional metadata from the version to imprint basic
    #     # folder attributes
    #     add_keys = [
    #         "frameStart", "frameEnd", "source", "author",
    #         "fps", "handleStart", "handleEnd"
    #     ]

    #     # move all version data keys to tag data
    #     data_imprint = {}
    #     for key in add_keys:
    #         data_imprint.update({
    #             key: version_data.get(key, str(None))
    #         })

    #     # add variables related to version context
    #     data_imprint.update({
    #         "representation": repre_entity["id"],
    #         "version": version_name,
    #         "colorspace": colorspace,
    #         "objectName": object_name
    #     })

    #     # update color of clip regarding the version order
    #     self.set_item_color(track_item, version)

    #     return phiero.update_container(track_item, data_imprint)

    # def remove(self, container):
    #     """ Removing previously loaded clips
    #     """
    #     # load clip to timeline and get main variables
    #     namespace = container['namespace']
    #     track_item = phiero.get_track_items(
    #         track_item_name=namespace)
    #     track = track_item.parent()

    #     # remove track item from track
    #     track.removeItem(track_item)

    # @classmethod
    # def multiselection(cls, track_item):
    #     if not cls.track:
    #         cls.track = track_item.parent()
    #         cls.sequence = cls.track.parent()

    # @classmethod
    # def set_item_color(cls, track_item, version):

    #     clip = track_item.source()
    #     # define version name
    #     version_name = version.get("name", None)
    #     # get all versions in list
    #     versions = io.find({
    #         "type": "version",
    #         "parent": version["parent"]
    #     }).distinct('name')

    #     max_version = max(versions)

    #     # set clip colour
    #     if version_name == max_version:
    #         clip.binItem().setColor(cls.clip_color_last)
    #     else:
    #         clip.binItem().setColor(cls.clip_color)
