from __future__ import annotations

import flame

import ayon_flame.api as ayfapi


class LoadClipBatch(ayfapi.ClipLoader):
    """Load a media product as clip into a batch reel.
    """
    label = "Load as clip to current batch"
    order = -10
    icon = "code-fork"
    color = "orange"

    # settings
    reel_name = "AYON_LoadedReel"
    clip_name_template = "{batch}_{folder[name]}_{product[name]}<_{output}>"

    layer_rename_template = "{folder[name]}_{product[name]}<_{output}>"
    layer_rename_patterns = []

    @property
    def product_types(self):
        return self.product_base_types

    def load(self, context, name, namespace, options):
        self.batch = options.get("batch") or flame.batch
        return super().load(context, name, namespace, options)

    def _get_clip_name_format_data(self, context, options) -> dict[str, str]:
        """ Get formatting data for the clip name template.
        """
        formatting_data = super()._get_clip_name_format_data(context, options)
        formatting_data["batch"] = self.batch.name.get_value()
        return formatting_data

    def _get_reel(self):
        """ Retrieve/Create expected reel from current batch.
        """
        for reel in self.batch.reels:
            if reel.name.get_value() == self.reel_name:
                return reel

        return self.batch.create_reel(str(self.reel_name))
