---
theme: '@slidev/theme-seriph'
layout: cover
---

# Setting Up Agentic Workflows in Python

---
layout: default
---

# Table of Contents

- Building Agentic Workflows in Python with AWS
- Parallel Agentic Workflows in Python
- Agentic Workflows with Vanilla Python
- Autonomous Systems in Python
- Agent UI Trends

---
layout: default
---

# Building Agentic Workflows in Python with AWS
A hands-on walkthrough focused on integrating Amazon Bedrock for scalable hosting environments.

Key insights: serverless deployment, tool orchestration using BedrockAgentCore.

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()
@app.entrypoint
def run_task(payload):
    return agent(payload)
if __name__ == "__main__":
    app.run()
```
---
layout: default
---

# Parallel Agentic Workflows in Python
Tutorial using Python asyncio for fast and accurate agent operations.

Reduction in latency by utilizing asynchronous API calls.

```python
import asyncio
import aiohttp

async def fetch_url(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

urls = ['https://example.com']
responses = asyncio.run(asyncio.gather(*(fetch_url(url) for url in urls)))
```
---
layout: default
---

# Agentic Workflows with Vanilla Python
Focus on simplicity and reducing complexity by eliminating frameworks.

Core logic using Python alone.
---
layout: default
---

# Autonomous Systems in Python
Design principles such as perception, decision-making, and action implementation.

Use cases discussed include customer bots and IoT orchestration.
---
layout: default
---

# Agent UI Trends
Insights into MCP design challenges and integrating workflows with tangible UI design frameworks.
---