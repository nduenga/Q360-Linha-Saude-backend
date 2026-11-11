FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-writer fonts-liberation fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system q360 \
    && useradd --system --gid q360 --home-dir /app q360

WORKDIR /app
COPY requirements.render.txt ./requirements.render.txt
RUN pip install --no-cache-dir -r requirements.render.txt
COPY --chown=q360:q360 . .
RUN mkdir -p /app/media /tmp/q360-home \
    && chown -R q360:q360 /app/media /tmp/q360-home

USER q360
ENV HOME=/tmp/q360-home

EXPOSE 10000
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers ${WEB_CONCURRENCY:-2} --access-logfile -"]
