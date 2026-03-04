# Python 3.12 + Playwright Chromium for Populi scraping
FROM python:3.12-bookworm

WORKDIR /app

# System deps for Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libdbus-1-3 libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium for Playwright (no .env/code needed yet)
RUN playwright install chromium

COPY config config
COPY data data
COPY src src
COPY viewer viewer
COPY app.py .

# output/ is created at runtime
ENV PORT=8765
EXPOSE 8765

# Railway sets PORT at runtime
CMD ["sh", "-c", "gunicorn -w 1 -b 0.0.0.0:${PORT:-8765} app:app"]
