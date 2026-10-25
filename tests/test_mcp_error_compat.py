import unittest


class MCPErrorCompatibilityTests(unittest.TestCase):
    def test_mcp_connector_imports_with_installed_sdk(self):
        from fastagent.grounding.backends.mcp.transport.connectors import base

        self.assertTrue(issubclass(base.McpError, Exception))


if __name__ == "__main__":
    unittest.main()
