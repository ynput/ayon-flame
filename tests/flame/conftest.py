"""Fixtures of the tests that run inside Flame.

The tests run in the dedicated AYON project started by
`tests/run_flame_tests.py`, in the Flame project of the same name. Every
batch group and sequence a test makes is deleted after it, the AYON session
and the Flame host state are restored. Workfiles of the test tasks are
deleted before each test.
"""

import copy
import glob
import os
import uuid

import ayon_api
import flame
import pytest

from ayon_core.pipeline import registered_host
from ayon_core.settings import get_project_settings

from ayon_flame.api import batch_utils, editorial_workfile, pipeline
from ayon_flame.api.lib import CTX

from helpers import (
    EDIT_PATH,
    EDIT_TASK,
    SHOT_OTHER_TASK,
    SHOT_PATH,
    SHOT_TASK,
    get_batch_groups,
    get_desktop,
    workfile_path,
)

_WORKFILE_PATTERNS = ("*.flamebatch", "*.flameedit", ".*.tmp")


def pytest_configure(config):
    expected = os.environ.get("AYON_FLAME_TEST_PROJECT")
    current = os.environ.get("AYON_PROJECT_NAME")
    if not expected or expected != current:
        pytest.exit(
            "Run the tests with `ayon run tests/run_flame_tests.py`, they "
            f"change the project '{current}' and its Flame project.",
            returncode=4,
        )


# --- AYON context -----------------------------------------------------------


@pytest.fixture(scope="session")
def project_name():
    return os.environ["AYON_PROJECT_NAME"]


def _get_context_entities(project_name, folder_path, task_name):
    folder_entity = ayon_api.get_folder_by_path(project_name, folder_path)
    assert folder_entity, f"Missing folder {folder_path}, run the runner."
    task_entity = ayon_api.get_task_by_name(
        project_name, folder_entity["id"], task_name
    )
    assert task_entity, f"Missing task {folder_path} {task_name}."
    return folder_entity, task_entity


@pytest.fixture(scope="session")
def shot_context(project_name):
    """Folder and task entities of the launch task."""
    return _get_context_entities(project_name, SHOT_PATH, SHOT_TASK)


@pytest.fixture(scope="session")
def other_task_context(project_name):
    """Folder and task entities of another task of the same shot."""
    return _get_context_entities(project_name, SHOT_PATH, SHOT_OTHER_TASK)


@pytest.fixture(scope="session")
def edit_context(project_name):
    return _get_context_entities(project_name, EDIT_PATH, EDIT_TASK)


@pytest.fixture(scope="session")
def project_settings(project_name):
    """Project settings with the settings of this checkout filled in.

    The server addon of the bundle can be older than this checkout.
    """
    settings = copy.deepcopy(get_project_settings(project_name))
    flame_settings = settings["flame"]
    flame_settings.setdefault("update_batch_workfile", {"enabled": True})
    flame_settings["publish"].setdefault(
        "ValidateEditorialWorkfileSaved",
        {"enabled": True, "optional": True, "active": True},
    )
    return settings


@pytest.fixture
def flame_settings(monkeypatch, project_settings):
    """Project settings the host reads, a copy each test can change."""
    settings = copy.deepcopy(project_settings)
    monkeypatch.setattr(
        pipeline, "get_current_project_settings", lambda: settings
    )
    return settings


@pytest.fixture(autouse=True)
def _clean_test_workfiles(shot_context, other_task_context, edit_context):
    """Delete workfiles of the test tasks before each test.

    The workfiles of the last test stay, to be read after a failure.
    """
    host = pipeline.FlameBatchHost()
    for folder_entity, task_entity in (
        shot_context, other_task_context, edit_context
    ):
        workdir = os.path.dirname(
            workfile_path(host, folder_entity, task_entity, 1)
        )
        for pattern in _WORKFILE_PATTERNS:
            for path in glob.glob(os.path.join(workdir, pattern)):
                os.remove(path)


@pytest.fixture(autouse=True)
def _restore_session():
    """Restore the AYON session and the Flame host state after each test.

    Saving or opening a workfile with context changes the AYON context
    (environment) like it does for an artist.
    """
    env = dict(os.environ)
    menu_context = CTX.context
    batch_workfiles = dict(batch_utils._SESSION_BATCH_WORKFILES)
    editorial = dict(editorial_workfile._CURRENT_WORKFILE)
    batch_utils._SESSION_BATCH_WORKFILES.clear()
    editorial_workfile._CURRENT_WORKFILE.update(
        flame_project=None, folder_path=None, task_name=None, path=None
    )
    yield
    os.environ.clear()
    os.environ.update(env)
    CTX.context = menu_context
    batch_utils._SESSION_BATCH_WORKFILES.clear()
    batch_utils._SESSION_BATCH_WORKFILES.update(batch_workfiles)
    editorial_workfile._CURRENT_WORKFILE.update(editorial)


@pytest.fixture
def host():
    """The registered host (editorial workfiles)."""
    return registered_host()


# --- Flame ------------------------------------------------------------------


@pytest.fixture
def make_batch_group():
    """Create batch groups, every batch group made during the test is deleted.

    Batch groups the code under test creates (opening a Batch workfile)
    are deleted too.
    """
    before = set(get_batch_groups())

    def _make(name=None):
        name = name or f"ayon_test_{uuid.uuid4().hex[:8]}"
        return flame.batch.create_batch_group(
            name, start_frame=1001, duration=10
        )

    yield _make

    for uid, batch in get_batch_groups().items():
        if uid not in before:
            flame.delete(batch, confirm=False)


@pytest.fixture
def batch_group(make_batch_group):
    """A new empty batch group, the current one of Flame."""
    return make_batch_group()


@pytest.fixture
def make_sequence():
    """Create sequences in a reel of the desktop, deleted after the test."""
    created = []

    def _make(name=None):
        name = name or f"ayon_test_seq_{uuid.uuid4().hex[:8]}"
        reel = get_desktop().reel_groups[0].reels[0]
        sequence = reel.create_sequence(name=name, video_tracks=1)
        created.append(sequence)
        return sequence

    yield _make

    for sequence in created:
        try:
            flame.delete(sequence, confirm=False)
        except Exception:
            pass
