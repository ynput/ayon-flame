from typing import Optional, List, Dict, Any

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
    workspace: Optional[flame.Workspace] = None
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
