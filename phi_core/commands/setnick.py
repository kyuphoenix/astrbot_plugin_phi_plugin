from __future__ import annotations

from ._unsupported import make_unsupported_handler

ALIASES = {"setnick", "setnic", "设置别名"}
handle = make_unsupported_handler("setnick")
