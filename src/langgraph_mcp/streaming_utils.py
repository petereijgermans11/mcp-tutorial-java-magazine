"""Shared streaming utilities for LangGraph chat endpoints"""

from fastapi import Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import (
    HumanMessage,
    ToolMessage,
    AIMessage,
    SystemMessage,
    AnyMessage,
)
import uuid
import re
import json


async def create_event_stream(
    langgraph_app, user_input: str, thread_id: str, verbose: bool = False
):
    """Create an async generator that streams LangGraph events to the frontend"""
    config = {"configurable": {"thread_id": thread_id}}
    tool_results_shown = set()
    tool_calls_shown = set()
    final_message = None
    last_printed_index = -1
    messages_printed = set()

    async for event in langgraph_app.astream_events(
        {"messages": [HumanMessage(content=user_input)]}, config=config
    ):
        event_type = event.get("event")

        if event_type == "on_chat_model_start" and verbose:
            run_id = event.get("run_id")
            if run_id and run_id not in messages_printed:
                messages_printed.add(run_id)
                data = event.get("data", {})
                input_data = data.get("input")
                if isinstance(input_data, list):
                    messages = input_data
                elif isinstance(input_data, dict):
                    messages = input_data.get("messages", [])
                else:
                    messages = data.get("messages", [])

                if messages and isinstance(messages, list):
                    while (
                        messages
                        and len(messages) == 1
                        and isinstance(messages[0], list)
                    ):
                        messages = messages[0]
                    if messages and len(messages) > 0:
                        _print_message_sequence(messages, skip_final_separator=True)
                        last_printed_index = len(messages) - 1

        if event_type == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content + " "

        # Tool calls
        if event_type == "on_tool_start":
            tool_name = event.get("name", "tool")
            tool_args = event.get("data", {}).get("input", {})
            # Use run_id to deduplicate tool calls
            tool_run_id = event.get("run_id")
            if tool_run_id and tool_run_id not in tool_calls_shown:
                tool_calls_shown.add(tool_run_id)
                yield f"\n__TOOL_CALL__:Calling tool '{tool_name}' with args {tool_args}\n"

        if event_type == "on_tool_end":
            tool_name = event.get("name", "tool")
            # LangGraph on_tool_end events have run_id at the top level (unique UUID per tool call)
            tool_id = event.get("run_id")
            tool_output = event.get("data", {}).get("output", "")

            if isinstance(tool_output, ToolMessage):
                tool_output = tool_output.content

            tool_output = _clean_tool_output(str(tool_output))

            if tool_id not in tool_results_shown:
                yield f"\n__TOOL_CALL_RESULT__:Tool '{tool_name}' returned: {tool_output}\n"
                tool_results_shown.add(tool_id)

        if event_type == "on_chain_end" and final_message is None:
            event_name = event.get("name", "")
            tags = event.get("tags", {})
            if event_name in ("LangGraph", "") and "node" not in tags:
                messages = event.get("data", {}).get("output", {}).get("messages", [])
                if messages:
                    final_message = _extract_final_message(messages)
                    if final_message and verbose:
                        final_index = last_printed_index + 1
                        content_preview = " ".join(final_message.split())[:50]
                        print(
                            f"  [{final_index}] AIMessage: content='{content_preview}...'"
                        )
                        print(f"{'='*60}\n")

    if final_message:
        yield f"\n__FINAL__:{final_message}"


async def chat_endpoint_handler(
    request: Request, user_input: str, thread_id: str = None, verbose: bool = False
):
    """Handle chat endpoint - streams LangGraph events to frontend"""
    # Ensure thread_id is valid and unique
    if not thread_id or (isinstance(thread_id, str) and not thread_id.strip()):
        thread_id = str(uuid.uuid4())

    langgraph_app = request.app.state.langgraph_app
    return StreamingResponse(
        create_event_stream(langgraph_app, user_input, thread_id, verbose),
        media_type="text/plain",
    )


def _clean_tool_output(tool_output: str) -> str:
    """
    Extract and pretty-print JSON content from Supabase MCP tool output.
    MCP server wraps tool results in JSON.stringify().
    """
    # Parse outer JSON (MCP server wraps all results in JSON.stringify)
    try:
        outer_parsed = json.loads(tool_output)
        if isinstance(outer_parsed, str):
            inner_output = outer_parsed
        else:
            return json.dumps(outer_parsed, indent=2)
    except (json.JSONDecodeError, ValueError):
        inner_output = tool_output

    # Extract JSON from <untrusted-data> tags if present
    uuid_match = re.search(r"<untrusted-data-([^>]+)>", inner_output)
    if uuid_match:
        uuid = uuid_match.group(1)
        pattern = rf"<untrusted-data-{re.escape(uuid)}>(.*?)</untrusted-data-{re.escape(uuid)}>"
        match = re.search(pattern, inner_output, re.DOTALL)
        if match:
            # Extract JSON data between tags, removing any verbose text before/after
            json_data = match.group(1).strip()
            json_data = re.sub(r"^[^[{]*", "", json_data)
            last_bracket = max(json_data.rfind("]"), json_data.rfind("}"))
            if last_bracket >= 0:
                json_data = json_data[: last_bracket + 1]
            json_data = json_data.strip()
            try:
                parsed_json = json.loads(json_data)
                return json.dumps(parsed_json, indent=2)
            except (json.JSONDecodeError, ValueError):
                return json_data

    # Try to parse as JSON
    try:
        parsed_json = json.loads(inner_output)
        return json.dumps(parsed_json, indent=2)
    except (json.JSONDecodeError, ValueError):
        return inner_output


def _extract_final_message(messages: list) -> str | None:
    """Extract final AIMessage with finish_reason='stop' from message list"""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            finish_reason = getattr(msg, "response_metadata", {}).get(
                "finish_reason", ""
            )
            if finish_reason == "stop":
                msg_content = str(msg.content)
                if msg_content.strip():
                    return msg_content


def truncate_messages_safely(
    messages: list[AnyMessage], max_history: int = 20
) -> list[AnyMessage]:
    """
    Truncate message history while preserving tool call sequences.
    Removes system messages and limits to max_history messages.
    ToolMessages must immediately follow their AIMessage with tool_calls.
    """
    # Remove any existing system messages
    messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]

    if len(messages) <= max_history:
        return messages

    # Take the last max_history messages
    start_idx = len(messages) - max_history
    truncated = messages[start_idx:]

    # If first message is a ToolMessage, we need its AIMessage
    if truncated and isinstance(truncated[0], ToolMessage):
        # Find the AIMessage before truncation point
        for i in range(start_idx - 1, -1, -1):
            msg = messages[i]
            if isinstance(msg, AIMessage) and msg.tool_calls:
                # Include this AIMessage and all its ToolMessages (up to truncation point)
                result = [msg]
                j = i + 1
                while j < start_idx and isinstance(messages[j], ToolMessage):
                    result.append(messages[j])
                    j += 1
                # Add truncated messages (which already includes ToolMessages from start_idx onwards)
                result.extend(truncated)
                return result

    # If we cut off an AIMessage with tool_calls, include it (ToolMessages are already in truncated)
    if start_idx > 0:
        prev_msg = messages[start_idx - 1]
        if isinstance(prev_msg, AIMessage) and prev_msg.tool_calls:
            # ToolMessages following this AIMessage are already in truncated
            return [prev_msg] + truncated

    return truncated


def _print_message_sequence(messages: list, skip_final_separator: bool = False):
    """Print message sequence for verbose debugging"""
    print(f"\n{'='*60}")
    print(f"ASSISTANT: Message sequence ({len(messages)} messages):")
    for i, msg in enumerate(messages):
        msg_type = type(msg).__name__
        # Add blank line before HumanMessage
        if msg_type == "HumanMessage":
            print()

        # Remove newlines and truncate content to 50 chars
        if hasattr(msg, "content") and msg.content:
            content_preview = " ".join(str(msg.content).split())[:50]
        else:
            content_preview = "N/A"

        # For AIMessage with tool_calls, show tool_calls count but not ids
        if msg_type == "AIMessage" and hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_call_count = len(msg.tool_calls)
            print(
                f"  [{i}] {msg_type}: tool_calls={tool_call_count}, content='{content_preview}...'"
            )
        else:
            # For all other messages (including ToolMessage), just show content
            print(f"  [{i}] {msg_type}: content='{content_preview}...'")
    # Only print separator if not skipping (i.e., if we're not going to add final message)
    if not skip_final_separator:
        print(f"{'='*60}\n")
