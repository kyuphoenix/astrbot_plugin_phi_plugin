from __future__ import annotations

from ._unsupported import make_unsupported_handler

ALIASES = {"mycmt"}
handle = make_unsupported_handler("mycmt")
