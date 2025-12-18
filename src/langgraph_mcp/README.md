# LangGraph MCP Examples

This directory contains progressive examples of building LangGraph agents with MCP (Model Context Protocol) servers.

## 01_no_mcp_langgraph_agent.py
**Run:** `poetry run python src/langgraph_mcp/01_no_mcp_langgraph_agent.py`

Basic LangGraph ReAct agent using local Python functions as tools (add, multiply, divide). This demonstrates the core LangGraph pattern without MCP integration.

--------------------------

## 02_mcp_stdio_local.py
**Run:** `poetry run python src/langgraph_mcp/02_mcp_stdio_local.py`

LangGraph agent with local MCP servers (math and weather) connected via stdio transport. Shows how to integrate MCP servers that run as subprocesses.

--------------------------

## 03_mcp_stdio_external_package.py
**Run:** `poetry run uvicorn langgraph_mcp.03_mcp_stdio_external_package:app --host 0.0.0.0 --port 8000`

LangGraph agent combining local MCP servers with external MCP packages (like office-word-mcp-server) via stdio. Includes a FastAPI web interface with streaming chat.

--------------------------

## 04_mcp_http_external_package.py
**Run:** `poetry run uvicorn langgraph_mcp.04_mcp_http_external_package:app --host 0.0.0.0 --port 8000`

**Docker:** 

```bash
docker build -f src/langgraph_mcp/Dockerfile -t vibify-frontend .
docker run -ti -p 8000:8000 vibify-frontend
```

LangGraph agent with remote HTTP MCP servers (Supabase) or code-explorer. This includes a FastAPI web interface with streaming chat. Feel free to add other servers (stdio or streamable-http).

--------------------------