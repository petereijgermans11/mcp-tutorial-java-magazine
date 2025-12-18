FROM python:3.12-slim

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy dependency files
COPY pyproject.toml ./

# Configure Poetry to not create virtual environment
RUN poetry config virtualenvs.create false

# Install dependencies (without lock file to avoid sync issues)
RUN poetry install --without dev --no-interaction --no-ansi --no-root

# Copy application code
COPY src/ ./src/

# Set PYTHONPATH to include src directory
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8000

# Run the FastAPI application
CMD ["python", "-m", "uvicorn", "langgraph_mcp.04_mcp_http_external_package:app", "--host", "0.0.0.0", "--port", "8000"]

