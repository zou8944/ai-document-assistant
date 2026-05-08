"""Tests for chat.agent.cancellation.CancellationToken."""

import asyncio

import pytest

from chat.agent.cancellation import CancellationToken


class TestCancellationToken:
    def test_cancel_sets_event(self):
        token = CancellationToken()
        assert not token.cancelled()
        token.cancel()
        assert token.cancelled()

    def test_raise_if_cancelled_when_not_cancelled(self):
        token = CancellationToken()
        token.raise_if_cancelled()

    def test_raise_if_cancelled_when_cancelled(self):
        token = CancellationToken()
        token.cancel()
        with pytest.raises(asyncio.CancelledError):
            token.raise_if_cancelled()

    async def test_wait_until_cancelled(self):
        token = CancellationToken()

        async def delayed_cancel():
            await asyncio.sleep(0.01)
            token.cancel()

        asyncio.create_task(delayed_cancel())
        await token.wait()
        assert token.cancelled()

    async def test_wait_already_cancelled(self):
        token = CancellationToken()
        token.cancel()
        await token.wait()
        assert token.cancelled()
