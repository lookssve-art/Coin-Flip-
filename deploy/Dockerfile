# SERO Accounting Agent — Container fuer den autonomen Remote-Betrieb.
FROM python:3.12-slim

WORKDIR /app

# Abhaengigkeiten zuerst (Layer-Cache). anthropic optional fuer Claude-Features.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir anthropic

COPY . .

# Persistente Daten (Audit-Log, Belegspeicher, Inbox, data/) als Volumes mounten.
VOLUME ["/app/audit", "/app/belege", "/app/inbox", "/app/data"]

# config.yaml wird NICHT ins Image gebacken — per Volume/Secret einhaengen:
#   docker run -v $PWD/config.yaml:/app/config.yaml ...
ENV PYTHONUNBUFFERED=1

# Standard: autonomer Dauerbetrieb (Bot + Pipeline-Takt).
CMD ["python", "run.py", "serve"]
