from __future__ import annotations

__all__ = ["__version__", "app"]
__version__ = "0.1.0"

from .cli import app  # so you can `from ddcli import app`
