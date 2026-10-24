FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir falkordb==1.7.1 pytest==9.1.1

COPY pyproject.toml ./
COPY warmopen/ ./warmopen/
COPY tests/ ./tests/
COPY data/seed_public.json ./data/seed_public.json

EXPOSE 8080
CMD ["python", "-m", "warmopen.cli", "serve", "--host", "0.0.0.0", "--port", "8080"]
