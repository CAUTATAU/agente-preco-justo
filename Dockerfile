FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
USER nobody
# Forma shell para usar o PORT do Railway. "::" atende IPv4 e IPv6 (a rede privada do Railway pode ser só IPv6).
# 1 worker: o serviço não guarda estado, mas os limites de uso ficam no Node.
CMD exec uvicorn app.main:app --host :: --port ${PORT:-8000}
