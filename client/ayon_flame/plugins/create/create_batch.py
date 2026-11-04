"""Creator plugin for Flame Batch.

Will create a new workfile instance from current batch.
"""
import re
from typing import Dict, Any, List, Tuple

from ayon_core.pipeline import CreatedInstance
from ayon_core.pipeline.create import PRODUCT_NAME_ALLOWED_SYMBOLS

import ayon_flame.api as flapi
from ayon_flame.constants import BATCH_CREATOR_IDENTIFIER

# Number Flame adds to the name of a batch group that is taken: ' (2)'.
_FLAME_NUMBER_SUFFIX = re.compile(r"^(?P<name>.*\S)\s*\((?P<number>\d+)\)\s*$")


def get_batch_product_name(batch_name: str, fallback: str) -> str:
    """ Return a product name valid for the server from a batch group name.

    Flame adds ' (2)', ' (3)'... to a batch group name that is taken, it
    becomes '_2', '_3'... like numbered names in AYON ('sh010_comp (2)'
    gives 'sh010_comp_2'). Batch groups can be named freely, so the
    characters the server rejects are removed and the name never starts or
    ends with a dot.

    Args:
        batch_name (str): Batch group name.
        fallback (str): Name used when nothing valid is left of the batch
            group name (e.g. '(2)' has only the number).

    Returns:
        str: Product name.
    """
    match = _FLAME_NUMBER_SUFFIX.match(batch_name)
    if match:
        batch_name = "{}_{}".format(match["name"].rstrip(), match["number"])

    product_name = re.sub(
        "[^{}]+".format(PRODUCT_NAME_ALLOWED_SYMBOLS), "", batch_name
    ).strip(".")
    return product_name or fallback


class CreateBatchWorkfile(flapi.FlameCreator):
    """Batch workfile creator (stores instance data in a Note node).
    """
    settings_category = "flame"

    identifier = BATCH_CREATOR_IDENTIFIER
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

    def _dump_instance_data(self, data: Dict[str, Any]):
        """ Write instance data into the batch metadata Note node.
        """
        node = flapi.get_metadata_node(create=True)
        flapi.write_node_metadata(node, data)

    def _load_instance_data(self) -> Dict[str, Any]:
        """ Read instance data from the batch metadata Note node.
        """
        node = flapi.get_metadata_node()
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
            batch = flapi.get_current_batch()
        except RuntimeError:
            self.log.warning("No active batch group found, skipping.")
            return
        batch_name = batch.name.get_value()
        self.log.info(f"Creating batch workfile instance for: {batch_name}")
        instance_data["batch_name"] = batch_name

        # The name is made from the batch group name, 'product_name' of the
        # creator context is the fallback.
        product_name = get_batch_product_name(batch_name, product_name)

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

        node = flapi.get_metadata_node()
        if node:
            node.delete()
