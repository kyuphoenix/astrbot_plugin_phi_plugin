from __future__ import annotations

from ._unsupported import make_unsupported_handler

ALIASES = {"comment", "cmt", "评论", "评价"}
handle = make_unsupported_handler("comment")
