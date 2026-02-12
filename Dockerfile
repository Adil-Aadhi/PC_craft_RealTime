FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

ENV DJANGO_SETTINGS_MODULE=realtime.settings

CMD ["daphne", "-b", "0.0.0.0", "-p", "8001", "realtime.asgi:application"]
