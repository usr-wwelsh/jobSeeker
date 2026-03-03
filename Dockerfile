# Used for Railway deployment (optional — all functionality works locally)
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# data/ is mounted as a Railway persistent volume at runtime
# so chroma_data/ and jobs.db survive redeploys
VOLUME ["/app/data"]

CMD ["uvicorn", "dashboard.app:app", "--host", "0.0.0.0", "--port", "8080"]
