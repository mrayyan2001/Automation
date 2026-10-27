FROM ghcr.io/berriai/litellm:latest

# LiteLLM needs Pillow to convert vision images for Ollama requests.
RUN /app/.venv/bin/python -m ensurepip --upgrade \
    && /app/.venv/bin/python -m pip install --no-cache-dir Pillow
