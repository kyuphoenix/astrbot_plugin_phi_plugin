from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phi_core.concurrency import AsyncKeyedLock


async def main() -> None:
    locks = AsyncKeyedLock()
    events: list[str] = []

    async def job(name: str, delay: float = 0.01) -> str:
        events.append(f"start:{name}")
        await asyncio.sleep(delay)
        events.append(f"end:{name}")
        return name

    same_key_results = await asyncio.gather(
        locks.run("session:user", lambda: job("a")),
        locks.run("session:user", lambda: job("b")),
    )
    if same_key_results != ["a", "b"]:
        raise SystemExit(f"same-key result order changed: {same_key_results!r}")
    if events != ["start:a", "end:a", "start:b", "end:b"]:
        raise SystemExit(f"same-key jobs should be serialized, got {events!r}")
    if locks.active_count() != 0:
        raise SystemExit(f"idle same-key locks should be cleaned, got {locks.active_count()}")

    events.clear()
    await asyncio.gather(
        locks.run("session:user-1", lambda: job("c", 0.03)),
        locks.run("session:user-2", lambda: job("d", 0.03)),
    )
    if events[:2] != ["start:c", "start:d"]:
        raise SystemExit(f"different-key jobs should run concurrently, got {events!r}")
    if locks.active_count() != 0:
        raise SystemExit(f"idle different-key locks should be cleaned, got {locks.active_count()}")

    print("command lock smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
