FROM python:3.12-slim

RUN useradd -m -u 10001 bot

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot

RUN mkdir -p /data && chown -R 10001:10001 /data
ENV DB_PATH=/data/data.db PYTHONUNBUFFERED=1

USER bot
CMD ["python", "-m", "bot.main"]
