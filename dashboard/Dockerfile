FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Copy parent .env and services for imports
COPY ../.env /app/.env 2>/dev/null || true
EXPOSE 8080
CMD ["python", "server.py", "8080"]
