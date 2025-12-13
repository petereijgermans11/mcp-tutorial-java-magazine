# server_divide.py
from fastapi import FastAPI
from fastmcp import FastMCP

# Create the main FastAPI application instance
app = FastAPI()


# Create your MCP server instance
mcp = FastMCP("My MCP Server")
mcp_app = mcp.from_fastapi(app)
@mcp.tool
def divide(a: float, b: float) -> float:
    """Divide two numbers and return the result."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

# Mount the MCP server as a sub-application
#app.mount("/mcp", mcp_app)

# No need for if __name__ == "__main__": mcp.run()

if __name__ == "__main__":
    mcp.run(transport="stdio")