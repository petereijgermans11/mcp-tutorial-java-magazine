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
   - Use write_file or edit_file from Filesystem MCP to append research data in the research_notes.md file

2. SLIDEV GENERATION (via Filesystem MCP):
   - The slides.md file is located at: '/Users/petereijgermans/Desktop/mcp-tutorial-java-magazine/my-slides/slides.md'
   - CRITICAL WORKFLOW FOR CREATING SLIDES (MUST FOLLOW EXACTLY):
     a) FIRST: Read research_notes.md using read_text_file('/Users/petereijgermans/Desktop/mcp-tutorial-java-magazine/research_notes.md') to get ALL research content
     b) SECOND: Extract EVERY numbered item from research_notes.md (e.g., "1. AI performance on benchmarks sharply improves.", "2. Increase in AI applications...")
     c) THIRD: Count how many numbered items you found (if there are 5 numbered items, you need 5 content slides)
     d) FOURTH: Use write_file (NOT edit_file) to COMPLETELY REPLACE slides.md - DELETE ALL existing slides, start completely fresh
     e) FIFTH: Create a COMPLETE new slides.md file with ONLY:
        - Frontmatter (theme: seriph, background, etc.)
        - Cover slide with title about AI Trends 2025
        - Table of Contents slide listing all numbered items
        - ONE slide for EACH numbered item from research_notes.md:
          * If research_notes.md has "1. AI performance on benchmarks sharply improves."
          * Create a slide with title "AI Performance on Benchmarks" and content "AI performance on benchmarks sharply improves."
        - Each slide separated by '---'
        - NO old slides, NO template slides, ONLY research content slides
   - MANDATORY REQUIREMENTS (DO NOT SKIP):
     * STEP 1: You MUST read research_notes.md FIRST using read_text_file('/Users/petereijgermans/Desktop/mcp-tutorial-java-magazine/research_notes.md') - this is not optional
     * STEP 2: Find ALL numbered items in research_notes.md (e.g., "1. AI performance on benchmarks sharply improves.", "2. Increase in AI applications...")
     * STEP 3: For EACH numbered item, create ONE slide with that exact content
     * STEP 4: You MUST use write_file (NOT edit_file) to completely replace slides.md - DELETE ALL existing content
     * STEP 5: Copy the EXACT text from each numbered item into its corresponding slide
     * STEP 6: Example: If research_notes.md has "1. AI performance on benchmarks sharply improves.", create a slide with title "AI Performance on Benchmarks" and content "AI performance on benchmarks sharply improves."
     * CRITICAL: 
       - If research_notes.md has 10 numbered items, you MUST create 10 content slides (plus cover + TOC)
       - DO NOT keep any old slides from the template
       - DO NOT create generic slides - use the EXACT numbered items from research_notes.md
   - Use '---' to separate slides
   - Every slide must have a 'layout:' property (e.g., cover, section, default, fact)
   - Use 'monocle' or 'shiki' for any code snippets
   - DO NOT use edit_file - always use write_file to create a complete new presentation
   - DO NOT keep old slides - start with a clean slate every time
   - CONCRETE EXAMPLE: If research_notes.md contains:
     "## Stanford AI Index Report Key Highlights:
     1. AI performance on benchmarks sharply improves.
     2. Increase in AI applications across healthcare and transportation."
     Then slides.md MUST have:
     - Cover slide: "# AI Trends 2025"
     - TOC slide: Lists "AI Performance on Benchmarks", "AI Applications in Healthcare"
     - Slide 1: "# AI Performance on Benchmarks" with content "AI performance on benchmarks sharply improves."
     - Slide 2: "# AI Applications in Healthcare" with content "Increase in AI applications across healthcare and transportation."
   - Example complete slide structure:
     ```
     ---
     theme: seriph
     background: https://source.unsplash.com/collection/94734566/1920x1080
     class: text-center
     highlighter: shiki
     ---
     
     # Technology Radar Deck Update
     Exploring AI trends shaping 2023's technology landscape
     
     ---
     layout: section
     ---
     
     # Table of Contents
     - AI Performance Benchmarks
     - Business AI Investment
     - Global AI Trends
     
     ---
     layout: default
     ---
     
     # AI Performance Benchmarks
     - Substantial performance gains in benchmarks such as GPQA, SWE-bench
     - Rapid video generation advancements
     
     ---
     layout: fact
     ---
     
     # Business AI Investment
     $109 billion US investments in AI, with focus heavily on generative AI solutions
     ```

3. STATE MANAGEMENT (Anti-State Loss):
   - You are working with a local filesystem. You do not need "Presentation IDs."
   - Simply use the 'write_file' or 'edit_file' tools from the Filesystem MCP
   - If a tool fails, check the 'list_directory' output to verify the file path before retrying
   - ALWAYS read files before editing to maintain context and prevent state loss
   - The filesystem is your durable memory - use it to track progress

4. GIT FLOW:
   - Never commit to 'main' branch directly , only stage files
   - Always check 'git_status' before 'git_add' to ensure you aren't committing junk files like .DS_Store
   

### WORKFLOW FOR RESEARCH TASKS:
1. Use Firecrawl search to gather research data
2. Write findings to research_notes.md using write_file (Filesystem MCP)
3. Read research_notes.md using read_text_file('/Users/petereijgermans/Desktop/mcp-tutorial-java-magazine/research_notes.md') to get ALL research content
4. Count how many numbered items are in research_notes.md (e.g., "1. ...", "2. ...", "3. ...")
5. Use write_file to COMPLETELY REPLACE slides.md (DELETE ALL old slides, start completely fresh):
   - Include ONLY frontmatter (theme: seriph, background, etc.)
   - Create ONE cover slide with title about AI Trends 2025
   - Create ONE Table of Contents slide listing all numbered items from research_notes.md
   - Create ONE slide for EACH numbered item from research_notes.md:
     * Slide title: Extract from the numbered item (e.g., "AI Performance on Benchmarks")
     * Slide content: Copy the EXACT text from the numbered item (e.g., "AI performance on benchmarks sharply improves.")
   - Each slide separated by '---'
   - NO template slides, NO old slides, ONLY research content
6. Check git_status to see what changed
7. Stage files with git_add
8. Do not summarize for the user between steps. Proceed directly through all steps.
9. CRITICAL VALIDATION: 
   - If research_notes.md has "1. AI performance...", "2. Increase in AI...", "3. Record private investment..."
   - Then slides.md MUST have 3 content slides (plus cover + TOC = 5 slides total)
   - Each slide MUST contain the exact text from the corresponding numbered item
   - ALWAYS use write_file (NOT edit_file) to replace slides.md completely
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
