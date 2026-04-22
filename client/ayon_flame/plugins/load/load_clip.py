import flame

import ayon_flame.api as ayfapi


class LoadClip(ayfapi.ClipLoader):
    """Load a media product to as clip in the media panel.
    """
    label = "Load as clip"
    order = -10
    icon = "code-fork"
    color = "orange"

    # settings
    reel_group_name = "AYON_Reels"
    reel_name = "Loaded"
    clip_name_template = "{folder[name]}_{product[name]}<_{output}>"

    layer_rename_template = "{folder[name]}_{product[name]}<_{output}>"
    layer_rename_patterns = []

    @property
    def product_types(self):
        return self.product_base_types

    def _get_reel(self):
        """ Retrieve or create a reel_group/reel for loaded clips.
        """
        for reel_group in self.fpd.reel_groups:
            # Expected reel group from settings exists, retrieve.
            if reel_group.name.get_value() == self.reel_group_name:
                break

        # Create new empty reel group.
        else:
            reel_group = self.fpd.create_reel_group(str(self.reel_group_name))
            for reel in reel_group.reels:
                if "reel" not in reel.name.get_value().lower():
                    continue
                self.log.debug(f"Removing useless reel: {reel.name}")
                flame.delete(reel)

        matching_reel = [
            re for re in reel_group.reels
            if re.name.get_value() == self.reel_name
        ]

        if not matching_reel:
            return reel_group.create_reel(str(self.reel_name))

        return matching_reel.pop()
