"""Test suite for WebFetchTool."""

import asyncio
import sys
from backend.tools.web_fetch_tool import WebFetchTool
from backend.tools.base import ToolContext


async def test_empty_url():
    """Test: empty URL returns error."""
    tool = WebFetchTool()
    result = await tool.execute({"url": ""}, ToolContext())
    assert result.is_error, "Empty URL should error"
    assert "empty" in result.content.lower(), "Should mention empty URL"
    print("✓ Test 1: empty URL → error")


async def test_invalid_protocol():
    """Test: invalid protocol returns error."""
    tool = WebFetchTool()
    result = await tool.execute({"url": "ftp://example.com"}, ToolContext())
    assert result.is_error, "Non-http URL should error"
    print("✓ Test 2: invalid protocol → error")


async def test_valid_url_text():
    """Test: valid URL with text extraction."""
    tool = WebFetchTool()
    result = await tool.execute(
        {"url": "https://microsoft.github.io/graphrag/", "extract": "text"},
        ToolContext(),
    )
    assert not result.is_error, "Valid URL should not error"
    assert "TEXT length=" in result.content, "Should have TEXT prefix"
    assert len(result.content) > 100, "Should have content"
    print("✓ Test 3: valid URL text extraction → OK")


async def test_valid_url_main():
    """Test: valid URL with main extraction."""
    tool = WebFetchTool()
    result = await tool.execute(
        {"url": "https://microsoft.github.io/graphrag/", "extract": "main"},
        ToolContext(),
    )
    assert not result.is_error, "Valid URL should not error"
    assert "MAIN CONTENT" in result.content, "Should have MAIN prefix"
    print("✓ Test 4: valid URL main extraction → OK")


async def test_valid_url_html():
    """Test: valid URL with HTML extraction."""
    tool = WebFetchTool()
    result = await tool.execute(
        {"url": "https://microsoft.github.io/graphrag/", "extract": "html"},
        ToolContext(),
    )
    assert not result.is_error, "Valid URL should not error"
    assert "HTML length=" in result.content, "Should have HTML prefix"
    assert "<!doctype" in result.content.lower() or "<html" in result.content.lower()
    print("✓ Test 5: valid URL HTML extraction → OK")


async def test_http_error():
    """Test: HTTP error returns error."""
    tool = WebFetchTool()
    result = await tool.execute(
        {"url": "https://www.datacamp.com/tutorial/graphrag", "extract": "text"},
        ToolContext(),
    )
    # This site returns 403, so we expect error
    assert result.is_error or "403" in result.content, "Should handle HTTP error"
    print("✓ Test 6: HTTP 403 error → handled")


async def run_all_tests():
    """Run all tests."""
    print("=== WebFetchTool Test Suite ===\n")
    
    await test_empty_url()
    await test_invalid_protocol()
    await test_valid_url_text()
    await test_valid_url_main()
    await test_valid_url_html()
    await test_http_error()
    
    print("\n=== All tests passed! ===")


if __name__ == "__main__":
    asyncio.run(run_all_tests())