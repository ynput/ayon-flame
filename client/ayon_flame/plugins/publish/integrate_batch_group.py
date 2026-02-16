import pyblish
import os

import ayon_api
from ayon_api.operations import OperationsSession

from ayon_core.lib import source_hash
from ayon_core.pipeline.load import (
    get_representation_context,
    discover_loader_plugins,
    load_with_repre_context,
    IncompatibleLoaderError
)
from ayon_core.pipeline.workfile import get_workdir

import ayon_flame.api as ayfapi


class IntegrateBatchgroup(pyblish.api.InstancePlugin):
    """Extract + Integrate Batchgroup Product data."""

    order = pyblish.api.IntegratorOrder + 0.45
    label = "Integrate Batchgroup"
    hosts = ["flame"]
    families = ["batchgroup"]

    settings_category = "flame"

    default_loader = "LoadClip"

    def process(self, instance):
        # Gather new published plate representation to
        # be associated with the current batchgroup.
        plate_repres = self._find_plate_representations(
            instance,
        )
        if not plate_repres:
            self.log.info(
                "Ignore batchgroup post-upgrade. "
                "No relevant plate representation found."
            )
            return

        # Load/Update plate representation(s) in the bgroup.
        bgroup = instance.data["extracted_batchgroup"]
        self.log.debug("Batchgroup: %s.", bgroup.name)
        self._load_clip_to_context(instance, bgroup, plate_repres)

        # Override batchgroup publish.
        self.update_repre_entity(instance, bgroup)

    def _find_plate_representations(self, instance):
        """ Gather representations to load/update in the
            batchgroup from sibling plate instance if any.
        """
        parent_instance_id = instance.data["parent_instance_id"]
        plate_instance = None

        # Find parent instance from context
        for inst in instance.context:
            creator_identifier = inst.data["creator_identifier"]
            inst_parent_instance_id = inst.data.get("parent_instance_id")

            if (
                inst_parent_instance_id == parent_instance_id
                and creator_identifier == "io.ayon.creators.flame.plate"
            ):
                plate_instance = inst
                break
        else:
            return []

        repre_names_to_load = {
            repr_data["name"]: repr_data
            for repr_data in plate_instance.data["representations"]
            if repr_data.get("load_to_batch_group")
        }

        published_repres = plate_instance.data["published_representations"]
        repre_plate_to_load = []
        for repre_id, repre_info in published_repres.items():
            repr_name = repre_info["representation"]["name"]
            if repr_name in repre_names_to_load:
                repre_info_copy = repre_info.copy()
                repre_info_copy.update(repre_names_to_load[repr_name])
                repre_info_copy["id"] = repre_id
                repre_plate_to_load.append(repre_info_copy)

        return repre_plate_to_load


    def _load_clip_to_context(self, instance, bgroup, plate_repres):
        """ Load/Update the representation(s) in the batchgroup.
        """
        # get all loaders for host
        loaders_by_name = {
            loader.__name__: loader
            for loader in discover_loader_plugins()
        }

        # loop all returned repres from repre_context dict
        for repre in plate_repres:
            loader_name = (
                repre.get("batch_group_loader_name")
                or self.default_loader
            )

            loader_plugin = loaders_by_name.get(loader_name)
            if not loader_plugin:
                self.log.warning(
                    "Unsupported loader for representation: %r ."
                    "Loader %s is unknown.",
                    repre["id"],
                    loader_name,
                )
                continue

            repre_context = get_representation_context(
                instance.data["projectEntity"]["name"],
                repre["id"],
            )
            task_workdir = self._get_shot_task_dir_path(instance)
            self.log.debug("Task work dir: %s", task_workdir)

            try:
                load_with_repre_context(
                    loader_plugin,
                    repre_context,
                    data={
                        "workdir": task_workdir,
                        "batch": bgroup
                    }
                )
            except IncompatibleLoaderError as error:
                self.log.error(
                    "Failed to load representaton %r with loader %s: %r",
                    repre["id"],
                    loader_name,
                    error
                )
                raise

            # TODO: investigate, only available from 2026.2 ?
            # Update resulting openclip to latest version.
            # FI-00398 Python: Possibility to change the Open Clip version
            #ops = opc.clip.format_specific_options
            #ops.refresh()
            #available_versions = ops.versions

    def _get_shot_task_dir_path(self, instance):
        task_data = instance.data["attachToTask"]
        project_entity = instance.data["projectEntity"]
        folder_entity = instance.data["folderEntity"]
        task_entity = ayon_api.get_task_by_name(
            project_entity["name"],
            folder_entity["id"],
            task_data["task_name"],
        )
        anatomy = instance.context.data["anatomy"]
        project_settings = instance.context.data["project_settings"]

        return get_workdir(
            project_entity,
            folder_entity,
            task_entity,
            "flame",
            anatomy=anatomy,
            project_settings=project_settings
        )


    def update_repre_entity(self, instance, bgroup):
        staging_dir = self.staging_dir(instance)
        repre = instance.data["published_representations"][0]

        ayfapi.save_as_consolidated_json(
            bgroup,
            output_json_file,
            staging_dir,
        )
        self.log.info(
            "Erase updated batchgroup %s as %s json file.",
            bgroup.name,
            output_json_file,
        )

        file_data.update(
            {
                "hash": source_hash(path),
                "size": os.path.getsize(path),
            }
        )
        op_session = OperationsSession()
        op_session.update_entity(
            instance.data["projectEntity"]["name"],
            "representation",
            repre["id"],
            {"files": file_data},
        )

        op_session.commit()
        self.log.info("Updated batchgroup representation.")
