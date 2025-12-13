
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
