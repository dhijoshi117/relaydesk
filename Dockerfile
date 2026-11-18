FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home relaydesk && mkdir /data && chown relaydesk:relaydesk /data
COPY app.py schema.sql ./
COPY static ./static
USER relaydesk
ENV RELAYDESK_DB=/data/relaydesk.db
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
