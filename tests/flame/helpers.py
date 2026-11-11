"""Helpers of the tests that run inside Flame."""

import importlib.util
import json
import os
import time

import ayon_api
import flame

from ayon_core.pipeline import Anatomy
from ayon_core.pipeline.template_data import get_template_data
from ayon_core.pipeline.workfile import get_workdir, get_workfile_template_key
from ayon_core.settings import get_project_settings

from ayon_flame import FLAME_ADDON_ROOT
from ayon_flame.api import batch_utils
from ayon_flame.constants import BATCH_CREATOR_IDENTIFIER

SHOT_PATH = "/shots/sq01/sh010"
SHOT_TASK = "compositing"
SHOT_OTHER_TASK = "paint"
EDIT_PATH = "/editorial"
EDIT_TASK = "edit"


_PLUGIN_MODULES = {}


def load_plugin_module(kind, filename):
    """Import a plugin file, plugins are not importable as modules."""
    path = os.path.join(FLAME_ADDON_ROOT, "plugins", kind, filename)
    if path not in _PLUGIN_MODULES:
        name = f"ayon_flame_test_{kind}_{os.path.splitext(filename)[0]}"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _PLUGIN_MODULES[path] = module
    return _PLUGIN_MODULES[path]


def workfile_path(host, folder_entity, task_entity, version, ext=None):
    """Return the path of a workfile version as the Workfiles tool does."""
    project_name = host.get_current_project_name()
    project_entity = ayon_api.get_project(project_name)
    settings = get_project_settings(project_name)
    anatomy = Anatomy(project_name, project_entity=project_entity)
    template_key = get_workfile_template_key(
        project_name, task_entity["taskType"], host.name,
        project_settings=settings,
    )
    template_data = get_template_data(
        project_entity, folder_entity, task_entity, host.name, settings
    )
    template_data["version"] = version
    template_data["ext"] = (
        ext or host.get_workfile_extensions()[0]
    ).lstrip(".")
    workdir = get_workdir(
        project_entity, folder_entity, task_entity, host.name,
        anatomy=anatomy, template_key=template_key,
        project_settings=settings,
    )
    file_template = anatomy.get_template_item("work", template_key, "file")
    return os.path.normpath(
        os.path.join(workdir, file_template.format_strict(template_data))
    )


def get_desktop():
    return flame.projects.current_project.current_workspace.desktop


def get_batch_groups():
    """Return the batch groups of the desktop by uid."""
    return {
        batch.uid.get_value(): batch for batch in get_desktop().batch_groups
    }


def get_batch_group_names():
    return [batch.name.get_value() for batch in get_desktop().batch_groups]


def add_note(batch, name, data=None):
    """Add a Note node, with AYON metadata when data is given."""
    node = batch.create_node("Note")
    node.name.set_value(name)
    if data is not None:
        batch_utils.write_node_metadata(node, data)
    return node


def add_write_node(batch, name, data=None):
    node = batch.create_node("Write File")
    node.name.set_value(name)
    if data is not None:
        batch_utils.write_node_metadata(node, data)
    return node


def get_node(batch, name):
    for node in batch.nodes:
        if node.name.get_value() == name:
            return node
    return None


def batch_product_data(folder_path, task_name, batch_name, **extra):
    """Data of a Batch product as its creator stores it."""
    data = {
        "productName": "workfileMain",
        "productType": "workfile",
        "productBaseType": "workfile",
        "variant": "Main",
        "folderPath": folder_path,
        "task": task_name,
        "batch_name": batch_name,
        "flame_context": "FlameMenuBatch",
        "creator_identifier": BATCH_CREATOR_IDENTIFIER,
    }
    data.update(extra)
    return data


def read_consolidated(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def batch_setup_text(path):
    """Return the '.batch' document of a consolidated Batch workfile."""
    data = read_consolidated(path)
    texts = [
        content for key, content in data.items() if key.endswith(".batch")
    ]
    assert texts, f"No '.batch' document in {path}"
    return "\n".join(texts)


def wait_for(predicate, timeout=10.0):
    """Wait for a condition, processing Qt events meanwhile."""
    from qtpy import QtWidgets

    deadline = time.time() + timeout
    while True:
        if predicate():
            return True
        if time.time() > deadline:
            return False
        QtWidgets.QApplication.processEvents()
        time.sleep(0.1)


def open_in_timeline(sequence):
    """Open a sequence in the Timeline, as the artist does."""
    sequence.open()
    flame.set_current_tab("Timeline")
    uid = sequence.uid.get_value()

    def _is_open():
        clip = flame.timeline.clip
        return clip is not None and clip.uid.get_value() == uid

    assert wait_for(_is_open), f"{sequence.name.get_value()} is not open"


class FakeInstance:
    """Pyblish instance stand-in for helpers reading 'instance.data'."""

    def __init__(self, **data):
        self.data = data
