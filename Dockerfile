FROM python:3.14-slim@sha256:f85c5697265c178cc6887276c55fe16cf3d14ca35c3df6a5eab3b360534a55d2
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FEEDASTROLABE_DATA_DIR=/data FEEDASTROLABE_BIND_HOST=0.0.0.0
WORKDIR /app
COPY requirements-production-lock.txt ./
RUN pip install --no-cache-dir -r requirements-production-lock.txt \
    && groupadd --gid 10001 feedastrolabe \
    && useradd --uid 10001 --gid 10001 --no-create-home feedastrolabe \
    && mkdir /data && chown 10001:10001 /data
COPY feedastrolabe ./feedastrolabe
USER 10001:10001
EXPOSE 5000
CMD ["python", "-m", "feedastrolabe"]
