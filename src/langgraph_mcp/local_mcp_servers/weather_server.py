from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Weather")


@mcp.tool()
def get_weather(city: str) -> str:
    """Get current weather for a city"""
    # Mock weather data - in real implementation, you'd call a weather API
    weather_data = {
        "nyc": "Sunny, 72°F",
        "london": "Cloudy, 65°F",
        "tokyo": "Rainy, 68°F",
        "paris": "Partly cloudy, 70°F",
    }
    return weather_data.get(city.lower(), f"Weather data not available for {city}")


@mcp.tool()
def get_forecast(city: str, days: int = 3) -> str:
    """Get weather forecast for a city"""
    return f"Forecast for {city}: Sunny for the next {days} days"


if __name__ == "__main__":
    mcp.run(transport="stdio")
