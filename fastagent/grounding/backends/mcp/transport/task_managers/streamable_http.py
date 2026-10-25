"""
Streamable HTTP connection management for MCP implementations.

This module provides a connection manager for streamable HTTP-based MCP connections
that ensures proper task isolation and resource cleanup.
"""

from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from typing import Any, Tuple

try:
    from mcp.client.streamable_http import (
        streamablehttp_client as _legacy_streamablehttp_client,
    )
except ImportError:
    _legacy_streamablehttp_client = None
    from mcp.client.streamable_http import (
        streamable_http_client as _modern_streamable_http_client,
    )
    from mcp.shared._httpx_utils import create_mcp_http_client
    import httpx2
else:
    _modern_streamable_http_client = None
    create_mcp_http_client = None
    httpx2 = None

from fastagent.utils.logging import Logger
from fastagent.grounding.core.transport.task_managers import (
    AsyncContextConnectionManager,
)

logger = Logger.get_logger(__name__)


def _normalize_streams(streams: Any) -> tuple[Any, Any]:
    if not isinstance(streams, (tuple, list)) or len(streams) not in (2, 3):
        raise RuntimeError(
            "Invalid streamable HTTP result: expected read/write streams and an "
            f"optional session callback, got {type(streams).__name__}"
        )
    return streams[0], streams[1]


def _seconds(value: Any, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, timedelta):
        return value.total_seconds()
    return float(value)


def _make_shim():
    """Adapt supported MCP SDK streamable-HTTP client APIs to two streams."""
    @asynccontextmanager
    async def _shim(**kw):
        stack = AsyncExitStack()
        try:
            if _legacy_streamablehttp_client is not None:
                ctx_manager = _legacy_streamablehttp_client(**kw)
            else:
                options = dict(kw)
                url = options.pop("url")
                headers = options.pop("headers", None)
                timeout = _seconds(options.pop("timeout", None), 30.0)
                read_timeout = _seconds(options.pop("sse_read_timeout", None), 300.0)
                if options:
                    unexpected = ", ".join(sorted(options))
                    raise TypeError(f"Unexpected streamable HTTP options: {unexpected}")

                http_client = create_mcp_http_client(
                    headers=headers,
                    timeout=httpx2.Timeout(timeout, read=read_timeout),
                )
                await stack.enter_async_context(http_client)
                ctx_manager = _modern_streamable_http_client(
                    url,
                    http_client=http_client,
                )

            streams = await stack.enter_async_context(ctx_manager)
            yield _normalize_streams(streams)
        except GeneratorExit:
            logger.debug("StreamableHTTP generator exit (normal cleanup)")
        except Exception as conn_error:
            error_msg = str(conn_error).lower()
            if "unhandled errors in a taskgroup" in error_msg:
                logger.debug(
                    "TaskGroup race condition during connection: %s",
                    type(conn_error).__name__,
                )
            else:
                logger.warning("Connection error: %s", conn_error)
            raise
        finally:
            try:
                await stack.aclose()
            except (GeneratorExit, RuntimeError, OSError, Exception) as cleanup_error:
                error_type = type(cleanup_error).__name__
                if "ExceptionGroup" in error_type or "TaskGroup" in str(cleanup_error):
                    logger.debug("Benign TaskGroup cleanup error: %s", error_type)
                else:
                    logger.debug("Benign cleanup error: %s", error_type)

    return _shim


class StreamableHttpConnectionManager(
    AsyncContextConnectionManager[Tuple[Any, Any], ...]
):
    """
    MCP Streamable-HTTP connection manager based on the generic
    AsyncContextConnectionManager.  Extra session-id callback returned by the
    SDK is discarded by the shim above.
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 5,
        read_timeout: float = 60 * 5,
    ):
        shim = _make_shim()              
        super().__init__(
            shim,
            url=url,
            headers=headers or {},
            timeout=timedelta(seconds=timeout),
            sse_read_timeout=timedelta(seconds=read_timeout),
        )
        self.url = url
        self.headers = headers or {}
        logger.debug("StreamableHttpConnectionManager init url=%s", url)
