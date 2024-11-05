# -*- coding: utf-8 -*-
"""Creator plugin for creating workfiles."""
import json
from xml.etree import ElementTree as ET

from ayon_core.pipeline import (
    AutoCreator,
    CreatedInstance,
)

from adsk.libwiretapPythonClientAPI import (
    WireTapClient,
    WireTapServerHandle,
    WireTapNodeHandle,
    WireTapStr
)

import ayon_flame.api as flapi


class CreateWorkfile(AutoCreator):
    """Workfile auto-creator."""
    settings_category = "flame"

    identifier = "io.ayon.creators.flame.workfile"
    label = "Workfile"
    product_type = "workfile"
    icon = "fa5.file"
    default_variant = "Main"

    # https://forums.autodesk.com/t5/flame-forum/store-persistent-variable-with-flame-project/td-p/9437717
    _METADATA_KEY = "Nickname"

    @classmethod
    def _get_project_metadata_handle(cls):
        """ Initialize project metadata setup.

        Returns:
            object. Flame wiretap handle for current project
        """
        current_project = flapi.get_current_project()

        wiretap_client = WireTapClient()
        wiretap_client.init()

        server = WireTapServerHandle("localhost:IFFFS")
        project_node_handle = WireTapNodeHandle(server, "/projects/{current_project.name}")
        return project_node_handle

    @classmethod
    def _get_project_metadata(cls):
        """ Returns the metadata stored at current project.

        Returns:
            xml.etree.ElementTree. The project metadata data.
        """
        project_node_handle = cls._get_project_metadata_handle()
        metadata = WireTapStr()
        project_node_handle.getMetaData("XML", "", 1, metadata)
        return ET.fromstring(metadata.c_str())

    @classmethod
    def _dump_instance_data(cls, data):
        """ Dump instance data into AyonData project tag.

        Args:
            data (dict): The data to push to the project tag.
        """
        metadata = cls._get_project_metadata()
        nickname_entry, = metadata.findall(cls._METADATA_KEY)
        nickname_entry.text = json.dumps(data)

    @classmethod
    def _load_instance_data(cls):
        """ Returns the data stored in AyonData project tag if any.

        Returns:
            dict. The metadata instance data.
        """
        metadata = cls._get_project_metadata()
        nickname_entry, = metadata.findall(cls._METADATA_KEY)
        return json.loads(nickname_entry.text) if nickname_entry.text else {}

    def _create_new_instance(self):
        """Create a new workfile instance.

        Returns:
            dict. The data of the instance to be created.
        """
        variant = self.default_variant
        project_name = self.create_context.get_current_project_name()
        folder_path = self.create_context.get_current_folder_path()
        task_name = self.create_context.get_current_task_name()
        host_name = self.create_context.host_name

        folder_entity = self.create_context.get_current_folder_entity()
        task_entity = self.create_context.get_current_task_entity()

        product_name = self.get_product_name(
            project_name,
            folder_entity,
            task_entity,
            self.default_variant,
            host_name,
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

    def create(self, options=None):
        """Auto-create an instance by default."""
        instance_data = self._load_instance_data()
        if instance_data:
            return

        self.log.info("Auto-creating workfile instance...")
        data = self._create_new_instance()
        current_instance = CreatedInstance(
            self.product_type, data["productName"], data, self)
        self._add_instance_to_context(current_instance)

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
