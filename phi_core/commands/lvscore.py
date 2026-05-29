from __future__ import annotations

from ._unsupported import make_unsupported_handler

ALIASES = {"lvscore", "lvsco", "scolv"}
handle = make_unsupported_handler("lvscore")
