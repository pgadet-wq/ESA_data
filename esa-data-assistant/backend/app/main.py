"""
Application FastAPI principale - ESA Data Assistant.
Point d'entrée de l'API backend.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .models.schemas import (
    ChatRequest,
    ChatResponse,
    CollectionListResponse,
    HealthResponse,
    ErrorResponse
)
from .services.chat_service import chat_service
from .services.vector_store import vector_store
from .services.esa_catalog import esa_catalog

# ============================================================================
# Configuration du logging
# ============================================================================

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# Création de l'application FastAPI
# ============================================================================

app = FastAPI(
    title=settings.app_name,
    description="Chatbot pour explorer le catalogue de données satellites ESA",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc"
)

# ============================================================================
# Middleware CORS (pour le développement)
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, spécifier les domaines autorisés
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Gestion des erreurs globale
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Gestionnaire d'erreurs global pour des réponses user-friendly."""
    logger.error(f"Erreur non gérée: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Une erreur interne s'est produite",
            "detail": str(exc) if settings.log_level == "DEBUG" else None
        }
    )

# ============================================================================
# Endpoints API
# ============================================================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint principal du chatbot.
    Reçoit un message utilisateur et retourne la réponse de l'assistant.

    - **message**: Le message de l'utilisateur
    - **conversation_history**: L'historique des messages précédents (optionnel)
    """
    logger.info(f"Message reçu: {request.message[:100]}...")

    try:
        # Convertit l'historique en format attendu
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.conversation_history
        ]

        # Appelle le service de chat
        result = await chat_service.chat(
            message=request.message,
            conversation_history=history
        )

        return ChatResponse(
            response=result["response"],
            sources=result.get("sources", []),
            tools_used=result.get("tools_used", [])
        )

    except Exception as e:
        logger.error(f"Erreur dans chat_endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors du traitement du message"
        )


@app.get("/api/collections", response_model=CollectionListResponse)
async def get_collections():
    """
    Retourne la liste des collections indexées.
    Utile pour voir quelles données sont disponibles.
    """
    try:
        # Récupère le nombre de collections indexées
        count = vector_store.get_collection_count()

        # Récupère quelques collections depuis le catalogue
        collections = esa_catalog.search_collections(limit=20)

        # Convertit en format attendu
        formatted = []
        for col in collections:
            formatted.append({
                "id": col["id"],
                "title": col["title"],
                "description": col.get("description", ""),
                "keywords": col.get("keywords", []),
                "temporal_extent": col.get("temporal_extent"),
                "spatial_extent": col.get("spatial_extent"),
                "providers": col.get("providers", []),
                "license": col.get("license"),
                "links": col.get("links", [])
            })

        return CollectionListResponse(
            collections=formatted,
            total=count if count > 0 else len(formatted)
        )

    except Exception as e:
        logger.error(f"Erreur dans get_collections: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la récupération des collections"
        )


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """
    Health check de l'application.
    Vérifie que les services sont opérationnels.
    """
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.utcnow()
    )


@app.get("/api/stats")
async def get_stats():
    """
    Retourne des statistiques sur le système.
    """
    try:
        indexed_count = vector_store.get_collection_count()
        return {
            "indexed_collections": indexed_count,
            "vector_store_status": "ready" if indexed_count > 0 else "empty",
            "mistral_configured": bool(settings.mistral_api_key),
            "catalog_url": settings.esa_catalog_url
        }
    except Exception as e:
        logger.error(f"Erreur dans get_stats: {e}")
        return {
            "indexed_collections": 0,
            "vector_store_status": "error",
            "error": str(e)
        }


@app.get("/api/welcome")
async def get_welcome():
    """
    Retourne le message de bienvenue du chatbot.
    """
    return {"message": chat_service.get_welcome_message()}

# ============================================================================
# Servir le Frontend
# ============================================================================

# Chemin vers le dossier frontend
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"


@app.get("/")
async def serve_frontend():
    """
    Sert la page principale du frontend.
    """
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    else:
        return JSONResponse(
            status_code=404,
            content={"error": "Frontend non trouvé", "path": str(index_path)}
        )


# Monte les fichiers statiques (CSS, JS)
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# ============================================================================
# Point d'entrée pour uvicorn
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
