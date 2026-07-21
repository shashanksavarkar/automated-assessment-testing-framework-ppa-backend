# Render deploy image: bundles backend (FastAPI) + TestCase1 (Selenium engine) into one
# container. They must share a filesystem because backend/app/worker.py launches TestCase1's
# main.py as a subprocess (see backend/app/config.py) -- Render can't run them as two separate
# services and have that subprocess call work. Render also only builds from a single git repo,
# so this assumes TestCase1 has been added as a git submodule at ./TestCase1 inside THIS repo
# (see repo setup instructions) -- that makes it show up in the build context below.
#
# No TestCase1/.venv exists in this image, so config.py's ASSESSMENT_PYTHON check falls back to
# sys.executable -- i.e. this same interpreter -- which is why both requirements files are
# installed into one global environment instead of two separate venvs.
FROM python:3.12-slim

# Headless Chrome for Selenium. webdriver-manager (in TestCase1's requirements) downloads a
# matching chromedriver at runtime, but the Chrome *browser* binary itself has to be installed
# in the image up front.
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg curl unzip \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Build context is this repo's root (backend/), which contains TestCase1/ as a submodule
# alongside app/, requirements.txt, etc. -- so /app ends up with backend's own layout plus a
# /app/TestCase1 sibling folder, matching what config.py expects once ASSESSMENT_DIR is set.
COPY . /app/

RUN pip install --no-cache-dir \
    -r /app/requirements.txt \
    -r /app/TestCase1/requirements.txt

ENV ASSESSMENT_DIR=/app/TestCase1
ENV HEADLESS=true
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
# Render injects $PORT at runtime; default to 8000 for local `docker run` testing.
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
