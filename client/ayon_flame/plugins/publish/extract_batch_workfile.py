"""Extract batch group as a consolidated JSON workfile."""
import os
import pyblish.api

from ayon_core.pipeline import publish
import ayon_flame.api as flapi


class ExtractBatchWorkfile(publish.Extractor):
    """Export the current batch group as a consolidated JSON workfile."""

    label = "Extract Batch Workfile"
    order = pyblish.api.ExtractorOrder - 0.45
    families = ["workfile"]
    hosts = ["flame"]

    def process(self, instance):
        if instance.data.get("batch_name") is None:
            self.log.warning("No batch_name found in instance data, skipping.")
            return

        if "representations" not in instance.data:
            instance.data["representations"] = []

        batch_name = instance.data.get("batch_name")
        batch = flapi.get_batch_from_workspace(batch_name)
        if not batch:
            raise ValueError(f"Batch group not found: {batch_name}")

        staging_dir = self.staging_dir(instance)
        filename = f"{batch_name}.json"
        filepath = os.path.join(staging_dir, filename)
        flapi.save_batch_as_consolidated_json(batch, filepath)

        representation = {
            "name": "batch",
            "ext": "json",
            "files": filename,
            "stagingDir": staging_dir,
        }
        instance.data["representations"].append(representation)
        self.log.info(
            f"Extracted batch workfile representation: {representation}"
        )
