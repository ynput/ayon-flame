"""Launch workfile of `startup/AYON_in_flame.py` and the Workfiles tools."""

import flame
import pytest

from ayon_flame.api import batch_utils, editorial_workfile, menu, pipeline

from helpers import (
    SHOT_PATH,
    SHOT_TASK,
    add_note,
    get_node,
    open_in_timeline,
    wait_for,
    workfile_path,
)


@pytest.fixture
def launch_env(monkeypatch):
    """Set the environment the launcher gives Flame for a last workfile."""

    def _set(filepath, open_last=True, show_tool=False):
        monkeypatch.setenv("AYON_LAST_WORKFILE", filepath)
        monkeypatch.setenv("AVALON_OPEN_LAST_WORKFILE", str(int(open_last)))
        monkeypatch.setenv("AYON_WORKFILE_TOOL_ON_START", str(int(show_tool)))

    return _set


@pytest.fixture
def workfiles_tools():
    """Close the Workfiles tool windows a test showed."""
    yield menu._WORKFILES_TOOLS
    for tool in menu._WORKFILES_TOOLS.values():
        tool.close()
        tool.deleteLater()
    menu._WORKFILES_TOOLS.clear()


def test_launch_opens_last_batch_workfile(
    startup_hook, launch_env, batch_group, shot_context
):
    folder_entity, task_entity = shot_context
    batch_host = pipeline.FlameBatchHost()
    add_note(batch_group, "from_last_workfile")
    path = workfile_path(batch_host, folder_entity, task_entity, 1)
    batch_host.save_workfile_with_context(
        path, folder_entity, task_entity, version=1
    )
    launch_env(path)

    startup_hook.open_launch_workfile()

    assert flame.batch.name.get_value() == batch_utils.get_task_batch_name(
        SHOT_PATH, SHOT_TASK
    )
    assert get_node(flame.batch, "from_last_workfile") is not None
    assert batch_host.get_current_workfile() == path


def test_launch_opens_last_editorial_workfile(
    startup_hook, launch_env, make_sequence, shot_context, monkeypatch
):
    monkeypatch.setattr(editorial_workfile, "save_flame_project", lambda: None)
    folder_entity, task_entity = shot_context
    host = pipeline.FlameHost()
    saved = make_sequence()
    open_in_timeline(saved)
    path = workfile_path(host, folder_entity, task_entity, 1)
    host.save_workfile_with_context(
        path, folder_entity, task_entity, version=1
    )
    open_in_timeline(make_sequence())
    editorial_workfile.set_current_editorial_workfile(None)
    launch_env(path)

    startup_hook.open_launch_workfile()

    uid = saved.uid.get_value()

    def _saved_is_open():
        opened = editorial_workfile.get_timeline_sequence()
        return opened is not None and opened.uid.get_value() == uid

    assert wait_for(_saved_is_open), "The saved sequence is not open."
    assert host.get_current_workfile() == path


def test_launch_without_workfile_opens_nothing(
    startup_hook, launch_env, batch_group, tmp_path
):
    launch_env(str(tmp_path / "missing_v001.flamebatch"))
    current = flame.batch.uid.get_value()

    startup_hook.open_launch_workfile()

    assert flame.batch.uid.get_value() == current


def test_launch_shows_workfiles_tool(
    startup_hook, launch_env, workfiles_tools, tmp_path
):
    launch_env(
        str(tmp_path / "missing_v001.flameedit"),
        open_last=False, show_tool=True,
    )

    startup_hook.open_launch_workfile()

    assert wait_for(lambda: workfiles_tools["editorial"].isVisible())
    assert "batch" not in workfiles_tools


def test_workfiles_tools_have_their_own_window(workfiles_tools, batch_group):
    menu.show_batch_workfiles()
    menu.show_editorial_workfiles()
    batch_tool = workfiles_tools["batch"]

    assert wait_for(lambda: batch_tool.isVisible())
    assert workfiles_tools["editorial"] is not batch_tool

    menu.show_batch_workfiles()

    assert workfiles_tools["batch"] is not batch_tool, (
        "The window is created again, its selection starts from the context."
    )
