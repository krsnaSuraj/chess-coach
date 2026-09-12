# Chess Coach v0.1.1 — web server image (Linux).
FROM python:3.12-slim

WORKDIR /app

# System deps for Qt imports + health checks. curl (-38MB with deps) is
# replaced by a python urllib probe so the runtime stays lean.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libegl1 libxkbcommon0 libdbus-1-3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -r -m -d /home/app -s /usr/sbin/nologin app

# Install the package first (better layer caching), then the full source.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e . \
    && chown -R app:app /app

COPY config.yaml ./
COPY static/ ./static/
RUN chown -R app:app /app

# Stockfish is NOT bundled (114MB + platform-specific).
# Download Stockfish 18 for your platform:
#   https://stockfishchess.org/download/
# Then either bake it in or mount + override at runtime:
#   docker run -p 8000:8000 \
#     -v /path/to/stockfish:/app/stockfish:ro \
#     -e CHESS_COACH_ENGINE=/app/stockfish \
#     chess-coach
# NOTE: engine.path must point at the binary (no .exe on Linux).
ENV CHESS_COACH_ENGINE=/app/stockfish

USER app

EXPOSE 8000

# NOTE: assumes the default port 8000 (CMD below passes no port arg).
# If you run with a custom port, override the healthcheck too:
#   --health-cmd="python -c \"...urlopen('http://127.0.0.1:8012/api/health'...\""
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import sys,urllib.request;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=4).status==200 else 1)"

CMD ["python", "-m", "chess_coach", "web"]
