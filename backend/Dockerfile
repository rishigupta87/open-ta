FROM python:3.12-slim as base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Configure poetry
RUN poetry config virtualenvs.create false

# Install dependencies with --no-root flag to avoid installing the current project
RUN poetry lock && poetry install --no-root

# Install debugpy for remote debugging
RUN pip install debugpy scipy

# Development stage with hot reloading
FROM base as development

# Set environment variables for development
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Copy the rest of the application
COPY . .

# Make start_debug.py executable
RUN chmod +x start_debug.py

# Command to run the application (supports both normal and debug mode)
CMD ["python", "start_debug.py"]

# Production stage
FROM base as production

# Copy the rest of the application
COPY . .

# Make start_debug.py executable
RUN chmod +x start_debug.py

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
