from unittest.mock import patch, AsyncMock


async def test_mcp_endpoint_exists(client):
    """MCP endpoint should respond."""
    resp = await client.get("/mcp")
    # fastapi-mcp returns 405 for GET on streamable HTTP (expects POST)
    # or 200 for SSE — either confirms the endpoint is mounted
    assert resp.status_code in (200, 405)


async def test_mcp_excludes_upload(client):
    """upload_file should not appear in MCP tools."""
    from app.main import mcp
    tool_names = [t.name for t in mcp.tools]
    assert "upload_file" not in tool_names
    assert "health" not in tool_names


async def test_mcp_includes_generate(client):
    """generate tool should appear in MCP tools."""
    from app.main import mcp
    tool_names = [t.name for t in mcp.tools]
    assert "generate" in tool_names
    assert "list_brands" in tool_names
    assert "create_workflow" in tool_names
    assert "templatize" in tool_names


async def test_mcp_tool_names_are_clean(client):
    """Tool names should be clean function names, not ugly auto-generated ones."""
    from app.main import mcp
    for tool in mcp.tools:
        # Should NOT contain path fragments like _brands_get or _post
        assert "_get" not in tool.name, f"Ugly tool name: {tool.name}"
        assert "_post" not in tool.name, f"Ugly tool name: {tool.name}"
        assert "_put" not in tool.name, f"Ugly tool name: {tool.name}"
        assert "_delete" not in tool.name, f"Ugly tool name: {tool.name}"
