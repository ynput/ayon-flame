"""Creator plugin for Flame Reel browser context.

This plugin allows users to create plates from selected items from within
the Flame Reel browser context.

Dev notes:
    - code shouls be universal enought to be able to serve also `render` and
      `image` types
    - Add support for creating plates from multiple selected items
    - Implement error handling for invalid selections
    - saving metadata at marker inside reel clip timeline

Restrictions:
    - only need to be offered within Creator plugins if opened
      from Flame Reel browser context
    - selected mode only supported so precreate validation needs to check
      if selected items are valid for plate creation and raise if no selection
"""
import uuid
from copy import deepcopy

import flame
from ayon_core.lib import BoolDef
from ayon_core.pipeline.create import CreatedInstance, CreatorError
from ayon_flame.api import lib, pipeline, plugin

# Used as a key by the creators in order to
# retrieve the instances data into clip markers.
_CONTENT_ID = "flame_sub_products"


class PlateCreator(plugin.FlameReelCreator):
    """Publishable clip"""
    identifier = "io.ayon.creators.flame.reel.plate"
    product_type = "plate"
    label = "Plate Reel Clip"

    icon = "film"
    defaults = ["Main"]

    detailed_description = """
Publishing clips/plate, audio for new shots to project
or updating already created from Flame. Publishing will create
OTIO file.
"""
    @classmethod
    def apply_settings(cls, project_settings):
        selection = lib.CTX.selection or []
        # make sure this is sequence timeline context
        if not [
            item for item in selection
            if isinstance(item, flame.PyClip)
        ]:
            cls.enabled = False

    def get_pre_create_attr_defs(self):

        return [
            BoolDef(
                "use_selection",
                label="Use only selected clip(s).",
                tooltip=(
                    "When enabled it restricts create process "
                    "to selected clips."
                ),
                default=True
            ),
        ]

    def create(self, product_name, instance_data, pre_create_data):
        super().create(
            product_name,
            instance_data,
            pre_create_data)

        if len(self.selected) < 1:
            return None

        self.log.info(self.selected)
        self.log.debug(f"Selected: {self.selected}")

        instance_data.update(pre_create_data)
        instance_data["task"] = None

        for clip_data in self.selected:
            item = clip_data["PyClip"]
            self.log.info(f"selected item: {item} is type {type(item)}")

            # set instance related data
            clip_index = str(uuid.uuid4())
            clip_instance_data = deepcopy(instance_data)
            clip_instance_data["clip_index"] = clip_index

            instance = CreatedInstance(
                self.product_type,
                instance_data["productName"],
                clip_instance_data,
                self
            )
            self._add_instance_to_context(instance)
            instance.transient_data["has_promised_context"] = True

            instance.transient_data["clip_item"] = item
            pipeline.imprint(
                item,
                data={
                    _CONTENT_ID: clip_instance_data,
                    "clip_data": clip_data,
                }
            )

    def collect_instances(self):
        """Collect all created instances from current timeline."""
        pass

    def update_instances(self, update_list):
        """Never called, update is handled via _FlameInstanceCreator."""
        pass

    def remove_instances(self, instances):
        """Never called, update is handled via _FlameInstanceCreator."""
        pass
