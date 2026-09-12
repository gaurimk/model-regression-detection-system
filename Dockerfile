FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal on purpose -- this image has no compiled
# dependencies that need build tools.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Configured via environment variables at `docker run` time:
#   OPENAI_API_KEY, OPENAI_MODEL, SLACK_WEBHOOK_URL
# Threshold configs live in config.yaml and can be overridden by
# mounting a replacement file at /app/config.yaml.
ENTRYPOINT ["python", "run_eval.py"]
CMD ["--prompt-version", "prompts/v1.yaml"]
