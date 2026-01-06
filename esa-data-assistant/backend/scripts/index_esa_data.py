#!/usr/bin/env python3
"""
Script d'indexation des collections ESA dans ChromaDB.
À exécuter une fois lors du setup initial pour créer la base vectorielle.

Usage:
    python -m scripts.index_esa_data

    ou depuis le dossier backend:
    python scripts/index_esa_data.py
"""

import sys
import os
import logging
from pathlib import Path

# Ajoute le chemin parent pour importer les modules de l'app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services.esa_catalog import esa_catalog
from app.services.vector_store import vector_store

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """
    Fonction principale d'indexation.
    1. Récupère toutes les collections depuis ESA EO-CAT
    2. Crée les embeddings avec sentence-transformers
    3. Stocke dans ChromaDB
    """
    print("=" * 60)
    print("🛰️  ESA Data Assistant - Script d'indexation")
    print("=" * 60)
    print()

    # Vérifie la configuration
    print(f"📍 Catalogue ESA : {settings.esa_catalog_url}")
    print(f"📁 Stockage ChromaDB : {settings.chroma_persist_dir}")
    print(f"🧠 Modèle embeddings : {settings.embedding_model}")
    print()

    try:
        # Étape 1 : Récupération des collections
        print("📥 Étape 1/3 : Récupération des collections depuis ESA EO-CAT...")
        print("   (Cela peut prendre quelques minutes selon la connexion)")
        print()

        collections = esa_catalog.get_all_collections_for_indexing()

        if not collections:
            print("❌ Aucune collection récupérée. Vérifiez la connexion au catalogue.")
            return 1

        print(f"   ✅ {len(collections)} collections récupérées")
        print()

        # Affiche un aperçu
        print("   📋 Aperçu des premières collections :")
        for i, col in enumerate(collections[:5]):
            title = col.get('title', col.get('id', 'Sans titre'))[:50]
            print(f"      {i+1}. {title}")
        if len(collections) > 5:
            print(f"      ... et {len(collections) - 5} autres")
        print()

        # Étape 2 : Création des embeddings et indexation
        print("🧮 Étape 2/3 : Génération des embeddings et indexation...")
        print("   (Le premier chargement du modèle peut prendre du temps)")
        print()

        indexed_count = vector_store.index_collections(collections)

        print(f"   ✅ {indexed_count} collections indexées dans ChromaDB")
        print()

        # Étape 3 : Vérification
        print("🔍 Étape 3/3 : Vérification de l'indexation...")

        total_in_db = vector_store.get_collection_count()
        print(f"   📊 Total dans la base : {total_in_db} documents")

        # Test de recherche
        print("   🔎 Test de recherche sémantique : 'forest monitoring'")
        test_results = vector_store.semantic_search("forest monitoring", top_k=3)

        if test_results:
            print("   ✅ Recherche réussie ! Résultats :")
            for i, res in enumerate(test_results):
                print(f"      {i+1}. {res['title'][:50]} (score: {res['relevance_score']:.3f})")
        else:
            print("   ⚠️  Aucun résultat - l'indexation peut nécessiter plus de données")

        print()
        print("=" * 60)
        print("✅ Indexation terminée avec succès !")
        print("=" * 60)
        print()
        print("🚀 Vous pouvez maintenant lancer l'application :")
        print("   uvicorn app.main:app --reload")
        print()

        return 0

    except ConnectionError as e:
        print(f"❌ Erreur de connexion : {e}")
        print("   Vérifiez votre connexion internet et l'accès au catalogue ESA.")
        return 1

    except Exception as e:
        print(f"❌ Erreur inattendue : {e}")
        logger.exception("Erreur durant l'indexation")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
