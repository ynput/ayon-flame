from copy import deepcopy
from typing import Optional, Dict

import ayon_api

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
        """Load all published versions as native Flame batch iterations.

        Each AYON version is loaded as a named iteration (v001, v002, …)
        inside a single batch group. Switch between versions via the Flame UI
        (right-click batch → Iterations). Programmatic iteration switching is
        not supported by the Flame Python API.
        """
        import flame

        project_name = context["project"]["name"]
        product_id = context["version"]["productId"]
        requested_version_entity = context["version"]
        batch_name = (
            requested_version_entity.get("data", {}).get("batch_name")
            or context["representation"]["context"].get("asset")
        )

        # Collect all versions sorted oldest → newest.
        all_versions = sorted(
            ayon_api.get_versions(project_name, product_ids=[product_id]),
            key=lambda v: v["version"],
        )

        # Collect matching representations per version.
        repres_by_version_id = {
            r["versionId"]: r
            for r in ayon_api.get_representations(
                project_name,
                representation_names={context["representation"]["name"]},
                version_ids=[v["id"] for v in all_versions],
            )
        }

        if not repres_by_version_id:
            raise RuntimeError(
                f"No representations found for product '{product_id}' "
                f"in project '{project_name}'."
            )

        current_iteration = None
        iterations = 0
        for version in all_versions:
            repre = repres_by_version_id.get(version["id"])
            if not repre:
                continue

            iterations += 1
            version_context = deepcopy(context)
            version_context["version"] = version
            version_context["representation"] = repre

            filepath = self.filepath_from_context(version_context)
            batch_utils.load_batch_from_consolidated_json(
                filepath,
                name=batch_name,
            )
            flame.batch.iterate()

            if requested_version_entity["id"] == version["id"]:
                current_iteration = flame.batch.batch_iterations[-1]

        self.log.debug(
            f"Loaded batch group with {iterations} versions as iterations."
        )

        if current_iteration:
            flame.batch.replace_setup(current_iteration)
            self.log.debug(
                f'Set {requested_version_entity["version"]} '
                f"as current batch iteration."
            )

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
