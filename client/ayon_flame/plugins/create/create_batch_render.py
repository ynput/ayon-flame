"""Creates a render product instance per selected Write File node,
storing instance metadata directly in the node's note attribute.
"""
from typing import Dict, Any, List, Tuple, Optional

from ayon_core.lib import BoolDef
from ayon_core.pipeline import CreatedInstance, CreatorError

import ayon_flame.api as flapi

import flame


class CreateBatchRender(flapi.FlameCreator):
    """Create render product instances from selected Write File node.
    """

    settings_category = "flame"

    identifier = "io.ayon.creators.flame.batch.render"
    label = "Batch Render"
    product_type = "render"
    product_base_type = "render"
    icon = "fa5.film"
    default_variant = "Main"

    detailed_description = """
Create render product from selected Write File node in the
current batch group.
"""

    def apply_settings(self, project_settings):
        super().apply_settings(project_settings)

        create_settings = project_settings["flame"]["create"]
        self.write_node_presets = create_settings[self.__class__.__name__]

        # Only active in Batch context.
        self.enabled = (flapi.CTX.context == "FlameMenuBatch")

    @staticmethod
    def _get_write_file_nodes() -> List[flame.PyWriteFileNode]:
        """ Return Write File nodes from the current batch selection. """
        selected = flame.batch.selected_nodes.get_value()
        return [
            node for node in selected
            if isinstance(node, flame.PyWriteFileNode)
        ]

    @staticmethod
    def _connect_clip_and_write_nodes(
        clip_node: flame.PyClipNode,
        write_node: flame.PyWriteFileNode,
    ):
        duration = clip_node.duration
        write_node.source_timecode = clip_node.clip.start_time

        start_frame = flame.batch.start_frame.get_value()
        write_node.range_start = start_frame
        write_node.range_end = start_frame + duration - 1

        flame.batch.connect_nodes(
            clip_node,
            clip_node.output_sockets[0], # rgb
            write_node,
            "Front",
        )

    def _apply_metadata_on_write_node(
        self,
        write_node: flame.PyWriteFileNode,
        node_name: Optional[str] = None,
    ):
        if node_name:
            write_node.name = node_name

        for attr, value in self.write_node_presets.items():
            if attr == "node_name":
                continue

            if value not in (None, ""):
                try:
                    setattr(write_node, attr, value)
                except RuntimeError as error:
                    raise RuntimeError(
                        f"Could not set attribute '{attr}' "
                        f"value '{value}' on Write File node."
                    ) from error

    def get_pre_create_attr_defs(self) -> List[BoolDef]:
        return [
            BoolDef(
                "use_selection",
                default=True,
                label="Use Selection"
            )
        ]

    def get_instance_attr_defs(self) -> List[BoolDef]:
        return [
            BoolDef(
                "review",
                default=True,
                label="Review"
            )
        ]

    def create(
            self,
            product_name: str,
            instance_data: Dict[str, Any],
            pre_create_data: Dict[str, Any],
    ):
        """Create a render instance for each selected Write File node."""
        instance_data["flame_context"] = flapi.CTX.context

        use_selection = pre_create_data["use_selection"]
        selected = flame.batch.selected_nodes.get_value()

        if use_selection and not selected:
            raise CreatorError("No nodes selected from batch.")

        if use_selection and len(selected) > 1:
            raise CreatorError("Multiple selected nodes.")

        nodes = self._get_write_file_nodes()
        if len(nodes) > 1:
            # TODO: How to handle multiple selected 'Write File' nodes ?
            # Currently they'd all produce the same product name.
            raise CreatorError("Multiple selected 'Write File' nodes.")

        if nodes:
            node = nodes[0]
        else:
            node = flame.batch.create_node("Write File")

        batch_name = flame.batch.name.get_value()

        # Apply setting metadata on the write node
        self._apply_metadata_on_write_node(
            node,
            node_name=self.write_node_presets.get("node_name"),
        )

        # Attempt to connect to select "Clip" node if exists
        selected_node = selected[0] if selected else None
        if selected_node and isinstance(selected_node, flame.PyClipNode):
            self._connect_clip_and_write_nodes(selected_node, node)

        node_name = node.name.get_value()
        node_instance_data = dict(instance_data)
        node_instance_data["batch_name"] = batch_name
        node_instance_data["write_node_name"] = node_name

        instance = CreatedInstance(
            product_base_type=self.product_base_type,
            product_type=self.product_type,
            product_name=product_name,
            data=node_instance_data,
            creator=self,
        )
        self._add_instance_to_context(instance)
        flapi.write_node_metadata(node, instance.data_to_store())
        self.log.info(
            f"Created render instance '{product_name}' "
            f"from node '{node_name}'."
        )

    def collect_instances(self):
        """ Collect existing instances from Write File node metadata. """
        for node in list(flame.batch.nodes):
            # Only process Write File nodes.
            if not isinstance(node, flame.PyWriteFileNode):
                continue

            data = flapi.read_node_metadata(node)
            # Not registered with AYON, skip.
            if not data:
                continue

            instance = CreatedInstance(
                product_base_type=self.product_base_type,
                product_type=self.product_type,
                product_name=data["productName"],
                data=data,
                creator=self,
            )
            self._add_instance_to_context(instance)

    def update_instances(self, update_list: List[Tuple[CreatedInstance, Any]]):
        """ Persist updated instance data back to the Write File node. """
        all_nodes = {
            node.name.get_value(): node
            for node in list(flame.batch.nodes)
            if isinstance(node, flame.PyWriteFileNode)
        }
        for created_inst, _ in update_list:
            node_name = created_inst.data.get("write_node_name")
            node = all_nodes.get(node_name)
            if node:
                flapi.write_node_metadata(node, created_inst.data_to_store())

            else:
                self.log.warning(
                    f"Write File node '{node_name}' not found."
                )

    def remove_instances(self, instances: List[CreatedInstance]):
        """ Clear AYON metadata from the associated Write File nodes. """
        all_nodes = {
            node.name.get_value(): node
            for node in list(flame.batch.nodes)
            if isinstance(node, flame.PyWriteFileNode)
        }
        for instance in instances:
            self._remove_instance_from_context(instance)
            node_name = instance.data.get("write_node_name")
            node = all_nodes.get(node_name)
            if node:
                flapi.clear_node_metadata(node)
