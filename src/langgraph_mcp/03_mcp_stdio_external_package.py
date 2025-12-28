from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import os
from contextlib import asynccontextmanager
from langchain_core.messages import SystemMessage
from pathlib import Path
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import tools_condition, ToolNode
from pydantic import BaseModel
from typing import Annotated, List
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph_mcp.configuration import get_llm
from langgraph_mcp.streaming_utils import (
    chat_endpoint_handler,
    truncate_messages_safely,
)

"""
LangGraph Agent with External MCP Packages (stdio)

This example shows:
- Local MCP servers (math, weather)  
- External MCP packages installed via uv (office-word-mcp-server)

Flow: User types in web interface → Agent uses tools → Response streams back

Example:
  User: "Calculate 5 * 8, then create a Word doc called 'result.docx' with the answer"
  Agent: *calls math multiply(5, 8) then word create_document()*
  Result: "5 * 8 = 40. Created result.docx with the result."
"""

# put verbose to true to see chat and tool results in terminal
VERBOSE = True


# Define the state of the graph
class MessageState(BaseModel):
    messages: Annotated[List, add_messages]


def create_assistant(llm_with_tools):
    """Create an assistant function with access to the LLM"""
    system_prompt = SystemMessage(
        content="""
You are an Expert Developer Relations Engineer automating technical content creation using MCP tools.

### WORKFLOW: Firecrawl → research_notes.md → slides.md → Git

### TOOL RULES:

1. FIRECRAWL:
   - Use 'search' (limit: 5), never 'crawl'
   - firecrawl_search returns: url, title, description for each result
   - For each result, write a numbered item to research_notes.md with: title + description + key insights
   - Only use firecrawl_scrape if description is insufficient (adds ~5-10 sec per scrape)
   - Write all findings to '/Users/petereijgermans/Desktop/mcp-tutorial-java-magazine/research_notes.md'

2. SLIDEV GENERATION:
   - File: '/Users/petereijgermans/Desktop/mcp-tutorial-java-magazine/my-slides/slides.md'
   - MANDATORY STEPS:
     a) Read research_notes.md using read_text_file to get ALL numbered items (e.g., "1. AI performance...", "2. Increase in AI...")
     b) Use write_file (NOT edit_file) to COMPLETELY REPLACE slides.md - DELETE all old slides
     c) Create slides.md with:
        - Frontmatter (theme: '@slidev/theme-seriph', background, etc.) followed by '---'
        - Cover slide: "# AI Trends 2025" followed by '---'
        - TOC slide listing all numbered items followed by '---'
        - ONE slide per numbered item: title from item, content is EXACT text from item (use 1 emoji per title)
        - CRITICAL FORMATTING: After EVERY layout: declaration, you MUST add '---' on the next line
        - Example: "---\nlayout: default\n---\n\n# Slide Title\nContent here\n---"
        - Each slide separated by '---', use layout: (cover, section, default, fact)
        - Use 'layout: default' for slides with bullet lists (NOT 'layout: fact' - that's for single facts only)
        - Avoid nested bullet points (sub-bullets) - use flat list with bold text for emphasis instead
   - CRITICAL: If research_notes.md has 10 numbered items → create 10 content slides (plus cover + TOC)
   - Example: "1. AI performance on benchmarks sharply improves." → Slide: "---\nlayout: default\n---\n\n# AI Performance on Benchmarks\nAI performance on benchmarks sharply improves.\n---"

3. GIT:
   - Check git_status before git_add (exclude .DS_Store)
   - Only stage files, never commit to main

4. STATE MANAGEMENT:
   - Filesystem is your memory - read files before editing
   - Use write_file for slides.md (complete replacement), edit_file for research_notes.md (append)
                """
    )


    async def assistant(state: MessageState):
        # Increase max_history to prevent state loss in multi-step workflows
        messages = truncate_messages_safely(state.messages, max_history=40)
        messages = [system_prompt] + messages
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    return assistant


def build_graph(tools):
    """Build and return the LangGraph ReAct agent with MCP tools"""
    llm = get_llm("openai")
    llm_with_tools = llm.bind_tools(tools)

    builder = StateGraph(MessageState)
    builder.add_node("assistant", create_assistant(llm_with_tools))
    builder.add_node("tools", ToolNode(tools))

    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")

    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


async def validate_servers(all_servers):
    """Validate and filter MCP servers, returning only successful ones"""
    successful_servers = {}
    for server_name, server_config in all_servers.items():
        try:
            test_client = MultiServerMCPClient({server_name: server_config})
            await test_client.get_tools()
            successful_servers[server_name] = server_config
            print(f"Successfully loaded: {server_name}")
        except Exception as e:
            print(f"Failed to load {server_name}: {e}")
    return successful_servers


async def setup_langgraph_app():
    """Setup the LangGraph app with MCP tools"""
    current_dir = Path(__file__).parent
    firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")

    # Define all MCP servers (local + external packages)
    all_servers = {
        # Local MCP servers (from our local files)
        "local_math": {
            "command": "python",
            "args": [str(current_dir / "local_mcp_servers" / "math_server.py")],
            "transport": "stdio",
        },
    
        # External MCP package (installed via uv/npx)
    
         "firecrawl-mcp": {
          "command": "npx",
          "args": [
             "-y",
             "firecrawl-mcp"
            ],
           "env": {
              "FIRECRAWL_API_KEY": firecrawl_api_key
            },
            "transport": "stdio"
        },
        
        "filesystem": {
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                str(current_dir.parent.parent)  # Allow access to project root
            ],
            "transport": "stdio"
        },
        
        "git": {
            "command": "uvx",
            "args": [
                "mcp-server-git"
            ],
            "transport": "stdio"
        },
        
        
    
    }

    # Validate servers - only load ones that work
    successful_servers = await validate_servers(all_servers)

    if successful_servers:
        client = MultiServerMCPClient(successful_servers)
        tools = await client.get_tools()

        print(f"\nLoaded {len(tools)} tools from {len(successful_servers)} server(s):")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")

        return build_graph(tools)
    else:
        print("No servers loaded! Terminating.")
        raise RuntimeError("No MCP servers available")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.langgraph_app = await setup_langgraph_app()
    yield


app = FastAPI(lifespan=lifespan)

# Mount static files directory
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def root():
    return RedirectResponse(url="/static/chat.html")


@app.post("/chat")
async def chat_endpoint(
    request: Request, user_input: str = Form(...), thread_id: str = Form(None)
):
    print("Received user_input:", user_input)
    return await chat_endpoint_handler(request, user_input, thread_id, VERBOSE)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
