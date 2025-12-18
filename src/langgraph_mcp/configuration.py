from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_llm(llm_type="openai"):
    """
    Returns an LLM instance.
    llm_type: "qwen" (default) or "openai"
    """
    if llm_type == "openai":
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        model = os.getenv("AZURE_OPENAI_MODEL", "gpt-4o")
        version = os.getenv("AZURE_OPENAI_MODEL_VERSION", "2024-08-01-preview")
        return AzureChatOpenAI(
            api_key=api_key, azure_endpoint=endpoint, api_version=version, model=model
        )
    else:
        return ChatOllama(model="qwen3:8b")


if __name__ == "__main__":
    llm = get_llm(llm_type="openai")
    print(llm.invoke("Hello, how are you?").content)
