FROM python:3.12-slim
RUN pip install --no-cache-dir duckdb==1.1.3 pandas==2.2.3
WORKDIR /app
COPY normalize_usage.py /app/
ENTRYPOINT ["python", "/app/normalize_usage.py"]
