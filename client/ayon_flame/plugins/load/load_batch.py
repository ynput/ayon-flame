from typing import Optional, Dict

from ayon_core.pipeline import LoaderPlugin

from ayon_flame.api import batch_utils


class LoadBatchgroup(LoaderPlugin):
    product_types = {"workfile"}
    representations = {"*"}
    extensions = ("json",)

    label = "Load batch"
    order = -10
    icon = "code-fork"
    color = "orange"

    def load(
            self,
            context: Dict,
            name: Optional[str] = None,
            namespace: Optional[str] = None,
            options: Optional[Dict] = None,
    ):
        """Load new batch from consolidated json file.
        """
        path = self.filepath_from_context(context)
        version_data = context.get("version", {}).get("data", {})
        batch_name = version_data.get("batch_name")

        batch = batch_utils.load_batch_from_consolidated_json(
            path,
            name=batch_name
        )
        self.log.info(f"Loaded batch: {batch}")
        #TODO: match with batchgroup iteration

    def update(self, container, context):
        raise NotImplementedError(
            "Version management rely on Flame "
            "native batch iteration implementation."
        )

    def remove(self, container):
        raise NotImplementedError(
            "Version management rely on Flame "
            "native batch iteration implementation."
        )
