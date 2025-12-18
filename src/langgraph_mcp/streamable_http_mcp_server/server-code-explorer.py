"""
Code Explorer MCP Server
Code explorer MCP server to explore Python files and functions -> expose with Streamable HTTP
"""

import os
from pathlib import Path
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("code-explorer")

# Get the root directory of the repository
REPO_ROOT = Path(__file__).parent.parent.resolve()


@mcp.tool()
def list_all_files(folder: str = "src/langgraph_mcp") -> str:
    """
    Show all files and folders in a directory as a tree structure.

    CRITICAL: This tool returns output formatted with tree characters (├── and └──).
    You MUST display the output EXACTLY as received - DO NOT reformat, categorize, or convert to bullet points.
    DO NOT split into "Folders:" and "Files:" sections. DO NOT change the structure.
    Simply show the tree output exactly as returned by the tool.

    Example of correct output format:
    src/langgraph_mcp/
    ├── static/
    ├── 01_agent_basics.py (12.5 KB)
    └── configuration.py (2.1 KB)

    Args:
        folder: Folder path (default: "src/langgraph_mcp"). Use "/" or "." for repository root.
    """
    target = _normalize_path(folder)

    # Validate path is within repo root (prevents ../ attacks)
    _validate_path(target)

    if not target.exists():
        return f"Folder '{folder}' not found"

    # Skip common ignored items
    ignore = {".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache"}

    items = []
    contents = sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name))

    for i, item in enumerate(contents):
        if item.name in ignore:
            continue

        is_last = i == len(contents) - 1
        prefix = "└── " if is_last else "├── "

        if item.is_dir():
            items.append(f"{prefix}{item.name}/")
        else:
            size = item.stat().st_size / 1024
            items.append(f"{prefix}{item.name} ({size:.1f} KB)")

    if not items:
        return f"{folder} is empty"

    result = f"{folder}/\n"
    result += "\n".join(items)

    return result


@mcp.tool()
def list_python_files(folder: str = "src/langgraph_mcp") -> str:
    """
    Show only Python files in a folder.

    Args:
        folder: Folder path (default: "src/langgraph_mcp"). Use "/" or "." for repository root.
    """
    target = _normalize_path(folder)

    # Validate path is within repo root
    _validate_path(target)

    if not target.exists():
        return f"Folder '{folder}' not found"

    files = []
    for file in sorted(target.glob("*.py")):
        size = file.stat().st_size / 1024
        files.append(f"{file.name} ({size:.1f} KB)")

    if not files:
        return f"No Python files in '{folder}'"

    result = f"Python files in {folder}:\n\n"
    result += "\n".join(files)
    return result


@mcp.tool()
def show_functions(file_path: str) -> str:
    """
    Show all functions in a Python file.

    Args:
        file_path: Path to Python file (e.g., "src/langgraph_mcp/configuration.py"). Must be within repository root.
    """
    # Normalize path (remove leading slashes)
    file_path = file_path.lstrip("/\\")
    target = REPO_ROOT / file_path

    # Validate path is within repo root
    _validate_path(target)

    if not target.exists():
        return f"File '{file_path}' not found"

    with open(target, "r", encoding="utf-8") as f:
        lines = f.readlines()

    functions = []
    for line_num, line in enumerate(lines, 1):
        if line.strip().startswith("def ") or line.strip().startswith("async def "):
            func_name = (
                line.strip().split("(")[0].replace("def ", "").replace("async ", "")
            )
            functions.append(f"{func_name}() at line {line_num}")

    if not functions:
        return f"No functions found in {file_path}"

    result = f"Functions in {file_path}:\n\n"
    result += "\n".join(functions)
    return result


@mcp.tool()
def read_function(file_path: str, function_name: str) -> str:
    """
    Read the source code of a function.

    Args:
        file_path: Path to Python file. Must be within repository root.
        function_name: Name of function to read
    """
    # Normalize path (remove leading slashes)
    file_path = file_path.lstrip("/\\")
    target = REPO_ROOT / file_path

    # Validate path is within repo root
    _validate_path(target)

    if not target.exists():
        return f"File '{file_path}' not found"

    with open(target, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find function start
    start = None
    indent_level = None

    for i, line in enumerate(lines):
        if f"def {function_name}(" in line or f"async def {function_name}(" in line:
            start = i
            indent_level = len(line) - len(line.lstrip())
            break

    if start is None:
        return f"Function '{function_name}' not found"

    # Get function body (stops at next function or class)
    code_lines = []
    for i in range(start, len(lines)):
        line = lines[i]

        # Stop if we hit another function/class at same indent level
        if (
            i > start
            and line.strip()
            and len(line) - len(line.lstrip()) <= indent_level
        ):
            if line.strip().startswith("def ") or line.strip().startswith("class "):
                break

        code_lines.append(line.rstrip())

    result = f"Function: {function_name}()\n"
    result += f"From: {file_path}\n\n"
    result += "\n".join(code_lines)

    return result


# Helper functions
def _normalize_path(folder: str) -> Path:
    """
    Normalize folder path to repo root.
    Converts "/", ".", or empty string to repo root.
    """
    # Normalize root paths to empty string (which means repo root)
    if folder in ("/", ".", ""):
        return REPO_ROOT

    # Remove leading slashes
    folder = folder.lstrip("/\\")

    return REPO_ROOT / folder


def _validate_path(path: Path) -> None:
    """
    Validate that a path is within REPO_ROOT.
    Raises ValueError if path is outside the repository root.
    Prevents directory traversal attacks (e.g., ../../).
    """
    try:
        resolved = path.resolve()
        repo_resolved = REPO_ROOT.resolve()

        # Use is_relative_to for Python 3.9+ (more robust than string comparison)
        try:
            # Check if resolved path is relative to repo root
            resolved.relative_to(repo_resolved)
        except ValueError:
            # Path is outside repo root
            raise ValueError(
                f"Path '{path}' is outside the repository root. Access denied."
            )
    except (OSError, ValueError) as e:
        raise ValueError(f"Invalid path: {e}")


if __name__ == "__main__":
    print("Code Explorer MCP Server")

    port = int(os.getenv("PORT", 8001))

    # Run with streamable-http transport
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
