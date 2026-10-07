FROM python:3.12-slim

# Chromium + Xvfb (browser-use 0.13 drives real Chrome via CDP instead of Playwright)
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium chromium-driver fonts-liberation procps curl xvfb xauth \
    && rm -rf /var/lib/apt/lists/*

# browser-use looks for a Chrome binary; point it at the distro Chromium
ENV CHROME_PATH=/usr/bin/chromium
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
EXPOSE 8000

# Xvfb provides a virtual display so Chromium can run headed inside the container
CMD ["sh", "-c", "Xvfb :99 -screen 0 1280x1024x24 & sleep 1; export DISPLAY=:99; exec uvicorn app:app --host 0.0.0.0 --port 8000"]
