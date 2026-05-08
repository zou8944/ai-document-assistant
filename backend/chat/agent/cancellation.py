"""Cancellation token for agent operations."""

import asyncio


class CancellationToken:
    """Token that can be checked/cancelled across async boundaries."""

    def __init__(self):
        self._cancelled = asyncio.Event()

    def cancel(self):
        self._cancelled.set()

    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def raise_if_cancelled(self):
        if self._cancelled.is_set():
            raise asyncio.CancelledError()

    async def wait(self):
        await self._cancelled.wait()
