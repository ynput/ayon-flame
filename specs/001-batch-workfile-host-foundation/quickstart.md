# Quickstart: validating Amendment 1

Static (agent-runnable):
```bash
ruff check .
ruff format --check .
python3 create_package.py --skip-zip
python3 -c "import sys; sys.path.insert(0,'client'); import ayon_flame.addon"  # no `flame` module
```

In Flame (reviewer, via the studio launcher wrapper; see README.md):
1. Batch page, active Batch group, open the Workfiles tool -> Save: a `.json`
   workfile with the Core-allocated version appears; Save again -> version+1.
2. Open that workfile: Batch restored (US1). Unwritable work area -> error,
   no partial file (US4.5).
3. Never-saved context: publish a Batch -> "Batch has no saved workfile"
   validation failure; click Repair -> new next-version workfile, validator
   passes, Workfiles tool never opens (US6.1-6.2, SC-A07).
4. Restart Flame, same context, publish again -> validator passes (FR-A18).
5. Compare `context.data["version"]` and iteration number on a Batch publish
   before/after this change (SC-A06), and publish from Timeline/Media Panel:
   no new validation failure (FR-A11).
6. Non-Batch tab: trigger save -> no file written (US5).
