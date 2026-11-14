FROM python:3.12-slim-bookworm

ARG INTER_VERSION=4.1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-writer fonts-liberation fonts-dejavu-core fontconfig curl unzip ca-certificates \
    && curl -fsSL -o /tmp/inter.zip "https://github.com/rsms/inter/releases/download/v${INTER_VERSION}/Inter-${INTER_VERSION}.zip" \
    && mkdir -p /usr/local/share/fonts/inter \
    && unzip -j -o /tmp/inter.zip 'extras/ttf/*.ttf' -d /usr/local/share/fonts/inter \
    && fc-cache -f \
    && rm -f /tmp/inter.zip \
    && apt-get purge -y curl unzip && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system q360 \
    && useradd --system --gid q360 --home-dir /app q360

WORKDIR /app
COPY requirements.production.txt ./requirements.production.txt
RUN pip install --no-cache-dir -r requirements.production.txt
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python -m playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright \
    && rm -rf /var/lib/apt/lists/*
COPY --chown=q360:q360 . .
RUN mkdir -p /app/media /tmp/q360-home \
    && chown -R q360:q360 /app/media /tmp/q360-home

USER q360
ENV HOME=/tmp/q360-home

EXPOSE 10000
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers ${WEB_CONCURRENCY:-2} --access-logfile -"]
