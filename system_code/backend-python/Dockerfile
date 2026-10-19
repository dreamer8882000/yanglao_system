FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY system_code/backend-python/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY system_code/backend-python/app ./app
COPY expression_recognition ./expression_recognition
COPY third_party ./third_party
COPY thesis_assets ./thesis_assets
COPY legacy ./legacy
ENV PYTHONPATH=/app

EXPOSE 8090
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
