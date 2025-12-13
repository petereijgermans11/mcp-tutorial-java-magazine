import os
from dotenv import load_dotenv

load_dotenv()
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_MODEL_VERSION = "2024-06-01" # "2023-07-01-preview"
AZURE_OPENAI_MODEL = "gpt-4o"

# TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")