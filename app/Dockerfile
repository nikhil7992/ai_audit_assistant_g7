FROM python:3.12-slim

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Pre-create data directories
RUN mkdir -p data/invoices data/forms data/ocr_output data/policies && \
    chown -R appuser:appuser data/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# PORT is exposed dynamically — ECS injects the correct port per service
# (8000=gateway, 8001=ocr, 8002=validation, 8003=duplicate, 8004=audit)
EXPOSE ${PORT}

# Health check uses $PORT so it works for every service, not just gateway
# The start-period gives uvicorn time to fully start before checks begin
HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=5 \
    CMD python3 -c \
        "import os, urllib.request; \
         urllib.request.urlopen('http://localhost:' + os.environ.get('PORT','8000') + '/health')" \
    || exit 1

USER appuser

# uvicorn binds to whatever PORT is injected by ECS at runtime
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
