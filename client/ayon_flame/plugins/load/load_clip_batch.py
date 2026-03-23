import flame
import ayon_flame.api as ayfapi
from ayon_core.lib.transcoding import (
    VIDEO_EXTENSIONS,
    IMAGE_EXTENSIONS
)

class LoadClipBatch(ayfapi.ClipLoader):
    """Load a product to timeline as clip

    Place clip to timeline on its asset origin timings collected
    during conforming to project
    """

    product_types = {"render2d", "source", "plate", "render", "review"}
    representations = {"*"}
    extensions = set(
        ext.lstrip(".") for ext in IMAGE_EXTENSIONS.union(VIDEO_EXTENSIONS)
    )

    label = "Load as clip to current batch"
    order = -10
    icon = "code-fork"
    color = "orange"

    # settings
    reel_name = "AYON_LoadedReel"
    clip_name_template = "{batch}_{folder[name]}_{product[name]}<_{output}>"

    """ Anatomy keys from version context data and dynamically added:
        - {layerName} - original layer name token
        - {layerUID} - original layer UID token
        - {originalBasename} - original clip name taken from file
    """
    layer_rename_template = "{folder[name]}_{product[name]}<_{output}>"
    layer_rename_patterns = []

    def _get_formatting_data(self, context, options):
        formatting_data = super()._get_formatting_data(context, options)
        self.batch = options.get("batch") or flame.batch
        folder_entity = context["folder"]
        product_entity = context["product"]
        formatting_data["batch"] = self.batch.name.get_value()
        formatting_data.update({
            "asset": folder_entity["name"],
            "folder": {
                "name": folder_entity["name"],
            },
            "subset": product_entity["name"],
            "family": product_entity["productType"],
            "product": {
                "name": product_entity["name"],
                "type": product_entity["productType"],
            }
        })
        return formatting_data

    def _get_reel(self):

        matching_reel = [
            rg for rg in self.batch.reels
            if rg.name.get_value() == self.reel_name
        ]

        return (
            matching_reel.pop()
            if matching_reel
            else self.batch.create_reel(str(self.reel_name))
        )
