FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Install watchdog for hot reload
RUN pip install watchdog

COPY . .

CMD ["python", "bridge_main.py"]