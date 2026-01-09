# Firecrawl → Slidev → Filesystem → Git Flow

This document describes the state-loss-resistant workflow for automated slide generation.

## Architecture Overview

```
User Prompt → Firecrawl MCP → research_notes.md → Filesystem MCP → slides.md → Git MCP
```

## Flow Details

### 1. **Firecrawl MCP** (Research)
- Uses `firecrawl_search` to gather web data
- Limits results to 3 items
- Writes findings to `research_notes.md`

### 2. **Filesystem MCP** (Memory & Slide Generation)
- **Acts as durable memory**: Always read files before editing
- Reads `research_notes.md` to get research data
- Reads existing `slides.md` to see current state (prevents state loss)
- Writes/updates `slides.md` with Slidev format
- File location: `/Users/petereijgermans/Desktop/mcp-tutorial-java-magazine/my-slides/slides.md`

### 3. **Slidev** (Presentation Engine)
- Automatically watches `slides.md` for changes
- Live preview at `http://localhost:3030`
- Uses Slidev syntax with layouts, themes, and code highlighting

### 4. **Git MCP** (Version Control)
- Checks `git_status` before committing
- Creates feature branch if needed
- Stages and commits changes

## State Loss Prevention

### Why This Flow Prevents State Loss:

1. **Filesystem as Memory**: The agent always reads files before editing, so it can "resume" by reading the current state
2. **Explicit File Operations**: Using `read_text_file` before `write_file` or `edit_file` ensures context is maintained
3. **Increased Message History**: Set to 40 messages to preserve conversation context
4. **No Stateful Server Dependencies**: Filesystem MCP is stateless - files are the source of truth

### Anti-State Loss Rules:

- ✅ **ALWAYS** read `slides.md` before editing
- ✅ **ALWAYS** read `research_notes.md` before generating slides
- ✅ Use `list_directory` to verify paths before operations
- ✅ Check `git_status` before committing

## Setup Instructions

1. **Run the Slidev setup script:**
   ```bash
   ./setup_slidev.sh
   ```

2. **Start the Slidev dev server (optional, for live preview):**
   ```bash
   cd my-slides
   npm run dev
   ```

3. **Start the LangGraph agent:**
   ```bash
   poetry run python src/langgraph_mcp/03_mcp_stdio_external_package.py
   ```

4. **Use the web interface at:** `http://localhost:8000`

## Example Workflow

**User Prompt:** "Research AI hardware and make a slide."

1. **Firecrawl**: Searches for "AI hardware" → writes to `research_notes.md`
2. **Filesystem MCP**: 
   - Reads `research_notes.md`
   - Reads existing `slides.md`
   - Writes formatted Slidev content to `slides.md`
3. **Slidev**: Automatically detects change → updates browser view
4. **Git MCP**: Creates branch, stages files, commits

## File Locations

- Research notes: `/Users/petereijgermans/Desktop/mcp-tutorial-java-magazine/research_notes.md`
- Slides: `/Users/petereijgermans/Desktop/mcp-tutorial-java-magazine/my-slides/slides.md`
- Agent: `src/langgraph_mcp/03_mcp_stdio_external_package.py`

## Slidev Syntax Reference

```markdown
---
theme: seriph
background: https://source.unsplash.com/collection/94734566/1920x1080
class: text-center
highlighter: shiki
---

# Slide Title
Content here

---
layout: section

# Section Slide

---
layout: fact

# Fact Slide
Some interesting fact

---
layout: default

# Code Example

\`\`\`python
def hello():
    print("Hello, Slidev!")
\`\`\`
```

## Troubleshooting

- **State Loss**: Ensure the agent reads files before editing
- **File Not Found**: Check `list_directory` to verify paths
- **Git Errors**: Always check `git_status` before `git_add`
- **Slidev Not Updating**: Restart the dev server if needed

