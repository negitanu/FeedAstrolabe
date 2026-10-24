ARG PYTHON_IMAGE=python:slim
FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN python -c "import sys; assert sys.version_info[:2] == (3,15), sys.version" \
    && pip install --no-cache-dir --no-compile -c requirements.txt --group app \
    && pip check \
    && groupadd --gid 10001 feedastrolabe \
    && useradd --uid 10001 --gid 10001 --no-create-home feedastrolabe \
    && mkdir -p /data /run/observer && chown 10001:10001 /data /run/observer

FROM runtime AS renderer
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN pip install --no-cache-dir --no-compile -c requirements.txt --group renderer \
    && pip check \
    && python -m playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/*
COPY feedastrolabe ./feedastrolabe
USER 10001:10001
CMD ["python", "-m", "feedastrolabe.renderer"]

# Keep the default docker build target free of browser and test dependencies.
FROM runtime AS app
ENV FEEDASTROLABE_DATA_DIR=/data FEEDASTROLABE_BIND_HOST=0.0.0.0
COPY feedastrolabe ./feedastrolabe
USER 10001:10001
EXPOSE 5000
CMD ["python", "-m", "feedastrolabe"]
