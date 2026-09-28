FROM python:3.11-slim

ARG INSTALL_ML=true
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt requirements-ml.txt ./
RUN pip install -r requirements.txt \
 && if [ "$INSTALL_ML" = "true" ]; then \
      pip install torch --index-url https://download.pytorch.org/whl/cpu && \
      pip install -r requirements-ml.txt ; \
    fi

COPY app ./app
RUN mkdir -p /app/data/references
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
