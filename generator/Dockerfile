FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy generator and the canonical repo assets it needs (logo + scripts + recipes.json for local snapshot).
COPY generator/requirements.txt /app/generator/requirements.txt
RUN pip install --no-cache-dir -r /app/generator/requirements.txt

COPY generator /app/generator
COPY scripts /app/scripts
COPY assets/bloody_dave_logo.png /app/assets/bloody_dave_logo.png
COPY recipes.json /app/recipes.json
COPY Recipes /app/Recipes
COPY cards /app/cards
COPY assets/hero /app/assets/hero
COPY docs /app/docs

ENV PYTHONPATH=/app/generator
ENV JOB_WORK_DIR=/data/work
ENV AUTH_MODE=password

RUN mkdir -p /data/work

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/generator"]
