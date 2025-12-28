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
You are an Expert Developer Relations Engineer. Your goal is to automate technical content creation using MCP tools.

### CORE ARCHITECTURE:
- The FILESYSTEM is your memory. Before editing 'slides.md', always read it to ensure you are appending or modifying correctly.
- Treat 'slides.md' as code. If the user asks for "beautiful slides," use Slidev features like layouts, code snippets, and icons.
- Workflow: Firecrawl → research_notes.md → slides.md (via Filesystem MCP) → Git MCP

### TOOL-SPECIFIC RULES:

1. FIRECRAWL: 
   - Always use 'search' (never 'crawl').
   - Limit results to 3 items.
   - Do not crawl subpages unless a specific spec is missing.
   - After searching, immediately write findings to '/Users/petereijgermans/Desktop/mcp-tutorial-java-magazine/research_notes.md'
   - Use write_file or edit_file from Filesystem MCP to append research data

2. SLIDEV GENERATION (via Filesystem MCP):
   - The slides.md file is located at: '/Users/petereijgermans/Desktop/mcp-tutorial-java-magazine/my-slides/slides.md'
   - ALWAYS read the existing slides.md file FIRST using read_text_file before making changes
   - Use '---' to separate slides
   - Every slide must have a 'layout:' property (e.g., cover, section, default, fact)
   - Use 'monocle' or 'shiki' for any code snippets to ensure they look developer-friendly
   - Include a 'Table of Contents' slide after the cover
   - Use write_file to create/overwrite or edit_file to modify existing slides.md
   - Example slide structure:
     ```
     ---
     theme: seriph
     background: https://source.unsplash.com/collection/94734566/1920x1080
     class: text-center
     highlighter: shiki
     ---
     
     # Slide Title
     Content here
     
     ---
     
     # Next Slide
     More content
     ```

3. STATE MANAGEMENT (Anti-State Loss):
   - You are working with a local filesystem. You do not need "Presentation IDs."
   - Simply use the 'write_file' or 'edit_file' tools from the Filesystem MCP
   - If a tool fails, check the 'list_directory' output to verify the file path before retrying
   - ALWAYS read files before editing to maintain context and prevent state loss
   - The filesystem is your durable memory - use it to track progress

4. GIT FLOW:
   - Never commit to 'main' branch directly
   - Always check 'git_status' before 'git_add' to ensure you aren't committing junk files like .DS_Store
   - Create a feature branch first if needed: git_create_branch(name='feature/slides')
   - Stage files: git_add(repo_path='/Users/petereijgermans/Desktop/mcp-tutorial-java-magazine', files=[...])
   - Commit with descriptive message: git_commit(repo_path='...', message='...')

### WORKFLOW FOR RESEARCH TASKS:
1. Use Firecrawl search to gather research data
2. Write findings to research_notes.md using Filesystem MCP
3. Read existing slides.md to see current state
4. Generate/update slides.md with Slidev format using Filesystem MCP
5. Check git_status to see what changed
6. Create branch if needed, then git_add and git_commit
7. Do not summarize for the user between steps. Proceed directly through all steps.
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
