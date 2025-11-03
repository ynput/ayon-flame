import contextlib
import copy
import os
from pprint import pformat

import ayon_flame.api as ayfapi
import pyblish.api
from ayon_core.pipeline.workfile import get_workdir


class ExtractBatchgroup(pyblish.api.InstancePlugin):
    """Extract Batchgroup Product data."""

    order = pyblish.api.CollectorOrder + 0.496  # Testing order
    label = "Extract Batchgroup"
    hosts = ["flame"]
    families = ["batchgroup"]

    def process(self, instance):

        attach_to_task = instance.data["attachToTask"]
        output_node_properties = instance.data["outputNodeProperties"]

        # update task in anatomy data
        task_anatomy_data = self._get_anatomy_data_with_current_task(
            instance, attach_to_task)

        task_workdir = self._get_shot_task_dir_path(
            instance, task_anatomy_data)
        self.log.debug(f"__ task_workdir: {task_workdir}")


        # create or get already created batch group
        bgroup = self._get_batch_group(instance)

        write_pref_data = self._get_write_node_prefs(
            task_workdir,
            task_anatomy_data,
            output_node_properties,
        )

        # add batch group content
        all_batch_nodes = self._add_nodes_to_batch_with_links(
            bgroup, write_pref_data)

        for name, node in all_batch_nodes.items():
            self.log.debug(f"name: {name}, dir: {dir(node)}")
            self.log.debug(f"__ node.attributes: {node.attributes}")

    def _add_nodes_to_batch_with_links(
        self,
        batch_group,
        write_pref_data
    ):
        batch_nodes = [
            {
                "type": "comp",
                "properties": {},
                "id": "comp_node01"
            },
            {
                "type": "Write File",
                "properties": write_pref_data,
                "id": "write_file_node01"
            }
        ]
        batch_links = [
            {
                "from_node": {
                    "id": "comp_node01",
                    "connector": "Result"
                },
                "to_node": {
                    "id": "write_file_node01",
                    "connector": "Front"
                }
            }
        ]

        # add nodes into batch group
        return ayfapi.create_batch_group_content(
            batch_nodes, batch_links, batch_group)

    def _get_batch_group(self, instance):
        frame_start = instance.data["frameStart"]
        frame_end = instance.data["frameEnd"]
        handle_start = instance.data["handleStart"]
        handle_end = instance.data["handleEnd"]
        frame_duration = (frame_end - frame_start) + 1
        folder_path = instance.data["folderPath"]

        batchgroup_name = folder_path.replace("/", "_")

        batch_data = {
            "schematic_reels": [
                "AYON_LoadedReel"
            ],
            "handleStart": handle_start,
            "handleEnd": handle_end
        }
        self.log.debug(f"__ batch_data: {pformat(batch_data)}")

        # check if the batch group already exists
        bgroup = ayfapi.get_batch_group_from_desktop(batchgroup_name)

        if not bgroup:
            self.log.info(
                "Creating new batch group: {}".format(batchgroup_name))
            # create batch with utils
            bgroup = ayfapi.create_batch_group(
                batchgroup_name,
                frame_start,
                frame_duration,
                **batch_data
            )

        else:
            self.log.info(
                "Updating batch group: {}".format(batchgroup_name))
            # update already created batch group
            bgroup = ayfapi.create_batch_group(
                batchgroup_name,
                frame_start,
                frame_duration,
                update_batch_group=bgroup,
                **batch_data
            )

        return bgroup

    @staticmethod
    def _get_anatomy_data_with_current_task(instance, task_data):
        anatomy_data = copy.deepcopy(instance.data["anatomyData"])
        task_name = task_data["task_name"]
        task_type = task_data["task_type"]
        anatomy_obj = instance.context.data["anatomy"]

        # update task data in anatomy data
        project_task_types = anatomy_obj["tasks"]
        task_code = project_task_types.get(task_type, {}).get("shortName")
        anatomy_data.update({
            "task": {
                "name": task_name,
                "type": task_type,
                "short": task_code
            }
        })
        return anatomy_data

    def _get_write_node_prefs(
        self,
        task_workdir,
        task_anatomy_data,
        output_node_properties,
    ):

        # TODO: this might be done with template in settings
        render_dir_path = os.path.join(
            task_workdir, "render", "flame")

        if not os.path.exists(render_dir_path):
            os.makedirs(render_dir_path, mode=0o777)

        # TODO: add most of these to `imageio/flame/batch/write_node`
        name = "{project[code]}_{folder[name]}_{task[name]}".format(
            **task_anatomy_data
        )
        self.log.debug(f"Extracting batch group for task {name}")

        # need to make sure the order of keys is correct
        properties = {
            "name": name,
            # The path attribute where the rendered clip is exported
            # /path/to/file.[0001-0010].exr
            "media_path": render_dir_path,
            # name of file represented by tokens
            "media_path_pattern": (
                "<name>_v<iteration###>/<name>_v<iteration###>.<frame><ext>"),
            # The Create Open Clip attribute of the Write File node.
            # Determines if an Open Clip is created by the Write File node.
            "create_clip": True,
            # The Include Setup attribute of the Write File node.
            # Determines if a Batch Setup file is created by the Write File
            # node.
            "include_setup": True,
            # The path attribute where the Open Clip file is exported by
            # the Write File node.
            "create_clip_path": "<name>",
            # The path attribute where the Batch setup file
            # is exported by the Write File node.
            "include_setup_path": "./<name>_v<iteration###>",
            # The file type for the files written by the Write File node.
            # Setting this attribute also overwrites format_extension,
            # bit_depth and compress_mode to match the defaults for
            # this file type.
            "file_type": "OpenEXR",
            # The file extension for the files written by the Write File node.
            # This attribute resets to match file_type whenever file_type
            # is set. If you require a specific extension, you must
            # set format_extension after setting file_type.
            "format_extension": "exr",
            # The bit depth for the files written by the Write File node.
            # This attribute resets to match file_type whenever file_type is
            # set.
            "bit_depth": "16",
            # The compressing attribute for the files exported by the Write
            # File node. Only relevant when file_type in 'OpenEXR', 'Sgi',
            # 'Tiff'
            "compress": True,
            # The compression format attribute for the specific File Types
            # export by the Write File node. You must set compress_mode
            # after setting file_type.
            "compress_mode": "DWAB",
            # The frame index mode attribute of the Write File node.
            # Value range: `Use Timecode` or `Use Start Frame`
            "frame_index_mode": "Use Start Frame",
            "frame_padding": 6,
            # The versioning mode of the Open Clip exported by the Write File
            # node.
            # Only available if create_clip = True.
            "version_mode": "Follow Iteration",
            "version_name": "v<version>",
            "version_padding": 3
        }
        # update properties from settings override
        for settings in output_node_properties:
            value = settings["value"]

            # convert to int if it is possible
            with contextlib.suppress(ValueError):
                value = int(value)

            properties[settings["name"]] = value

        return properties

    @staticmethod
    def _get_shot_task_dir_path(instance, anatomy_data):
        # TODO: does this already exists at future context?
        project_entity = instance.data["projectEntity"]
        folder_entity = instance.data["folderEntity"]
        # faking at this moment nonexistent task entity
        task_entity = {
            "name": anatomy_data["task"]["name"],
            "taskType": anatomy_data["task"]["type"]
        }
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
