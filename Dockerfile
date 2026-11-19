FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN python manage.py migrate
RUN python manage.py seed_ph_samples
RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT}"]
