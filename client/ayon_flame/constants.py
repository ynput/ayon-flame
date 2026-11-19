"""Constants shared by the addon and the Flame host integration.

Kept free of 'flame' imports, the addon class reads them outside Flame.
"""

# Workfile extensions are explicit per kind of workfile, never a generic
# one like '.json': AYON matches files, workfile hosts and applications by
# extension, so every workfile kind owns a unique one.

# Batch group saved as a consolidated JSON document.
BATCH_WORKFILE_EXTENSION = ".flamebatch"

# Identifier of the creator of the Batch product. The creator plugins are
# loaded by file path and cannot be imported, so the host and the creator
# share the identifier from here.
BATCH_CREATOR_IDENTIFIER = "io.ayon.creators.flame.batch.workfile"

# Editorial workfile, a small JSON reference to a Flame project sequence.
EDITORIAL_WORKFILE_EXTENSION = ".flameedit"
