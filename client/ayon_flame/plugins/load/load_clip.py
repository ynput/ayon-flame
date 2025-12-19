import flame
import ayon_flame.api as ayfapi
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
