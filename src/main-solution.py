
from typing import TypedDict, Annotated, Dict, Any
from langgraph.graph import add_messages, StateGraph, END
from langchain_core.messages import AIMessage, HumanMessage, AnyMessage, SystemMessage
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode
from langchain_openai import AzureChatOpenAI
from langchain_ollama import ChatOllama
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import aiosqlite
from src.configuration import *
from pydantic import BaseModel
import uuid
import asyncio
from rich import print
from fastapi import FastAPI, Form, Request, Depends
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import os
from contextlib import asynccontextmanager
from langchain_core.prompts import ChatPromptTemplate

"""
AsyncSqliteSaver persists the graph's state (including messages) in a SQLite database asynchronously.
Restoration works as defined by your state class—if you use add_messages for the messages field,
the conversation history is preserved and extended across runs.
If you omit add_messages or use a different structure, message history may not be tracked.
Use the same thread_id to continue a conversation after restarting the script.
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.langgraph_app = await setup_langgraph_app()
    yield

app_instance = FastAPI(lifespan=lifespan)

static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
app_instance.mount(
    "/static",
    StaticFiles(directory=static_dir),
    name="static"
)

@app_instance.get("/")
def root():
    return RedirectResponse(url="/static/chat.html")

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    intel_messages: Annotated[list, add_messages]
    logistics_messages: Annotated[list, add_messages]

# Part 1: Calculator Tools
async def multiply_tool(a: float, b: float) -> float:
    """Multiplies two numbers.
    Args:
        a: The first number.
        b: The second number.
    Returns: The result of a multiplied by b.
    """
    return a * b

async def add_tool(a: float, b: float) -> float:
    """Adds two numbers.
    Args:
        a: The first number.
        b: The second number.
    Returns: The result of a added to b.
    """
    return a + b

# Part 2: Dynamic Data Tool (Simulated)
# In a real app, this would call a secure weather API.
async def weather_tool(location: str) -> str:
    """Returns the current weather information for a specific location.
    Args:
        location: The city or region to check the weather for.
    Returns: A string containing the weather details (temperature, condition).
    """
    # Simulate an LLM or an API call for realistic context generation
    if "Paris" in location:
        return "18°C and partly cloudy. Expect light rain later."
    else:
        return f"Current conditions in {location}: 22°C and sunny."

async def get_tools():
    """Returns the list of available MCP tools."""
    return [multiply_tool, add_tool, weather_tool]

async def get_llm():
    """Create and return the LLM instance using environment variables."""
    return AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_MODEL_VERSION,
        deployment_name=AZURE_OPENAI_MODEL,  
        temperature=0
    )
    # Or use Ollama if needed
    # return ChatOllama(model="qwen3:8b")

async def setup_langgraph_app():
    """Setup the LangGraph app, model, tools, and graph. Returns the compiled app."""
    load_dotenv()
    llm = await get_llm()
    tools = await get_tools()
    llm_with_tools = llm.bind_tools(tools=tools) # Connects tools to the AI

    # Define the prompt template for Rene, the commander agent
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are Rene, a AI commander agent. "
            "Your orders must be clear, concise, and actionable. For example, if asked about logistics, you might say: 'Ensure all supply trucks are refueled and ready by 0600 hours.'"
        )),
        ("user", "{input}")
    ])

    # Chain the prompt with the LLM
    chain = prompt | llm_with_tools # Links personality with AI brain

    async def model(state: AgentState):
        # Take the last user message as input
        user_message = state["messages"]
        response = await chain.ainvoke({"input": user_message}) # gets AI response
        return {"messages": [response]}

    # Checks if AI wants to use tools
    def tools_router(state: AgentState):
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
            return "tool_node"
        else:
            return END

    tool_node = ToolNode(tools=tools)

    graph = StateGraph(AgentState) # Creates empty workflow
    graph.add_node("model", model) # Adds thinking step
    graph.add_node("tool_node", tool_node) # Adds tool-using step
    
    graph.set_entry_point("model") # Starts with thinking
    graph.add_conditional_edges("model", tools_router) # Decides to use tools or not
    graph.add_edge("tool_node", "model") # After tools, go back to thinking

    conn = await aiosqlite.connect("checkpoint_06.sqlite") # Creates database
    memory = AsyncSqliteSaver(conn=conn) #  Makes workflow remember conversations
    app = graph.compile(checkpointer=memory) # Puts all parts together
    return app # Returns the ready-to-use AI commander



@app_instance.post("/chat")
async def chat_endpoint(request: Request, user_input: str = Form(...), thread_id: str = Form(None)):
    print("Received user_input:", user_input)
    if not thread_id:
        thread_id = "demo-user-1"
    config = {"configurable": {"thread_id": thread_id}}
    langgraph_app = app_instance.state.langgraph_app
    async def event_stream():
        final_message = None
        async for event in langgraph_app.astream_events(
            {"messages": [HumanMessage(content=user_input)]},
            config=config
        ):
            print("Event:", event)
            if event.get("event") == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content:
                    yield chunk.content + " "
            elif event.get("event") == "on_tool_start":
                tool_name = event.get("name", "tool")
                tool_args = event.get("data", {}).get("input", {})
                yield f"\n__TOOL_CALL__:Calling tool '{tool_name}' with args {tool_args}\n"
            elif event.get("event") == "on_tool_end":
                tool_name = event.get("name", "tool")
                tool_output = event.get("data", {}).get("output", "")
                state = event.get("data", {}).get("state", {})
                if tool_name == "logistics_agent" and "logistics_messages" in state and state["logistics_messages"]:
                    latest = state["logistics_messages"][-1]
                    yield f"\n__LOGISTICS__:{latest}\n"
                elif tool_name == "intel_agent" and "intel_messages" in state and state["intel_messages"]:
                    latest = state["intel_messages"][-1]
                    yield f"\n__INTEL__:{latest}\n"
                else:
                    yield f"\n__TOOL_CALL_RESULT__:Tool '{tool_name}' returned: {tool_output}\n"
            elif event.get("event") in ("on_chain_stream", "on_chain_end"):
                messages = []
                if "data" in event and "chunk" in event["data"] and "messages" in event["data"]["chunk"]:
                    messages = event["data"]["chunk"]["messages"]
                elif "data" in event and "output" in event["data"] and "messages" in event["data"]["output"]:
                    messages = event["data"]["output"]["messages"]
                if messages:
                    final_message = messages[-1].content
        if final_message:
            yield f"\n__FINAL__:{final_message}"
    return StreamingResponse(event_stream(), media_type="text/plain")

