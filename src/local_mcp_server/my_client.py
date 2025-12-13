from fastmcp import Client
import asyncio

async def demo():
    client = Client("my_server.py")
    async with client:
        tools = await client.list_tools()
        print("Available tools:", tools)
        result = await client.call_tool("divide", {"a": 49, "b": 7})
        print("divide(49, 7) =", result)

asyncio.run(demo())