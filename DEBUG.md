# 🐛 Debugging Open-TA in VSCode with Docker

This guide shows how to set up VSCode debugging for the Open-TA backend running in Docker containers.

## 🚀 Quick Start

### Option 1: Debug with Auto-Start (Recommended)
1. Open VSCode in the project root
2. Set breakpoints in your Python code (e.g., `backend/app/main.py`)
3. Press `F5` or go to **Run and Debug** → **Debug: Attach to Docker Backend**
4. The debugger will attach to the running container

### Option 2: Debug with Manual Control
1. Start containers with debug waiting:
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.debug.yml up -d
   ```
2. The backend will wait for debugger attachment
3. In VSCode: **Run and Debug** → **Debug: Wait for Docker Backend**
4. Set breakpoints and debug!

## 🔧 Configuration

### Environment Variables
- `DEBUG_ENABLED=true` - Enable debugpy
- `DEBUG_PORT=5678` - Debug port (must match VSCode config)
- `DEBUG_WAIT=true/false` - Wait for debugger before starting

### VSCode Configuration
The project includes pre-configured debugging setups:

**`.vscode/launch.json`**:
- **Debug: Attach to Docker Backend** - Connect to running container
- **Debug: Wait for Docker Backend** - Restart container and wait

**`.vscode/tasks.json`**:
- **restart-backend-with-wait** - Restart with debug waiting
- **restart-backend-no-wait** - Normal restart
- **stop-backend** - Stop backend container
- **logs-backend** - View backend logs

## 🎯 Debugging Workflow

### 1. Set Breakpoints
```python
# In backend/app/db/operations.py
def bulk_upsert_instruments(db: Session, instruments_data: List[Dict[str, Any]]) -> Dict[str, int]:
    """Bulk insert/update filtered instruments in database"""
    breakpoint()  # Or set VSCode breakpoint here
    try:
        stats = {"inserted": 0, "updated": 0, "errors": 0, "filtered_out": 0}
        # ... rest of function
```

### 2. Start Debugging
**Quick Method**:
- Press `F5` → Select **Debug: Attach to Docker Backend**

**Manual Method**:
```bash
# Terminal 1: Start with debug waiting
docker-compose -f docker-compose.yml -f docker-compose.debug.yml up -d backend

# Terminal 2: Watch logs
docker-compose logs -f backend

# VSCode: Attach debugger
```

### 3. Test Your Code
```bash
# Trigger the function you want to debug
curl -X POST -H "Content-Type: application/json" \
  -d '{"query":"mutation { syncInstruments(forceRefresh: true) { success message } }"}' \
  http://localhost:8000/graphql
```

## 🛠️ Troubleshooting

### Debugger Won't Attach
1. Check if backend is running: `docker-compose ps`
2. Check if port 5678 is exposed: `docker-compose port backend 5678`
3. View backend logs: `docker-compose logs backend`

### Breakpoints Not Hitting
1. Ensure path mappings are correct in `.vscode/launch.json`
2. Check `localRoot` matches your local path structure
3. Verify `remoteRoot` matches container path (`/app`)

### Container Keeps Restarting
1. Check for syntax errors in your Python code
2. View logs: `docker-compose logs backend`
3. Disable debug waiting: Set `DEBUG_WAIT=false`

## 📝 Debug Commands

```bash
# Start with debug enabled
docker-compose up -d

# Start with debug waiting (for manual attachment)
docker-compose -f docker-compose.yml -f docker-compose.debug.yml up -d

# Restart backend only
docker-compose restart backend

# View real-time logs
docker-compose logs -f backend

# Execute commands in container
docker-compose exec backend bash

# Check debug port
docker-compose port backend 5678
```

## 🎯 Common Debug Scenarios

### Debug Instrument Sync
1. Set breakpoint in `backend/app/db/operations.py:bulk_upsert_instruments`
2. Trigger: GraphQL mutation `syncInstruments`
3. Inspect `instruments_data`, `filtered_instruments`, etc.

### Debug Streaming
1. Set breakpoint in `backend/app/streaming/market_data_streamer.py`
2. Trigger: GraphQL mutation `startEnhancedStreaming`
3. Step through token generation and streaming logic

### Debug API Calls
1. Set breakpoint in `backend/app/graphql/mutations.py`
2. Make GraphQL request from browser/curl
3. Inspect request parameters and response building

## 🔗 Useful Links
- [debugpy Documentation](https://github.com/microsoft/debugpy)
- [VSCode Python Debugging](https://code.visualstudio.com/docs/python/debugging)
- [Docker Debugging Guide](https://code.visualstudio.com/docs/containers/debug-python)
