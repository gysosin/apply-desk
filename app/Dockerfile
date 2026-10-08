# Runtime image for Apply Desk. Code, TeX (TinyTeX), bun and the Claude login are bind-mounted
# from the host (see docker-compose.yml), so the image only carries system packages + Python deps.
FROM debian:13
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv bubblewrap poppler-utils fontconfig \
      ca-certificates tzdata curl \
 && rm -rf /var/lib/apt/lists/*
COPY app/requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1
