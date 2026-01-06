# ============================================================================
# Dockerfile - ESA Data Assistant Backend
# ============================================================================

# Image de base Python 3.11 slim
FROM python:3.11-slim

# Métadonnées
LABEL maintainer="ESA Data Assistant"
LABEL description="Chatbot pour explorer le catalogue de données satellites ESA"
LABEL version="1.0.0"

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Répertoire de travail
WORKDIR /app

# Installation des dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copie des fichiers de dépendances
COPY requirements.txt .

# Installation des dépendances Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copie du code source
COPY app/ ./app/
COPY scripts/ ./scripts/

# Copie du frontend (sera monté depuis le parent normalement)
# COPY ../frontend/ ./frontend/

# Crée le répertoire de données
RUN mkdir -p /app/data/chroma

# Expose le port
EXPOSE 8000

# Utilisateur non-root pour la sécurité
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Commande de démarrage
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
