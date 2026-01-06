"""
Schémas Pydantic pour la validation des données.
Définit les modèles de requête et réponse de l'API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# Modèles pour le Chat
# ============================================================================

class ChatMessage(BaseModel):
    """Un message dans la conversation."""
    role: str = Field(..., description="Rôle: 'user' ou 'assistant'")
    content: str = Field(..., description="Contenu du message")


class ChatRequest(BaseModel):
    """Requête envoyée au chatbot."""
    message: str = Field(..., description="Message de l'utilisateur", min_length=1)
    conversation_history: List[ChatMessage] = Field(
        default=[],
        description="Historique des messages précédents"
    )


class ChatResponse(BaseModel):
    """Réponse du chatbot."""
    response: str = Field(..., description="Réponse générée par l'assistant")
    sources: List[str] = Field(
        default=[],
        description="Sources utilisées pour la réponse"
    )
    tools_used: List[str] = Field(
        default=[],
        description="Outils appelés pendant le traitement"
    )


# ============================================================================
# Modèles pour les Collections ESA
# ============================================================================

class ESACollection(BaseModel):
    """Représentation d'une collection de données ESA."""
    id: str = Field(..., description="Identifiant unique de la collection")
    title: str = Field(..., description="Titre de la collection")
    description: Optional[str] = Field(None, description="Description détaillée")
    keywords: List[str] = Field(default=[], description="Mots-clés associés")
    temporal_extent: Optional[Dict[str, Any]] = Field(
        None,
        description="Étendue temporelle (dates début/fin)"
    )
    spatial_extent: Optional[Dict[str, Any]] = Field(
        None,
        description="Étendue spatiale (bbox)"
    )
    providers: List[str] = Field(default=[], description="Fournisseurs de données")
    license: Optional[str] = Field(None, description="Licence d'utilisation")
    links: List[Dict[str, str]] = Field(default=[], description="Liens associés")


class CollectionListResponse(BaseModel):
    """Liste des collections disponibles."""
    collections: List[ESACollection]
    total: int = Field(..., description="Nombre total de collections")


class CollectionSearchResult(BaseModel):
    """Résultat d'une recherche de collection."""
    collection: ESACollection
    relevance_score: float = Field(
        ...,
        description="Score de pertinence (0-1)",
        ge=0,
        le=1
    )


# ============================================================================
# Modèles pour les Items (Granules)
# ============================================================================

class ESAItem(BaseModel):
    """Un item (granule) dans une collection."""
    id: str
    collection: str
    datetime: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None
    bbox: Optional[List[float]] = None
    properties: Dict[str, Any] = Field(default={})
    assets: Dict[str, Any] = Field(default={})
    links: List[Dict[str, str]] = Field(default=[])


class ItemSearchRequest(BaseModel):
    """Paramètres de recherche d'items."""
    collections: List[str] = Field(
        default=[],
        description="Collections à rechercher"
    )
    bbox: Optional[List[float]] = Field(
        None,
        description="Bounding box [minX, minY, maxX, maxY]"
    )
    datetime: Optional[str] = Field(
        None,
        description="Filtre temporel (ex: '2023-01-01/2023-12-31')"
    )
    limit: int = Field(
        default=10,
        description="Nombre max de résultats",
        ge=1,
        le=100
    )


class ItemSearchResponse(BaseModel):
    """Résultat d'une recherche d'items."""
    items: List[ESAItem]
    total: int
    next_page: Optional[str] = None


# ============================================================================
# Modèles utilitaires
# ============================================================================

class HealthResponse(BaseModel):
    """Réponse du health check."""
    status: str = "healthy"
    version: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Réponse en cas d'erreur."""
    error: str = Field(..., description="Message d'erreur")
    detail: Optional[str] = Field(None, description="Détails supplémentaires")
    code: Optional[str] = Field(None, description="Code d'erreur")
