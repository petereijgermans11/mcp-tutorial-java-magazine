import asyncio
from pathlib import Path
from langchain_core.messages import HumanMessage, AnyMessage
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import tools_condition, ToolNode
from pydantic import BaseModel
from typing import Annotated, List
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph_mcp.configuration import get_llm

"""
LangGraph ReAct Agent with Multiple MCP Servers

Flow: Human Question → Assistant (calls MCP tools from multiple servers) → Tool Execution → Assistant (final answer)

Example:
  Human: "What's 3 + 4 and what's the weather in NYC?"
  Assistant: *calls math add(3, 4) and weather get_weather("nyc")*
  MCP Tools: returns 7 and "Sunny, 72°F"
  Assistant: "3 + 4 = 7. Weather in NYC is Sunny, 72°F"
"""


# Define the state of the graph.
class MessageState(BaseModel):
    messages: Annotated[List[AnyMessage], add_messages]


def create_assistant(llm_with_tools):
    """Create an assistant function with access to the LLM"""

    async def assistant(state: MessageState):
        state.messages = await llm_with_tools.ainvoke(state.messages)
        return state

    return assistant


def build_graph(tools):
    """Build and return the LangGraph ReAct agent with MCP tools"""
    llm = get_llm("openai")
    llm_with_tools = llm.bind_tools(tools)

    builder = StateGraph(MessageState)
    # Define nodes
    builder.add_node("assistant", create_assistant(llm_with_tools))
    builder.add_node("tools", ToolNode(tools))
    # Define edges
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges(
        "assistant",
        tools_condition,
    )
    # note: The tool call output will be sent back to the assistant node (to 'summarize' the tool call)
    builder.add_edge("tools", "assistant")

    memory = MemorySaver()
    react_graph_memory = builder.compile(checkpointer=memory)
    return react_graph_memory


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


async def run_mcp_agent(input_state):
    """Load MCP tools from multiple servers and run the LangGraph agent"""
    current_dir = Path(__file__).parent

    all_servers = {
        "math": {
            "command": "python",
            "args": [str(current_dir / "local_mcp_servers" / "math_server.py")],
            "transport": "stdio",
        },
        "weather": {
            "command": "python",
            "args": [str(current_dir / "local_mcp_servers" / "weather_server.py")],
            "transport": "stdio",
        },
    }

    successful_servers = await validate_servers(all_servers)

    if successful_servers:
        client = MultiServerMCPClient(successful_servers)
        tools = await client.get_tools()

        print(
            f"Loaded {len(tools)} MCP tools from {len(successful_servers)} server(s):"
        )
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")
    else:
        print("No servers loaded! Terminating.")
        raise RuntimeError("No MCP servers available")

    graph = build_graph(tools)
    config = {"configurable": {"thread_id": "1"}}

    # Test with math question
    result = await graph.ainvoke(input_state, config)

    return result


if __name__ == "__main__":
    input_state = {"messages": [HumanMessage(content="What's (3 + 5) * 12?")]}
    result = asyncio.run(run_mcp_agent(input_state))
    for m in result["messages"]:
        m.pretty_print()

    input_state = {
        "messages": [HumanMessage(content="What's the weather forecast in london?")]
    }
    result = asyncio.run(run_mcp_agent(input_state))
    for m in result["messages"]:
        m.pretty_print()
