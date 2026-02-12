FROM python:3.12-slim

# Evita criação de .pyc e buffer de logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements primeiro (melhora cache)
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copia aplicação
COPY . .

# Expõe porta
EXPOSE 8000

# Inicia API
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
