import unittest

from fastagent.grounding.backends.gui.transport.connector import GUIConnector
from fastagent.platform.screenshot import ScreenshotClient


class FakeResponse:
    status = 200
    headers = {"Content-Type": "image/png"}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def read(self):
        return b'{"error":"synthetic non-image response"}'

    async def text(self):
        return '{"error":"synthetic non-image response"}'


class FakeSession:
    closed = False

    def get(self, url):
        return FakeResponse()


class ScreenshotResponseValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_screenshot_client_rejects_mislabeled_non_image_body(self):
        client = ScreenshotClient(base_url="http://synthetic.invalid")
        client._session = FakeSession()

        self.assertIsNone(await client.capture())

    async def test_gui_connector_rejects_mislabeled_non_image_body(self):
        connector = GUIConnector("127.0.0.1", retry_times=1)

        async def synthetic_request(*args, **kwargs):
            return FakeResponse()

        connector._request = synthetic_request
        self.assertIsNone(await connector.get_screenshot())

    def test_png_signature_is_accepted_without_image_content_type(self):
        png_signature = b"\x89PNG\r\n\x1a\nsynthetic"
        self.assertTrue(ScreenshotClient._is_valid_image_response("application/octet-stream", png_signature))
        self.assertTrue(GUIConnector._is_valid_image_response("application/octet-stream", png_signature))


if __name__ == "__main__":
    unittest.main()
