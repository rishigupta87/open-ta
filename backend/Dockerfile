FROM python:3.9-slim

# Install Poetry
RUN pip install poetry

# Set the working directory
WORKDIR /app

# Copy the pyproject.toml and poetry.lock files
COPY pyproject.toml poetry.lock* /app/

# Install dependencies
RUN poetry install

# Copy the rest of the application files
COPY . .

# Expose the port FastAPI will run on and the debugging port
EXPOSE 8000 5678

# Command to run the FastAPI server
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
