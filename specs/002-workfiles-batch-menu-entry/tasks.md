# Tasks: Workfiles Menu Entry (Flame Batch Menu)

**Feature**: specs/002-workfiles-batch-menu-entry/spec.md
**Plan**: specs/002-workfiles-batch-menu-entry/plan.md
**Branch**: workfile-entry-batch-menu
**Prerequisites**: spec.md, plan.md, research.md, data-model.md,
contracts/menu-action.md

## Scope and conventions

- [P] means the task can run in parallel with other tasks in its phase when
  it touches a different file or is read-only.
- The runtime implementation is limited to client/ayon_flame/api/menu.py.
- Do not modify client/ayon_flame/addon.py, client/ayon_flame/plugins/**,
  server/**, client/ayon_flame/api/pipeline.py, or
  client/ayon_flame/api/workfile.py.
- Do not wire IWorkfileHost into FlameHost; that is the deferred feature-001
  D1b decision and is explicitly out of scope.
- The repository has no test framework; do not add one.
- Preserve the existing menu.py style and pass the configured Ruff checks.

## Phase 1 — Contract and implementation

- [x] **T001 [P] Verify the installed AYON Core callback contract** — Attempted
      in the agent environment; neither ayon_core nor Ruff is installed or
      importable here. The established show_publisher(parent=...) callback
      pattern was used, and the exact show_workfiles signature remains an
      in-host/runtime validation item.

- [x] **T002 Implement the Batch-only menu action** — In
      client/ayon_flame/api/menu.py, added a build_menu override to
      FlameMenuBatch that calls super().build_menu(), preserves an empty
      inherited result, and appends exactly one action named
      4 - Workfiles.... The action invokes
      host_tools.show_workfiles(parent=_get_main_window()) through the
      existing callback_selection path. The inherited Create, Publish, and
      Load actions and shared context builder were left unchanged.
      Depends on T001.

- [x] **T003 [P] Review the implementation against the menu contract** — Confirmed
      by source diff inspection: only FlameMenuBatch gains the action, the
      inherited action order is unchanged, Timeline and Universal classes are
      untouched, and the existing self.flame guard is retained through the
      superclass implementation.
      Depends on T002.

## Phase 2 — Static validation and regression containment

- [x] **T004 [P] Run targeted lint and formatting checks** — The checks were
      attempted, but Ruff is not installed in the agent environment. They must
      be rerun in CI or the development environment.
      Depends on T002.

- [x] **T005 [P] Verify file-scope and launcher boundaries** — Confirmed by
      git status and diff inspection: only client/ayon_flame/api/menu.py and
      the feature task artifact are changed; no plugins, server, pipeline,
      workfile host, startup, or addon.py changes were made. addon.py remains
      without a flame import.
      Depends on T002.

- [x] **T006 Run the package-build check** — python3 create_package.py
      --skip-zip completed successfully. No unintended source files were left
      modified.
      Depends on T004, T005.

## Phase 3 — In-host validation

- [ ] **T007 Validate Batch menu construction in Flame** — Using the supported
      studio launcher and a loaded Flame project, open the AYON Batch menu and
      confirm the project row is followed by Create, Publish, Load, and
      Workfiles in that order. Confirm the exact label is 4 - Workfiles... and
      that menu construction does not raise when the Flame runtime is
      unavailable to the builder.
      Depends on T006.

- [ ] **T008 Validate Workfiles callback behavior in Flame** — Trigger the
      Workfiles action and confirm it calls show_workfiles with the Flame main
      window parent and opens the AYON workfiles UI. Confirm the existing
      selection/context callback path receives the Batch selection and
      FlameMenuBatch context. Record behavior if the feature-001 IWorkfileHost
      wiring is still deferred; do not add a publish collector or change
      validator/version behavior as a workaround.
      Depends on T007.

- [ ] **T009 Validate menu scoping and regression behavior** — In Flame, inspect
      Timeline and Universal/Media Panel menus and confirm Workfiles is absent,
      while Create, Publish, and Load remain unchanged. Confirm no publish,
      version, iteration, or settings behavior changed. Also verify the
      no-main-window case follows the existing parent=None behavior where
      practical.
      Depends on T007, T008.

## Phase 4 — Completion

- [ ] **T010 Record validation results and final diff** — Update the feature
      research or plan with the observed AYON Core callback signature and
      in-host results, including any Flame-version differences. Run
      git diff --check, review git status --short, and ensure all acceptance
      criteria in spec.md and the contract are covered. Keep all deferred
      feature-001 host-wiring work out of this change.
      Depends on T006, T008, T009.

## Dependency graph

T001 -> T002 -> T003
T002 -> T004, T005 -> T006
T006 -> T007 -> T008 -> T009 -> T010
T004, T005 -> T006

## Acceptance criteria mapping

| Requirement | Covered by |
| --- | --- |
| FR-001 / SC-001: Batch menu contains Workfiles | T002, T007 |
| FR-002 / SC-002: callback invokes show_workfiles with parent | T001, T002, T008 |
| FR-003: Timeline and Universal remain unchanged | T003, T009 |
| FR-004: existing Flame availability guard remains | T002, T003, T007 |
| FR-005: Create/Publish/Load order and labels preserved | T002, T003, T007 |
| FR-006 / FR-008: no publish, settings, plugin, or host-wiring changes | T005, T008, T010 |
| FR-007 / SC-004: launcher boundary remains intact | T005 |
| SC-003: lint, package, and focused diff validation | T004, T005, T006, T010 |
