import flame
import json
import os
import tempfile

from typing import Tuple

from ayon_core.pipeline import LoaderPlugin


class LoadBatchgroup(LoaderPlugin):
    product_types = {"workfile"}
    representations = {"*"}
    extensions = ("json",)

    label = "Load batchgroup"
    order = -10
    icon = "code-fork"
    color = "orange"

    @staticmethod
    def _extract_in_temp_dir(consolidated_file: str) -> Tuple[str]:
        """ Extract consolidated JSON file into temporary folder.
        """
        with open(consolidated_file, "r", encoding="utf-8") as file_:
            data = json.load(file_)

        temp_dir = tempfile.mkdtemp()
        batch_file = None
        for relative_file, content in data.items():
            # create sub-folder if needed
            parent_dir = os.path.dirname(relative_file)
            expected_parent_dir = os.path.join(temp_dir, parent_dir)
            if parent_dir and not os.path.exists(expected_parent_dir):
                os.makedirs(expected_parent_dir)

            # "extract" file content
            file_path = os.path.join(temp_dir, relative_file)
            with open(file_path, "w") as file_handler:
                file_handler.write(content)

            if relative_file.endswith(".batch"):
                batch_file = relative_file

        return temp_dir, batch_file

    def load(self, context, name=None, namespace=None, options=None):
        """Load asset via database

        Arguments:
            context (dict): Full parenthood of representation to load
            name (str, optional): Use pre-defined name
            namespace (str, optional): Use pre-defined namespace
            options (dict, optional): Additional settings dictionary
        """
        path = self.filepath_from_context(context)
        folder_path, batch_file_name = self._extract_in_temp_dir(path)
        full_path = os.path.join(folder_path, batch_file_name)

        desktop = flame.project.current_project.current_workspace.desktop
        new_batch_group = desktop.import_batch_group(full_path)

        #TODO: contenerize

    def update(self, container, context):
        """Update `container` to `representation`

        Args:
            container (avalon-core:container-1.0): Container to update,
                from `host.ls()`.
            context (dict): Update the container to this representation.

        """
        raise NotImplementedError("TODO")

    def remove(self, container):
        """Remove a container

        Arguments:
            container (avalon-core:container-1.0): Container to remove,
                from `host.ls()`.

        Returns:
            bool: Whether the container was deleted

        """
        raise NotImplementedError("TODO")
