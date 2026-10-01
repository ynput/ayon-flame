"""Flame workfile host implementations.

This module is part of the Flame host-API seam: it imports the ``flame``
module and therefore must never be imported from
``client/ayon_flame/addon.py`` (launcher/hook safe code).

The workfile host is selected at call time from the active Flame tab
(``flame.get_current_tab()``):

- the Batch page uses :class:`FlameBatchWorkfileHost`, which serialises the
  active Batch Group through the existing consolidated JSON helpers in
  :mod:`ayon_flame.api.batch_utils`;
- every other tab uses :class:`FlameWorkfileHost`, which delegates to the
  existing :mod:`ayon_flame.api.workio` seam.

Publish and version behaviour is intentionally untouched: this module only
provides the host *capability*. Wiring it into ``FlameHost`` is tracked
separately, see decision D1 in
``specs/001-batch-workfile-host-foundation/plan.md``.
"""
import os
from typing import Optional

import ayon_api
import flame

from ayon_core.host import IWorkfileHost
from ayon_core.lib import Logger
from ayon_core.pipeline import registered_host

from . import batch_utils
from . import workio
from .workio import BATCH_TAB, _is_batch_tab  # noqa: F401

log = Logger.get_logger(__name__)

# Consolidated JSON workfile extension produced by 'batch_utils'.
BATCH_WORKFILE_EXTENSION = ".json"

# Session scoped record of the last AYON workfile path per context.
#
# Flame itself does not store where a Batch Group was saved, so this is the
# only source for 'get_current_workfile()'. It is deliberately not persisted
# and never guessed: an unknown path stays unknown.
_WORKFILE_PATHS = {}


def _project_name() -> Optional[str]:
    """Return the AYON project name of the running session."""
    return os.environ.get("AYON_PROJECT_NAME")


def _context_key(kind: str, name: Optional[str] = None) -> str:
    """Build a stable key used to remember a workfile path."""
    return "{}::{}::{}".format(kind, _project_name() or "", name or "")


def _batch_name(batch) -> Optional[str]:
    """Return the name of a Flame Batch Group, if it has one."""
    try:
        return batch.name.get_value()
    except Exception:
        return None


class _FlameWorkfileHostBase(IWorkfileHost):
    """Shared bookkeeping for the Flame workfile hosts.

    Only the methods required by the host contexts this addon supports are
    implemented here. Template/path resolution, workfile entities and events
    are provided by 'IWorkfileHost' itself and must not be reimplemented.
    """

    def get_current_workfile(self) -> Optional[str]:
        """Return the AYON workfile path last saved or opened.

        Flame exposes no native "current workfile" path for the contexts this
        addon supports, so the path comes from AYON's own session record.
        'None' means unknown - never a guessed path.
        """
        key = self._workfile_key()
        if key is None:
            return None
        return _WORKFILE_PATHS.get(key)

    def workfile_has_unsaved_changes(self) -> Optional[bool]:
        """Flame does not expose a dirty state through the Python API."""
        return None

    def _remember_workfile(self, filepath: str):
        """Record a workfile path for 'get_current_workfile'."""
        key = self._workfile_key()
        if key is None:
            return
        _WORKFILE_PATHS[key] = os.path.normpath(filepath)

    def _workfile_key(self) -> Optional[str]:
        raise NotImplementedError


class FlameWorkfileHost(_FlameWorkfileHostBase):
    """Workfile host used outside of the Flame Batch page.

    Delegates to the existing 'workio' seam so this addon keeps a single
    workfile API.
    """

    def save_workfile(self, dst_path: Optional[str] = None):
        workio.save_file(dst_path)
        if dst_path:
            self._remember_workfile(dst_path)

    def open_workfile(self, filepath: str):
        workio.open_file(filepath)
        self._remember_workfile(filepath)

    def get_current_workfile(self) -> Optional[str]:
        try:
            return workio.current_file()
        except NotImplementedError:
            # Flame has no native scene path; fall back to AYON's record.
            return super().get_current_workfile()

    def get_workfile_extensions(self) -> list:
        return workio.file_extensions()

    def work_root(self, session):
        """Extra convenience helper, delegates to 'workio.work_root'."""
        return workio.work_root(session)

    def _workfile_key(self) -> Optional[str]:
        return _context_key("workfile")


class FlameBatchWorkfileHost(_FlameWorkfileHostBase):
    """Workfile host for the Flame Batch page.

    A Batch Group is a native Flame object without a file path, so AYON owns
    its consolidated JSON representation
    (:func:`batch_utils.save_batch_as_consolidated_json`).
    """

    def save_workfile(self, dst_path: Optional[str] = None):
        if not dst_path:
            raise RuntimeError(
                "Cannot save a Flame Batch workfile without a destination "
                "path."
            )

        workio.save_file(dst_path)
        self._remember_workfile(dst_path)

    def open_workfile(self, filepath: str):
        batch_utils.load_batch_from_consolidated_json(filepath)
        self._remember_workfile(filepath)

    def get_workfile_extensions(self) -> list:
        """Return the consolidated JSON extension used by Batch workfiles."""
        return [BATCH_WORKFILE_EXTENSION]

    def _workfile_key(self) -> Optional[str]:
        try:
            batch = batch_utils.get_current_batch()
        except RuntimeError:
            return None
        return _context_key("batch", _batch_name(batch))


def get_flame_workfile_host() -> IWorkfileHost:
    """Return the workfile host matching the active Flame tab.

    Selection is based on 'flame.get_current_tab()'. Any failure to read the
    tab falls back to the default host rather than guessing Batch.
    """
    try:
        tab = flame.get_current_tab()
    except Exception:
        log.warning(
            "Unable to read the current Flame tab, "
            "using the default workfile host.",
            exc_info=True,
        )
        return FlameWorkfileHost()

    if _is_batch_tab(tab):
        return FlameBatchWorkfileHost()

    return FlameWorkfileHost()


def context_has_batch_instance(context) -> bool:
    """Return whether the publish context holds an instance from the Batch."""
    return any(
        instance.data.get("flame_context") == "FlameMenuBatch"
        for instance in context
    )


def list_batch_workfiles() -> list:
    """Return the AYON workfiles of the current context.

    Always lists Batch workfiles ('.json'), whatever tab is active, so the
    answer does not depend on where the artist is in Flame. Needs the AYON
    folder and task of the current context.

    Raises:
        RuntimeError: When the current context has no resolvable folder or
            task.
    """
    context = registered_host().get_current_context()
    project_name = context["project_name"]
    folder_path = context["folder_path"]
    task_name = context["task_name"]

    folder_entity = ayon_api.get_folder_by_path(project_name, folder_path)
    task_entity = None
    if folder_entity:
        task_entity = ayon_api.get_task_by_name(
            project_name, folder_entity["id"], task_name
        )
    if not task_entity:
        raise RuntimeError(
            f"Current context '{folder_path}' / '{task_name}' was not "
            f"found in project '{project_name}'."
        )

    return FlameBatchWorkfileHost().list_workfiles(
        project_name, folder_entity, task_entity
    )
