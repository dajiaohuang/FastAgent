from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastagent.grounding.backends.mcp.transport.task_managers import streamable_http


class _FakeTimeout:
    def __init__(self, timeout, *, read):
        self.timeout = timeout
        self.read = read


class StreamableHttpSdkCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_modern_sdk_uses_configured_http_client_and_two_streams(self):
        events = []
        received = {}

        class FakeHttpClient:
            async def __aenter__(self):
                events.append("http-enter")
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                events.append("http-exit")

        fake_http_client = FakeHttpClient()

        def create_fake_http_client(**kwargs):
            received["http_client_options"] = kwargs
            return fake_http_client

        @asynccontextmanager
        async def fake_streamable_http_client(url, *, http_client):
            received["transport"] = (url, http_client)
            events.append("transport-enter")
            try:
                yield ("read-stream", "write-stream")
            finally:
                events.append("transport-exit")

        with (
            patch.object(streamable_http, "_legacy_streamablehttp_client", None),
            patch.object(
                streamable_http,
                "_modern_streamable_http_client",
                fake_streamable_http_client,
            ),
            patch.object(
                streamable_http,
                "create_mcp_http_client",
                side_effect=create_fake_http_client,
            ),
            patch.object(
                streamable_http, "httpx2", SimpleNamespace(Timeout=_FakeTimeout)
            ),
        ):
            shim = streamable_http._make_shim()
            async with shim(
                url="https://synthetic.invalid/mcp",
                headers={"Authorization": "synthetic-token"},
                timeout=timedelta(seconds=5),
                sse_read_timeout=timedelta(seconds=60),
            ) as streams:
                self.assertEqual(streams, ("read-stream", "write-stream"))
                self.assertEqual(
                    received["transport"],
                    ("https://synthetic.invalid/mcp", fake_http_client),
                )
                timeout = received["http_client_options"]["timeout"]
                self.assertEqual(timeout.timeout, 5)
                self.assertEqual(timeout.read, 60)
                self.assertEqual(
                    received["http_client_options"]["headers"],
                    {"Authorization": "synthetic-token"},
                )

        self.assertEqual(
            events,
            ["http-enter", "transport-enter", "transport-exit", "http-exit"],
        )

    async def test_current_sdk_client_is_task_local_and_needs_no_server(self):
        if streamable_http._modern_streamable_http_client is None:
            self.skipTest("installed MCP SDK uses the legacy transport API")

        received = {}

        @asynccontextmanager
        async def fake_streamable_http_client(url, *, http_client):
            received["url"] = url
            received["http_client"] = http_client
            yield ("read-stream", "write-stream")

        with patch.object(
            streamable_http,
            "_modern_streamable_http_client",
            fake_streamable_http_client,
        ):
            async with streamable_http._make_shim()(
                url="https://synthetic.invalid/mcp",
                headers={"X-Test": "synthetic"},
                timeout=timedelta(seconds=5),
                sse_read_timeout=timedelta(seconds=60),
            ) as streams:
                self.assertEqual(streams, ("read-stream", "write-stream"))
                self.assertEqual(received["url"], "https://synthetic.invalid/mcp")
                http_client = received["http_client"]
                self.assertFalse(http_client.is_closed)

        self.assertTrue(http_client.is_closed)

    async def test_legacy_sdk_drops_session_callback_from_three_stream_result(self):
        received = {}

        @asynccontextmanager
        async def fake_legacy_client(**kwargs):
            received.update(kwargs)
            yield ("read-stream", "write-stream", object())

        with patch.object(
            streamable_http, "_legacy_streamablehttp_client", fake_legacy_client
        ):
            shim = streamable_http._make_shim()
            async with shim(
                url="https://synthetic.invalid/mcp",
                headers={"Authorization": "synthetic-token"},
                timeout=timedelta(seconds=5),
                sse_read_timeout=timedelta(seconds=60),
            ) as streams:
                self.assertEqual(streams, ("read-stream", "write-stream"))

        self.assertEqual(received["url"], "https://synthetic.invalid/mcp")
        self.assertEqual(received["timeout"], timedelta(seconds=5))
        self.assertEqual(received["sse_read_timeout"], timedelta(seconds=60))


if __name__ == "__main__":
    unittest.main()
