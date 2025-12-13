# MCP-Langgraph Integration Tutorial
This tutorial demonstrates how to integrate Model Context Protocol (MCP) servers with Langgraph agents to create powerful, tool-enabled AI applications

We’ll build a working MCP tool in Python — an AI Commander that can execute calculations, generate intel, and manage logistics with precision.|

## Prerequisites
Python 3.13+ installed
Git installed (to clone the starter code)
Basic Python knowledge

Clone the AO (Area of Operations)

Bash
~~~
git clone https://github.com/petereijgermans11/mcp-tutorial.git

cd mcp-tutorial
~~~



Your base camp contains:

main.py (command center)
run.py (FastAPI launcher)
static/ (frontline comms)
SQLite bunkers (for persistent memory)



1. Define your environment settings in your .env file
~~~
touch .env
~~~

~~~
GITLAB_PERSONAL_ACCESS_TOKEN = 
AZURE_OPENAI_API_KEY = 
AZURE_OPENAI_ENDPOINT =
~~~

and add your .env file to gitignore
~~~
echo ".env" >> .gitignore
~~~

