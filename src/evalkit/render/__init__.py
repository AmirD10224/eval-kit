"""HTML-to-PNG screenshot rendering for the demo asset.

The single function exported here, :func:`render_pr_comment_to_png`, takes
the same Markdown the GitHub Action posts and renders it as a PNG that
*looks* like a real PR comment. This is what powers
``examples/regression-demo/`` and produces ``docs/screenshots/auto-reject.png``.

Importing this module without the ``[render]`` extra installed is fine, the
ImportError only fires when you actually call the function.
"""

from evalkit.render.screenshot import render_pr_comment_to_png

__all__ = ["render_pr_comment_to_png"]
