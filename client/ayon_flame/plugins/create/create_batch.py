"""Creator plugin for Flame Batch.

Will create a new workfile instance from current batch.
"""
from typing import Optional, Dict, Any, List, Tuple

from ayon_core.pipeline import CreatedInstance

import ayon_flame.api as flapi

import flame


# Name of the hidden Note node used to embed instance data inside the batch.
_METADATA_NODE_NAME = "AYON_metadata"


class CreateBatchWorkfile(flapi.FlameCreator):
    """Batch workfile creator (stores instance data in a Note node).
    """
    settings_category = "flame"

    identifier = "io.ayon.creators.flame.batch.workfile"
    label = "Batch"
    product_base_type = "workfile"
    product_type = product_base_type
    icon = "fa5.file-code"
    default_variant = "Main"

    detailed_description = """
Publishing batch from Batch panel.
"""

    def apply_settings(self, project_settings):
        super().apply_settings(project_settings)
        # Only active in Batch context.
        self.enabled = (flapi.CTX.context == "FlameMenuBatch")

    @staticmethod
    def _get_current_batch() -> flame.PyBatch:
        """ Return the current flame.batch object or None.
        """
        try:
            return flame.batch
        except Exception as error:
            raise RuntimeError(
                "Cannot find current batch from context."
            ) from error

    def _get_metadata_node(
            self,
            create: bool = True
        ) -> Optional[flame.PyNode]:
        """ Find or create the AYON metadata Note node in the current batch.
        """
        batch = self._get_current_batch()
        for node in batch.nodes:
            if node.name.get_value() == _METADATA_NODE_NAME:
                return node

        if not create:
            return None

        node = batch.create_node("Note")
        node.name.set_value(_METADATA_NODE_NAME)
        return node

    def _dump_instance_data(self, data: Dict[str, Any]):
        """ Write instance data into the batch metadata Note node.
        """
        node = self._get_metadata_node()
        flapi.write_node_metadata(node, data)

    def _load_instance_data(self) -> Dict[str, Any]:
        """ Read instance data from the batch metadata Note node.
        """
        node = self._get_metadata_node(create=False)
        if not node:
            return {}

        data = flapi.read_node_metadata(node)
        if data is None:
            return {}
        return data

    def create(
            self,
            product_name: str,
            instance_data: Dict[str, Any],
            pre_create_data: Dict[str, Any]
        ):
        """Create a batch workfile instance.
        """
        # Set flame_context directly.
        # Skip FlameCreator.create() which runs reel/clip
        # logic irrelevant to the batch context.
        instance_data["flame_context"] = flapi.CTX.context

        try:
            batch = self._get_current_batch()
        except RuntimeError:
            self.log.warning("No active batch group found, skipping.")
            return
        batch_name = batch.name.get_value()
        self.log.info(f"Creating batch workfile instance for: {batch_name}")
        instance_data["batch_name"] = batch_name

        # TODO: check this logic with prod use-cases.
        product_name = batch_name.replace(" ", "")

        instance = CreatedInstance(
            product_base_type=self.product_base_type,
            product_type=self.product_type,
            product_name=product_name,
            data=instance_data,
            creator=self,
        )
        self._add_instance_to_context(instance)
        self._dump_instance_data(instance.data_to_store())

    def collect_instances(self):
        """ Collect existing batch instance from the metadata Note node.
        """
        data = self._load_instance_data()
        if not data:
            # No data found, nothing to collect
            return

        instance = CreatedInstance(
            product_base_type=self.product_base_type,
            product_type=self.product_type,
            product_name=data["productName"],
            data=data,
            creator=self,
        )
        self._add_instance_to_context(instance)

    def update_instances(self, update_list: List[Tuple[CreatedInstance, Any]]):
        """ Persist updated instance data to the metadata Note node.
        """
        for created_inst, _ in update_list:
            self._dump_instance_data(created_inst.data_to_store())

    def remove_instances(self, instances: List[CreatedInstance]):
        """Remove instance and delete the metadata Note node from the batch.
        """
        for instance in instances:
            self._remove_instance_from_context(instance)

        node = self._get_metadata_node(create=False)
        if node:
            node.delete()
