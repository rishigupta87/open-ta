# Open-TA Agent Instructions

## Build/Test/Lint Commands
- **Backend**: `cd backend && poetry run python -m app.main` (dev server)
- **Frontend**: `cd frontend && streamlit run app.py` (or via Docker)
- **Docker**: `docker-compose up` (full stack with Redis)
- **Backend tests**: `cd backend && poetry run pytest` (framework available but no tests yet)
- **Health check**: `curl -X POST -H "Content-Type: application/json" -d '{"query":"query { health { status } }"}' http://localhost:8000/graphql`

## Architecture
- **Backend**: FastAPI + GraphQL-first (Strawberry) + WebSocket for real-time data
- **Frontend**: Streamlit dashboard for real-time market data visualization
- **Database**: PostgreSQL via SQLAlchemy ORM, Redis for real-time data & pub/sub
- **Trading**: SmartAPI integration with real-time streaming, WebSocket market data
- **Docker**: Multi-service setup (backend:8000, frontend:8501, redis:6379, postgres:5432)
- **GraphQL**: Single endpoint at /graphql with queries/mutations, playground available
- **Instruments**: 120K+ trading instruments synced from AngelOne OpenAPI to PostgreSQL

## Code Style
- **Python**: Follow PEP 8, use type hints, dataclasses for models
- **Dependencies**: Poetry for backend, Python 3.12+, requirements in pyproject.toml
- **Structure**: app/graphql/ (types, queries, mutations, schema), trading/, streaming/
- **GraphQL**: Use Strawberry decorators (@strawberry.type, @strawberry.field, @strawberry.mutation)
- **WebSocket**: Real-time market data at /ws/market-data/{symbol}
- **Config**: Secrets in config.py (contains API keys - handle carefully)
- **Redis**: Pub/sub streaming, keys: websocket-data:{category}:stream:{timestamp}
