from typing import Optional, List, Dict, Any

import pathlib
import json
import tempfile

from ayon_core.lib import Logger

import flame


log = Logger.get_logger(__name__)


def create_batch(
    name,
    frame_start: int,
    frame_duration: int,
    handle_start: int = 0,
    handle_end: int = 0,
) -> flame.PyBatch:
    """Create Batch Group in active project's Desktop
    """
    frame_start -= handle_start
    frame_duration += handle_start + handle_end

    return flame.batch.create_batch_group(
        name,
        start_frame=frame_start,
        duration=frame_duration,
    )


def update_batch(
    batch: flame.PyBatch,
    name: Optional[str] = None,
    frame_start: Optional[int] = None,
    frame_duration: Optional[int] = None,
    handle_start: int = 0,
    handle_end: int = 0,
) -> flame.PyBatch:
    """ Update provided batch with new values.
    """
    if name:
        batch.name = name
    if frame_start is not None:
        batch.start_frame = frame_start
    if frame_duration is not None:
        frame_duration += handle_start + handle_end
        batch.duration = frame_duration

    return batch


def add_reels_to_batch(
    batch: flame.PyBatch,
    reels: Optional[List[str]] = None,
    shelf_reels: Optional[List[str]] = None,
):
    """ Add reels and shelf reels to batch.
    """
    if reels:
        existing_reel_names = [
            reel.name.get_value()
            for reel in batch.reels
        ]
        for new_reel in reels:
            if new_reel not in existing_reel_names:
                batch.create_reel(new_reel)

    if shelf_reels:
        existing_shelf_reel_names = [
            reel.name.get_value()
            for reel in batch.shelf_reels
        ]
        for new_sr in shelf_reels:
            if new_sr not in existing_shelf_reel_names:
                batch.create_shelf_reel(new_sr)


def edit_batch_group_content(
    batch: flame.PyBatch,
    batch_nodes: List[Dict[str, Any]],  # each dict is node definition
    batch_links: List[Dict[str, Any]]   # each dict is new link definition
) -> Dict[str, flame.PyNode]:
    all_batch_nodes = {
        node.name.get_value(): node
        for node in batch.nodes
    }
    for node in batch_nodes:

        # Node to edit already exists, update existing batch node
        node_name = node["properties"].pop("name", None) or node["id"]
        if all_batch_nodes.get(node_name):
            batch_node = all_batch_nodes[node_name]

        # create new batch node, otherwise
        else:
            batch_node = batch.create_node(node["type"])
            batch_node.name.set_value(node_name)
            all_batch_nodes[node["id"]] = batch_node

        # set attributes found in node props
        for key, value in node["properties"].items():
            if hasattr(batch_node, key):
                setattr(batch_node, key, value)
            else:
                log.warning(
                    f"Attribute {key} not found on batch node {node_name}"
                )

    # link nodes to each other
    for link in batch_links:
        _from_n, _to_n = link["from_node"], link["to_node"]

        if(
            all_batch_nodes.get(_from_n["id"])
            and all_batch_nodes.get(_to_n["id"])
        ):
            batch.connect_nodes(
                all_batch_nodes[_from_n["id"]], _from_n["connector"],
                all_batch_nodes[_to_n["id"]], _to_n["connector"]
            )
        else:
            log.warning(
                f"Failed to link node(s) {_from_n['id']} to {_to_n['id']}."
            )

    batch.organize()  # sort batch nodes
    return all_batch_nodes


def get_batch_from_workspace(
    name: str,
    workspace: Optional[flame.PyWorkspace] = None
) -> Optional[flame.PyBatch]:
    """ Get batch group from name and workspace.
    """
    if workspace is None:
        project = flame.project.current_project
        workspace = project.current_workspace

    desktop = workspace.desktop
    for batchgroup in desktop.batch_groups:
        if batchgroup.name.get_value() == name:
            return batchgroup

    return None


def save_batch_as_consolidated_json(
    batch: flame.PyBatch,
    filepath: str,
    temporary_folder: Optional[str] = None,  # where flame run native export
) -> str:
    """ Export batch as a consolidated json file.
    """
    tmp = tempfile.TemporaryDirectory() if temporary_folder is None else None
    tmp_dir = pathlib.Path(tmp.name if tmp else temporary_folder)

    try:
        bgroup_file = tmp_dir / f"{batch.name}.batch"
        batch.save_setup(str(bgroup_file))

        if not tmp_dir.is_dir():
            raise RuntimeError(
                f"Unable to save batchgroup to folder: {tmp_dir}."
            )

        # Concatenate all intermediary files as 1 single consolidated JSON.
        json_output = {}
        for file_path in tmp_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(tmp_dir)
                try:
                    content = file_path.read_text(encoding="utf-8")
                    json_output[str(relative_path)] = content
                except Exception as error:
                    raise RuntimeError(
                        f"Could not encode file {file_path} as text: {error}"
                    ) from error

        with open(filepath, "w") as file_handler:
            json.dump(json_output, file_handler, indent=4)

    finally:
        # Delete temporary directory if created.
        if tmp is not None:
            tmp.cleanup()

    return filepath


def load_batch_from_consolidated_json(
    filepath: str,
    name: Optional[str] = None,
    temporary_folder: Optional[str] = None,
) -> Optional[flame.PyBatch]:
    """ Load a batch from a consolidated json file.
    """
    with open(filepath, "r", encoding="utf-8") as file_:
        data = json.load(file_)

    tmp = tempfile.TemporaryDirectory() if not temporary_folder else None
    tmp_dir = pathlib.Path(tmp.name if tmp else temporary_folder)

    try:
        batch_file = None
        for relative_file, content in data.items():
            file_path = tmp_dir / relative_file
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

            if relative_file.endswith(".batch"):
                batch_file = relative_file

        if batch_file is None:
            raise ValueError(
                f"No valid batch found in consolidated json: {filepath}"
            )

        flame.batch.load_setup(str(tmp_dir / batch_file))

        # Restore the batch group name from the provided name
        # or use the .batch filename stem otherwise.
        batch_name = name or pathlib.Path(batch_file).stem
        flame.batch.name = batch_name

        return flame.batch

    finally:
        if tmp is not None:
            tmp.cleanup()
