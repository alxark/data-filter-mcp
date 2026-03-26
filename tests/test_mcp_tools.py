from __future__ import annotations

import asyncio

from data_filter_mcp.server import create_mcp_server


def test_fastmcp_tool_metadata_is_descriptive() -> None:
    mcp = create_mcp_server()
    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}

    register_tool = tools["register_filter"]
    assert "restricted Python filter" in register_tool.description
    assert (
        register_tool.inputSchema["properties"]["code"]["description"]
        == "Python source code that defines exactly one top-level function named filter_item(data). The function receives the loaded document and must return a text result."
    )
    assert (
        register_tool.outputSchema["properties"]["filter_id"]["description"]
        == "Unique filter identifier to pass into run_filter."
    )

    run_tool = tools["run_filter"]
    assert "local file" in run_tool.description
    assert (
        run_tool.inputSchema["properties"]["filter_id"]["description"]
        == "Identifier previously returned by register_filter."
    )
    assert (
        run_tool.inputSchema["properties"]["file_path"]["description"]
        == "Path to the local file that should be loaded and passed into filter_item(data)."
    )
    assert run_tool.inputSchema["properties"]["file_type"]["anyOf"][0]["enum"] == [
        "json",
        "yaml",
        "txt",
    ]
    assert (
        run_tool.inputSchema["properties"]["file_type"]["description"]
        == "Optional explicit file type override. If omitted, the server detects the type from the file extension."
    )
    assert (
        run_tool.outputSchema["properties"]["result_text"]["description"]
        == "Exact text returned by filter_item(data)."
    )
