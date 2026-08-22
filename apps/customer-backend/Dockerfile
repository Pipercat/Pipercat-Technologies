FROM python:3.12-slim

# S1V2-02-029: provides `nmcli`, which app/services/network_setup.py uses
# to configure the host's Ethernet/Wi-Fi/setup hotspot via NetworkManager
# (reached over the D-Bus socket bind-mounted in docker-compose.yml -
# this package alone does not grant host network access).
RUN apt-get update \
    && apt-get install -y --no-install-recommends network-manager \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
