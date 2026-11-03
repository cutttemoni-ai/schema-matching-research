FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements-gcp.lock.txt ./
RUN pip install --no-cache-dir -r requirements-gcp.lock.txt
COPY schema_match ./schema_match
COPY scripts ./scripts
COPY config ./config
COPY schemas ./schemas
USER 65532:65532
ENTRYPOINT ["python", "scripts/gcp_job.py"]
CMD ["--help"]
