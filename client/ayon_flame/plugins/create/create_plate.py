"""Creator plugin for Flame Reel browser (or media panel) context.

This plugin allows users to create plates from selected items from within
the Flame Reel browser context.

Dev notes:
    - code should be universal enought to be able to serve also `render` and
      `image` types
    - Add support for creating plates from multiple selected items
    - Implement error handling for invalid selections
    - saving metadata at marker inside reel clip timeline

Restrictions:
    - only need to be offered within Creator plugins if opened
      from Flame Reel browser context
    - selected mode only
"""
import uuid
from copy import deepcopy

from ayon_core.lib import BoolDef
from ayon_core.pipeline.create import CreatedInstance
from ayon_flame.api import lib, pipeline, plugin

# Used as a key by the creators in order to
# retrieve the instances data into clip markers.
_CONTENT_ID = "flame_sub_products"


class FlameReelPlateCreator(plugin.FlameCreator):
    """Reel/Media panel clip"""
    identifier = "io.ayon.creators.flame.reel.plate"
    product_base_type = "plate"
    product_type = product_base_type
    label = "Plate Reel Clip"

    icon = "film"
    defaults = ["Main"]

    detailed_description = """
Publishing clips/plate from Media panel.
"""

    def apply_settings(self, project_settings):
        super().apply_settings(project_settings)
        # Disable if not in menu context.
        self.enabled = (lib.CTX.context == "FlameMenuUniversal")

    def get_pre_create_attr_defs(self):
        return [
            BoolDef(
                "use_selection",
                label="Use only selected clip(s).",
                tooltip=(
                    "Restricts creation to selected clips."
                ),
                default=True,
                visible=False,
            ),
            BoolDef(
                "review",
                label="Review",
                tooltip="Switch to reviewable instance",
                default=False,
            ),
        ]

    def get_attr_defs_for_instance(self, instance):
        return [
            BoolDef(
                "review",
                label="Review",
                tooltip="Switch to reviewable instance",
                default=instance.creator_attributes.get("review", False),
            )
        ]

    def create(self, product_name, instance_data, pre_create_data):
        super().create(
            product_name,
            instance_data,
            pre_create_data)

        if not self.selected:
            return  # No selection, nothing to do.

        self.log.info(self.selected)
        self.log.debug(f"Selected: {self.selected}")

        project_entity = self.create_context.get_current_project_entity()
        folder_entity = self.create_context.get_current_folder_entity()
        task_entity = self.create_context.get_current_task_entity()

        project_name = project_entity["name"]
        host_name = self.create_context.host_name

        product_name_base = self.get_product_name(
            project_name=project_name,
            project_entity=project_entity,
            folder_entity=folder_entity,
            task_entity=task_entity,
            variant=self.default_variant,
            host_name=host_name,
        )

        instance_data.update(pre_create_data)
        instance_data["task"] = None
        instance_data["creator_attributes"] = {
            "review": pre_create_data.get("review", False)
        }

        for clip_data in self.selected:
            clip_name = clip_data["name"]
            product_name = f"{product_name_base}_{clip_name}"
            clip_item = clip_data.pop("PyClip")
            _ = clip_data.pop("PySegment")

            # set instance related data
            clip_index = str(uuid.uuid4())
            clip_instance_data = deepcopy(instance_data)
            clip_instance_data["productName"] = product_name
            clip_instance_data["clip_data"] = clip_data

            instance = CreatedInstance(
                self.product_type,
                product_name,
                clip_instance_data,
                self
            )
            self._add_instance_to_context(instance)
            instance.transient_data["has_promised_context"] = True

            instance.transient_data["clip_item"] = clip_item
            pipeline.imprint(
                clip_item,
                data={
                    _CONTENT_ID: {self.identifier: clip_instance_data},
                    "clip_index": clip_index,
                }
            )

    def collect_instances(self):
        """Collect all created instances from current timeline."""
        clips = lib.get_clips_in_reels(self.project)
        for clip_data in clips:
            clip_item = clip_data.pop("PyClip")
            clip_data.pop("PySegment")  # non-serializable

            marker_data = lib.get_clip_data_marker(clip_item)
            if not marker_data:
                continue

            content_data = marker_data.get(_CONTENT_ID, {})
            instance_data = content_data.get(self.identifier, None)
            if not instance_data:
                continue

            # Add instance
            created_instance = CreatedInstance.from_existing(
                instance_data, self)

            self._add_instance_to_context(created_instance)
            created_instance.transient_data["clip_item"] = clip_item

    def update_instances(self, update_list):
        """Store changes of existing instances so they can be recollected.

        Args:
            update_list(List[UpdateData]): Gets list of tuples. Each item
                contain changed instance and it's changes.
        """
        for created_inst, _changes in update_list:
            clip_item = created_inst.transient_data["clip_item"]
            marker_data = lib.get_clip_data_marker(clip_item)

            instances_data = marker_data[_CONTENT_ID]
            instances_data[self.identifier] = created_inst.data_to_store()

            pipeline.imprint(
                clip_item,
                data=marker_data
            )

    def remove_instances(self, instances):
        """Remove instances."""
        for instance in instances:
            clip_item = instance.transient_data["clip_item"]
            marker_data = lib.get_clip_data_marker(clip_item)

            instances_data = marker_data.get(_CONTENT_ID, {})
            instances_data.pop(self.identifier, None)
            self._remove_instance_from_context(instance)

            pipeline.imprint(
                clip_item,
                data=marker_data
            )
