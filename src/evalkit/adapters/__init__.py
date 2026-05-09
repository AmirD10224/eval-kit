"""Optional integrations with other eval / observability tools.

Each adapter has its own optional extra (e.g., ``pip install
'evalkit-oss[langfuse]'``). Importing the package at top level does not
require any of them; you import the specific adapter when you want it.
"""

from evalkit.adapters.promptfoo import import_promptfoo_config

__all__ = ["import_promptfoo_config"]
