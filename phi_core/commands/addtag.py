from __future__ import annotations

from ._unsupported import make_unsupported_handler

ALIASES = {"addtag", "subtag", "retag"}
handle = make_unsupported_handler("addtag")
