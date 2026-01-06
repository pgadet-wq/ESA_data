"""
Configuration de l'application ESA Data Assistant.
Charge les variables d'environnement et définit les paramètres globaux.
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Paramètres de configuration de l'application.
    Les valeurs sont chargées depuis les variables d'environnement ou le fichier .env
    """

    # API Mistral
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"

    # ESA Catalog
    esa_catalog_url: str = "https://eocat.esa.int/eo-catalogue/"

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma"

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"

    # Application
    log_level: str = "INFO"
    app_name: str = "ESA Data Assistant"
    app_version: str = "1.0.0"

    class Config:
        # Charge les variables depuis le fichier .env
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore les variables non définies


@lru_cache()
def get_settings() -> Settings:
    """
    Retourne l'instance des paramètres (singleton mis en cache).
    Utilise lru_cache pour éviter de recharger à chaque appel.
    """
    return Settings()


# Instance globale pour un accès facile
settings = get_settings()
