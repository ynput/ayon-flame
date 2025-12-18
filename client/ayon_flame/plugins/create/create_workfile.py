# -*- coding: utf-8 -*-
"""Creator plugin for creating workfiles."""
import json
import os

from ayon_core.pipeline import (
    AutoCreator,
    CreatedInstance,
)

import ayon_flame.api as flapi


class CreateWorkfile(AutoCreator):
    """Workfile auto-creator."""
    settings_category = "flame"

    identifier = "io.ayon.creators.flame.workfile"
    label = "Workfile"
    product_type = "workfile"
    product_base_type = "workfile"
    icon = "fa5.file"
    default_variant = "Main"

    @staticmethod
    def _get_project_workfile_filepath():
        """
        Args:
            project_name (str): The project name.

        Returns:
            str. The path to the expected Json workfile.
        """
        project_name = flapi.get_current_project().name
        return os.path.join(
            os.environ["AYON_WORKDIR"],
            f"{project_name}.workfile"
        )

    def _dump_instance_data(self, data):
        """ Dump instance data into a side-car json file.

        Args:
            data (dict): The data to push to the project metadata.

        Returns:
            bool. Has the metadata been updated.
        """
        out_path = self._get_project_workfile_filepath()
        with open(out_path, "w", encoding="utf-8") as out_file:
            json.dump(data, out_file)

    def _load_instance_data(self):
        """ Returns the data stored in side-car json file if exists.

        Returns:
            dict. The workfile metadata data.
        """
        in_path = self._get_project_workfile_filepath()

        try:
            with open(in_path) as in_file:
                return json.load(in_file)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _create_new_instance(self):
        """Create a new workfile instance.

        Returns:
            dict. The data of the instance to be created.
        """
        variant = self.default_variant

        project_entity = self.create_context.get_current_project_entity()
        folder_entity = self.create_context.get_current_folder_entity()
        task_entity = self.create_context.get_current_task_entity()

        project_name = project_entity["name"]
        folder_path = folder_entity["path"]
        task_name = task_entity["name"]
        host_name = self.create_context.host_name

        product_name = self.get_product_name(
            project_name=project_name,
            project_entity=project_entity,
            folder_entity=folder_entity,
            task_entity=task_entity,
            variant=self.default_variant,
            host_name=host_name,
        )
        data = {
            "folderPath": folder_path,
            "task": task_name,
            "variant": variant,
        }
        data.update(
            self.get_dynamic_data(
                variant,
                task_name,
                folder_entity,
                project_name,
                host_name,
                False,
            )
        )
        self.log.info("Auto-creating workfile instance...")
        current_instance = CreatedInstance(
            self.product_type, product_name, data, self)
        self._add_instance_to_context(current_instance)
        return current_instance

    def create(self, options=None):
        """Auto-create an instance by default."""
        instance_data = self._load_instance_data()
        if instance_data:
            return

        self.log.info("Auto-creating workfile instance...")
        self._create_new_instance()

    def collect_instances(self):
        """Collect from timeline marker or create a new one."""
        data = self._load_instance_data()
        if not data:
            return

        instance = CreatedInstance(
            self.product_type, data["productName"], data, self
        )
        self._add_instance_to_context(instance)

    def update_instances(self, update_list):
        """Store changes in project metadata so they can be recollected.

        Args:
            update_list(List[UpdateData]): Gets list of tuples. Each item
                contain changed instance and its changes.
        """
        for created_inst, _ in update_list:
            data = created_inst.data_to_store()
            self._dump_instance_data(data)
