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
import ayon_flame.api as ayfapi
import flame
from ayon_core.lib import BoolDef, EnumDef, NumberDef, TextDef, UILabelDef
from ayon_core.pipeline.create import (
    CreatedInstance,
    CreatorError,
    ParentFlags,
)
from ayon_flame.api import lib, pipeline, plugin

# Used as a key by the creators in order to
# retrieve the instances data into clip markers.
_CONTENT_ID = "flame_sub_products"

# get current selection from the current focus
# TODO: implement it in plugin
def get_segments_from_selection():
    """Get segments from selected items.

    Returns:
        list: List of segments.
    """
    return [
        segment for segment in lib.CTX.selection
        if isinstance(segment, flame.PySegment)
    ]


class _FlameInstanceCreator(plugin.HiddenFlameCreator):
    """Wrapper class for clip types products.
    """

    def _add_instance_to_context(self, instance):
        parent_id = instance.get("parent_instance_id")
        if parent_id is not None and ParentFlags is not None:
            instance.set_parent(
                parent_id,
                # Disable if a parent is disabled and delete if a parent
                #   is deleted
                ParentFlags.share_active | ParentFlags.parent_lifetime
            )
        super()._add_instance_to_context(instance)

    def create(self, instance_data, _):
        """Return a new CreateInstance for new shot from Flame.

        Args:
            instance_data (dict): global data from original instance

        Return:
            CreatedInstance: The created instance object for the new shot.
        """

        new_instance = CreatedInstance(
            self.product_type,
            instance_data["productName"],
            instance_data,
            self
        )
        self._add_instance_to_context(new_instance)
        return new_instance

    def update_instances(self, update_list):
        """Store changes of existing instances so they can be recollected.

        Args:
            update_list(List[UpdateData]): Gets list of tuples. Each item
                contain changed instance and it's changes.
        """
        for created_inst, _changes in update_list:
            clip_item = created_inst.transient_data["clip_item"]
            marker_data = ayfapi.get_clip_data_marker(clip_item)

            # Backwards compatible (Deprecated since 24/09/05)
            # ignore instance if no existing marker data
            if marker_data is None:
                continue

            try:
                instances_data = marker_data[_CONTENT_ID]

            # Backwards compatible (Deprecated since 24/09/05)
            except KeyError:
                marker_data[_CONTENT_ID] = {}
                instances_data = marker_data[_CONTENT_ID]

            instances_data[self.identifier] = created_inst.data_to_store()
            pipeline.imprint(
                clip_item,
                data=  {
                    _CONTENT_ID: instances_data,
                    "clip_index": marker_data["clip_index"],
                }
            )

    def remove_instances(self, instances):
        """Remove instance marker from track item.

        Args:
            instance(List[CreatedInstance]): Instance objects which should be
                removed.
        """
        for instance in instances:
            clip_item = instance.transient_data["clip_item"]
            marker_data = ayfapi.get_clip_data_marker(clip_item)

            instances_data = marker_data.get(_CONTENT_ID, {})
            instances_data.pop(self.identifier, None)
            self._remove_instance_from_context(instance)

            pipeline.imprint(
                clip_item,
                data=  {
                    _CONTENT_ID: instances_data,
                    "clip_index": marker_data["clip_index"],
                }
            )


class _FlameInstanceClipCreatorBase(_FlameInstanceCreator):
    """ Base clip product creator.
    """

    def register_callbacks(self):
        self.create_context.add_value_changed_callback(self._on_value_change)

    def _on_value_change(self, event):
        for item in event["changes"]:
            instance = item["instance"]
            if (
                instance is None
                or instance.creator_identifier != self.identifier
            ):
                continue

            changes = item["changes"].get("creator_attributes", {})
            if "review" not in changes:
                continue

            attr_defs = instance.creator_attributes.attr_defs
            review_value = changes["review"]
            reviewable_source = next(
                attr_def
                for attr_def in attr_defs
                if attr_def.key == "reviewableSource"
            )
            reviewable_source.enabled = review_value

            instance.set_create_attr_defs(attr_defs)

    def get_attr_defs_for_instance(self, instance):
        parent_instance = instance.creator_attributes.get("parent_instance")
        current_sequence = lib.get_current_sequence(lib.CTX.selection)

        if current_sequence is not None:
            gui_tracks = [
                {"value": tr_name, "label": f"Track: {tr_name}"}
                for tr_name in get_video_track_names(current_sequence)
            ]
        else:
            gui_tracks = []

        instance_attributes = [
            TextDef(
                "parentInstance",
                label="Linked to",
                disabled=True,
                default=parent_instance,
            ),
        ]

        if self.product_type == "plate":
            current_review = instance.creator_attributes.get("review", False)
            instance_attributes.extend(
                [
                    BoolDef(
                        "review",
                        label="Review",
                        tooltip="Switch to reviewable instance",
                        default=False,
                    ),
                    EnumDef(
                        "reviewableSource",
                        label="Reviewable Source",
                        tooltip=("Selecting source for reviewable files."),
                        items=(
                            [
                                {
                                    "value": "clip_media",
                                    "label": "[ Clip's media ]",
                                },
                            ]
                            + gui_tracks
                        ),
                        disabled=not current_review,
                    ),
                ]
            )

        return instance_attributes


class EditorialPlateInstanceCreator(_FlameInstanceClipCreatorBase):
    """Plate product type creator class"""
    identifier = "io.ayon.creators.flame.plate"
    product_type = "plate"
    label = "Editorial Plate"

    def create(self, instance_data, _):
        """Return a new CreateInstance for new shot from Resolve.

        Args:
            instance_data (dict): global data from original instance

        Return:
            CreatedInstance: The created instance object for the new shot.
        """
        return super().create(instance_data, None)
