FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY eztiktok/ eztiktok/
COPY tt.py gui.py config.json.example CACHE_SPEC.md ./

ENV EZTIKTOK_DATA=/data
VOLUME ["/data"]
WORKDIR /data

ENTRYPOINT ["python", "/app/tt.py"]
CMD []
