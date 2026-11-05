FROM python:3.12.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY apps/api/requirements /requirements
RUN CFLAGS="-O0 -g0" pip install --no-cache-dir -r /requirements/production.txt
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /code
COPY apps/api /code
COPY scripts/kitchen/verify-app/verify_settings.py /code/plane/settings/kitchen_verify.py
