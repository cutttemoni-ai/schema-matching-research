FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
COPY requirements-gcp.lock.txt ./
RUN pip install --no-cache-dir -r requirements-gcp.lock.txt
# Allowlist: credentials, runs, datasets, experiments and D product code stay out.
COPY schema_match/__init__.py schema_match/config.py schema_match/models.py schema_match/files.py schema_match/profiles.py schema_match/records.py schema_match/review.py schema_match/vertex_provider_v1.py schema_match/vertex_budget_v1_2.py schema_match/cloud_c_service.py ./schema_match/
COPY config/gcp_research_v1.json config/gcp_budget_v1_2.json config/comparison_v0.json ./config/
COPY schemas ./schemas
COPY examples ./examples
COPY cloud_app.py PROFILE_SPEC.md GEMINI_EVALUATION_RESULTS.md ./
USER 65532:65532
EXPOSE 8080
CMD ["sh", "-c", "exec streamlit run cloud_app.py --server.address=0.0.0.0 --server.port=${PORT:-8080} --server.headless=true --server.maxUploadSize=1 --browser.gatherUsageStats=false"]
