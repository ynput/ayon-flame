"""Creator plugin for Flame Reel browser context.

This plugin allows users to create plates from selected items from within
the Flame Reel browser context.

Dev notes:
    - code shouls be universal enought to be able to serve also `render` and
      `image` types
    - Add support for creating plates from multiple selected items
    - Implement error handling for invalid selections

Restrictions:
    - only need to be offered within Creator plugins if opened
      from Flame Reel browser context
    - selected mode only supported so precreate validation needs to check
      if selected items are valid for plate creation and raise if no selection
"""
