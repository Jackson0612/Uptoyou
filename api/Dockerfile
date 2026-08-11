# The host runs Python 3.9, which is end of life. The container carries a current one —
# that split is deliberate and is why nothing here depends on the host interpreter.
FROM python:3.13-slim

# Fail fast and log immediately: a buffered stdout hides the startup error that matters.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/srv/src

WORKDIR /srv

# Requirements first, so a source edit does not reinstall the world.
COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

COPY src /srv/src

# Not root inside the container. The daemon itself is rootful (D10) because the success
# criterion is literally `docker compose up`, but that is no reason for the application
# process to be root as well.
RUN useradd --system --uid 10001 --no-create-home upto
USER 10001

EXPOSE 8000

CMD ["uvicorn", "upto.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
