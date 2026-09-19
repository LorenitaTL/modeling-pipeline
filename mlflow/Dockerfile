FROM python:3.10-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "mlflow[extras]" psycopg2-binary boto3

EXPOSE 5000