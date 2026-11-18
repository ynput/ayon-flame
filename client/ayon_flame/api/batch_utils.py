from typing import Optional, List, Dict, Any

import base64
import pathlib
import json
import os
import tempfile

from ayon_core.lib import Logger

import flame


log = Logger.get_logger(__name__)

# Helps to identify AYON-managed nodes.
AYON_NOTE_MARKER = "__ayon__"

# Name of the hidden Note node used to embed instance data inside the batch.
_METADATA_NODE_NAME = "AYON_metadata"


def read_node_metadata(node: flame.PyNode) -> Optional[Dict[str, Any]]:
    """ Read AYON instance data from a node's note attribute.
    """
    try:
        raw = node.note.get_value()
    except Exception:
        return None

    if not raw:
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    return data if data.get(AYON_NOTE_MARKER) else None


def write_node_metadata(node: flame.PyNode, data: Dict[str, Any]):
    """ Write AYON instance data into a node's note attribute."""
    payload = dict(data)
    payload[AYON_NOTE_MARKER] = True
    node.note = json.dumps(payload)
    node.note_collapsed = True


def clear_node_metadata(node: flame.PyNode):
    """ Remove AYON instance data from a node's note attribute."""
    node.note = ""


def create_batch(
    name,
    frame_start: int,
    frame_duration: int,
    handle_start: int = 0,
    handle_end: int = 0,
) -> flame.PyBatch:
    """ Create Batch Group in active project's Desktop
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
        batch.start_frame = frame_start - handle_start
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


def get_task_batch_name(folder_path: str, task_name: str) -> str:
    return f"{folder_path}_{task_name}".replace("/", "_").strip("_")


def get_unique_batch_name(name: str) -> str:
    existing = {
        bg.name.get_value()
        for bg in flame.project.current_project.current_workspace
            .desktop.batch_groups
    }
    if name not in existing:
        return name

    counter = 2
    while f"{name} ({counter})" in existing:
        counter += 1
    return f"{name} ({counter})"


def get_write_node_from_batch(
    batch: flame.PyBatch,
    name: str,
) -> Optional[flame.PyWriteFileNode]:
    for node in batch.nodes:
        if (
            isinstance(node, flame.PyWriteFileNode)
            and node.name.get_value() == name
        ):
            return node

    return None


def set_write_node_output_dir(
    write_node: flame.PyWriteFileNode,
    directory: str,
):
    """Render Write File node output directly into directory.

    Sub-folders from the media path pattern are dropped,
    only the file name part is kept.
    """
    pattern = write_node.media_path_pattern.get_value()
    write_node.media_path = directory
    write_node.media_path_pattern = pattern.rsplit("/", 1)[-1]


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
        batch_name = batch.name.get_value()
        bgroup_file = tmp_dir / f"{batch_name}.batch"
        batch.save_setup(str(bgroup_file))

        if not tmp_dir.is_dir():
            raise RuntimeError(
                f"Unable to save batchgroup to folder: {tmp_dir}."
            )

        # Concatenate all intermediary files as 1 single consolidated JSON.
        # Binary files (e.g. .mx presets are not utf-8) are base64-encoded
        # using a "__b64__:" prefix so we can deserialize them.
        json_output = {}
        for file_path in tmp_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(tmp_dir)
                try:
                    content = file_path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, ValueError):
                    content = "__b64__:" + base64.b64encode(
                        file_path.read_bytes()
                    ).decode("ascii")
                json_output[str(relative_path)] = content

        with open(filepath, "w") as file_handler:
            json.dump(json_output, file_handler, indent=4)

    finally:
        # Delete temporary directory if created.
        if tmp is not None:
            tmp.cleanup()

    return filepath


def get_current_batch() -> flame.PyBatch:
    """ Return the current flame.batch object or None.
    """
    try:
        return flame.batch
    except Exception as error:
        raise RuntimeError(
            "Cannot find current batch from context."
        ) from error


def get_metadata_node(
        batch: Optional[flame.PyBatch] = None,
        create: bool = False
    ) -> Optional[flame.PyNode]:
    """ Find or create the AYON metadata Note node in the current batch.
    """
    batch = batch or get_current_batch()
    for node in batch.nodes:
        if node.name.get_value() == _METADATA_NODE_NAME:
            return node

    if not create:
        return None

    node = batch.create_node("Note")
    node.name.set_value(_METADATA_NODE_NAME)
    return node


def get_batch_product_data(
    batch: Optional[flame.PyBatch] = None
) -> Optional[Dict[str, Any]]:
    """ Return the Batch product data stored in the batch metadata note."""
    node = get_metadata_node(batch=batch)
    if node is None:
        return None
    return read_node_metadata(node)


def get_batch_products_context(
    batch: Optional[flame.PyBatch] = None
) -> Optional[Dict[str, str]]:
    """ Return the folder path and task name of the batch AYON products.

    The Batch product of the metadata note is preferred, the Batch Render
    products of Write File nodes are used when it is missing.

    Returns:
        Optional[Dict[str, str]]: 'folder_path' and 'task_name' or None
            when the batch group has no AYON product with a context.
    """
    try:
        batch = batch or get_current_batch()
    except RuntimeError:
        return None

    products_data = [get_batch_product_data(batch)]
    products_data.extend(
        read_node_metadata(node)
        for node in batch.nodes
        if isinstance(node, flame.PyWriteFileNode)
    )
    for data in products_data:
        if data and data.get("folderPath") and data.get("task"):
            return {
                "folder_path": data["folderPath"],
                "task_name": data["task"],
            }
    return None


# Batch workfile saved or opened for each batch group. The key is the Flame
# project and the batch group uid. The value keeps the AYON folder and task
# of the file, and its size and date. It is not stored in the batch: a path
# in a note went stale and was saved with the file.
# The links are kept in the Flame project folder after each Flame project
# save, so they survive a Flame restart. Flame has just saved every batch
# group then: after a crash, a batch group holds at least what AYON last
# wrote to its kept workfile.
# An AYON write removes the kept link of its batch group until the next
# Flame project save.
_SESSION_BATCH_WORKFILES: Dict[tuple, dict] = {}


def _get_session_batch_key(batch: flame.PyBatch) -> tuple:
    return (flame.project.current_project.name, batch.uid.get_value())


def _get_kept_links_folder() -> str:
    """ Return the folder of the kept links of the current Flame project."""
    return os.path.join(
        flame.project.current_project.project_folder,
        "ayon",
        "batch_workfiles",
    )


def _get_kept_link_path(uid: str) -> str:
    return os.path.join(_get_kept_links_folder(), f"{uid}.json")


def _remove_kept_link(key: tuple):
    """ Remove the kept link of the batch group, if any.

    A failure is only logged. A raise would report a good save or open as
    failed.
    """
    filepath = _get_kept_link_path(key[1])
    try:
        os.remove(filepath)
    except FileNotFoundError:
        pass
    except OSError:
        log.warning(
            "Unable to remove the kept link %r.", filepath, exc_info=True
        )


def _get_link(key: tuple) -> Optional[dict]:
    """ Return the link of the batch group, from memory or its kept file.

    A kept file is loaded into memory. A missing or bad kept file gives
    None, a bad one is logged.
    """
    data = _SESSION_BATCH_WORKFILES.get(key)
    if data:
        return data

    filepath = _get_kept_link_path(key[1])
    try:
        with open(filepath, "r") as stream:
            data = json.load(stream)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        log.warning(
            "Unable to read the kept link %r.", filepath, exc_info=True
        )
        return None

    stat = data.get("stat") if isinstance(data, dict) else None
    if (
        not isinstance(data, dict)
        or not all(
            isinstance(data.get(name), str)
            for name in ("path", "folder_path", "task_name")
        )
        or not isinstance(stat, list)
        or len(stat) != 2
        or not all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in stat
        )
    ):
        log.warning("Kept link %r is not valid, ignoring it.", filepath)
        return None

    data = {
        "path": data["path"],
        "folder_path": data["folder_path"],
        "task_name": data["task_name"],
        "stat": tuple(stat),
    }
    _SESSION_BATCH_WORKFILES[key] = data
    return data


def set_session_batch_workfile(
    batch: flame.PyBatch, filepath: str, folder_path: str, task_name: str
):
    """ Remember the workfile saved or opened for the batch group.

    It follows the batch group uid. A renamed batch group keeps it. A batch
    group created again, or replaced with Batch Load And Replace, does not.
    It survives a Flame restart only once a Flame project save kept it, see
    'keep_session_batch_workfiles'.

    The size and date of the file are kept too, so a save made elsewhere
    is noticed. Call it right after AYON wrote or opened the file.
    """
    filepath = os.path.normpath(filepath)
    key = _get_session_batch_key(batch)
    # Flame has not saved the batch group since this write or open. After
    # a crash it would come back older than the file.
    _remove_kept_link(key)
    stat = os.stat(filepath)
    _SESSION_BATCH_WORKFILES[key] = {
        "path": filepath,
        "folder_path": folder_path,
        "task_name": task_name,
        "stat": (stat.st_mtime_ns, stat.st_size),
    }


def keep_session_batch_workfiles():
    """ Keep the batch group links of the current Flame project on disk.

    Call it right after a Flame project save. Flame has just saved every
    batch group, each one holds at least what AYON last wrote to its
    workfile. The links then survive a Flame restart.

    Each link keeps the size and date of the last AYON write or open, not
    the ones of now. A file saved elsewhere is still noticed after a
    restart. Failures are logged, never raised.
    """
    try:
        project_name = flame.project.current_project.name
        links = [
            (uid, data)
            for (link_project, uid), data in _SESSION_BATCH_WORKFILES.items()
            if link_project == project_name
        ]
        # No folder in a Flame project without Batch workfiles.
        if not links:
            return
        os.makedirs(_get_kept_links_folder(), exist_ok=True)
    except Exception:
        log.warning("Unable to keep the Batch workfile links.", exc_info=True)
        return

    for uid, data in links:
        filepath = _get_kept_link_path(uid)
        tmp_path = f"{filepath}.{os.getpid()}.tmp"
        try:
            with open(tmp_path, "w") as stream:
                json.dump(data, stream)
            os.replace(tmp_path, filepath)
        except Exception:
            log.warning(
                "Unable to keep the link %r.", filepath, exc_info=True
            )
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _get_file_stat(filepath: str) -> Optional[tuple]:
    """ Return the date and size of the file, None when it is missing."""
    try:
        stat = os.stat(filepath)
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def get_session_batch_workfile(
    batch: flame.PyBatch, folder_path: str, task_name: str
) -> Optional[str]:
    """ Return the workfile saved or opened for the batch group, if any.

    Args:
        batch (flame.PyBatch): Batch group.
        folder_path (str): Folder path of the products of the batch group.
        task_name (str): Task name of the products of the batch group.

    Returns:
        Optional[str]: Path of the workfile when it belongs to the given
            task, None otherwise. None also when the file is missing or was
            saved elsewhere since AYON last saved or opened it.
    """
    data = _get_link(_get_session_batch_key(batch))
    # Another batch group, Flame or machine may have saved the file.
    # Saving over it would lose that work.
    if (
        not data
        or data["folder_path"] != folder_path
        or data["task_name"] != task_name
        or _get_file_stat(data["path"]) != data["stat"]
    ):
        return None
    return data["path"]


def pop_batch_workfile_saved_elsewhere(
    batch: flame.PyBatch, folder_path: str, task_name: str
) -> Optional[str]:
    """ Unlink the batch group when its workfile was saved elsewhere.

    Args:
        batch (flame.PyBatch): Batch group.
        folder_path (str): Folder path of the products of the batch group.
        task_name (str): Task name of the products of the batch group.

    Returns:
        Optional[str]: Path of the workfile linked for the given task when
            it was saved elsewhere since AYON last saved or opened it. None
            otherwise, and when the file is missing.
    """
    key = _get_session_batch_key(batch)
    data = _get_link(key)
    if (
        not data
        or data["folder_path"] != folder_path
        or data["task_name"] != task_name
    ):
        return None
    stat = _get_file_stat(data["path"])
    if stat is None or stat == data["stat"]:
        return None
    del _SESSION_BATCH_WORKFILES[key]
    _remove_kept_link(key)
    return data["path"]


def get_instances_batches(instances) -> Dict[str, flame.PyBatch]:
    """ Return batch groups of active Batch menu instances, by name.

    Batch groups which are not found in the workspace are skipped.
    """
    batches = {}
    for instance in instances:
        if (
            instance.data.get("flame_context") != "FlameMenuBatch"
            or not instance.data.get("publish", True)
            or not instance.data.get("active", True)
        ):
            continue

        batch_name = instance.data.get("batch_name")
        if not batch_name or batch_name in batches:
            continue

        batch = get_batch_from_workspace(batch_name)
        if batch is not None:
            batches[batch_name] = batch
    return batches


def set_batch_products_context(
    batch: flame.PyBatch, folder_path: str, task_name: str
) -> int:
    """ Set the folder and task of every AYON product of the batch group.

    The Batch product and the Batch Render products keep the context they
    were created in, so a workfile saved into, or opened in, another task
    would keep the context of the previous one.

    Returns:
        int: Number of products that were moved to another context.
    """
    changed = 0
    for node in batch.nodes:
        data = read_node_metadata(node)
        if not data or "folderPath" not in data:
            continue

        if data["folderPath"] == folder_path and data.get("task") == task_name:
            continue

        data["folderPath"] = folder_path
        data["task"] = task_name
        write_node_metadata(node, data)
        changed += 1
    return changed


def set_instances_batch_name(batch: flame.PyBatch, batch_name: str):
    """ Set the batch group name saved in each AYON instance note.

    Publishing finds the batch group by this name, so a workfile opened
    under another name (' (2)' added for a taken one) must carry it.
    """
    for node in batch.nodes:
        data = read_node_metadata(node)
        if data and "batch_name" in data:
            data["batch_name"] = batch_name
            write_node_metadata(node, data)


def _get_safe_extracted_path(
    root: pathlib.Path, relative_file: str
) -> pathlib.Path:
    """ Return the path of a consolidated file, never outside of root.

    The keys of a consolidated json are file paths relative to its root,
    the document comes from a work folder, so absolute paths and '..' are
    refused instead of written wherever they point to.
    """
    file_path = (root / relative_file).resolve()
    if not file_path.is_relative_to(root.resolve()):
        raise ValueError(
            f"Consolidated file path is outside of its folder: "
            f"'{relative_file}'"
        )
    return file_path


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
            file_path = _get_safe_extracted_path(tmp_dir, relative_file)
            if not isinstance(content, str):
                raise ValueError(
                    f"Invalid content of '{relative_file}' in {filepath}"
                )
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if content.startswith("__b64__:"):
                file_path.write_bytes(base64.b64decode(content[8:]))
            else:
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
