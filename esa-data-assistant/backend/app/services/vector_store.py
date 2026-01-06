"""
Service de stockage vectoriel avec ChromaDB.
Gère les embeddings des collections ESA pour la recherche sémantique.
"""

import logging
import os
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from ..config import settings

# Configuration du logger
logger = logging.getLogger(__name__)


class VectorStoreService:
    """
    Service de recherche sémantique utilisant ChromaDB.
    Stocke les embeddings des descriptions de collections ESA.
    """

    def __init__(self):
        """Initialise le service de stockage vectoriel."""
        self._client = None
        self._collection = None
        self._embedding_model = None
        self.collection_name = "esa_collections"

    def _get_embedding_model(self) -> SentenceTransformer:
        """
        Charge le modèle d'embeddings (chargement paresseux).

        Returns:
            Modèle SentenceTransformer
        """
        if self._embedding_model is None:
            logger.info(f"Chargement du modèle d'embeddings: {settings.embedding_model}")
            self._embedding_model = SentenceTransformer(settings.embedding_model)
            logger.info("Modèle d'embeddings chargé")
        return self._embedding_model

    def _get_client(self) -> chromadb.ClientAPI:
        """
        Retourne le client ChromaDB avec persistance.

        Returns:
            Client ChromaDB configuré
        """
        if self._client is None:
            # Crée le répertoire de persistance si nécessaire
            persist_dir = settings.chroma_persist_dir
            os.makedirs(persist_dir, exist_ok=True)

            logger.info(f"Initialisation de ChromaDB (persistance: {persist_dir})")

            self._client = chromadb.PersistentClient(
                path=persist_dir,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            logger.info("ChromaDB initialisé")

        return self._client

    def _get_collection(self) -> chromadb.Collection:
        """
        Retourne la collection ChromaDB (création si nécessaire).

        Returns:
            Collection ChromaDB pour les données ESA
        """
        if self._collection is None:
            client = self._get_client()

            # Crée ou récupère la collection
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "ESA satellite data collections"}
            )
            logger.info(f"Collection '{self.collection_name}' prête")

        return self._collection

    def index_collections(self, collections: List[Dict[str, Any]]) -> int:
        """
        Indexe une liste de collections dans ChromaDB.

        Args:
            collections: Liste de collections ESA à indexer

        Returns:
            Nombre de collections indexées
        """
        if not collections:
            logger.warning("Aucune collection à indexer")
            return 0

        collection = self._get_collection()
        model = self._get_embedding_model()

        # Prépare les données pour l'indexation
        ids = []
        documents = []
        metadatas = []

        for col in collections:
            col_id = col.get("id", "")
            if not col_id:
                continue

            # Crée le texte à indexer (combinaison titre + description + keywords)
            title = col.get("title", "")
            description = col.get("description", "")
            keywords = " ".join(col.get("keywords", []))

            document = f"{title}. {description} Keywords: {keywords}"

            # Métadonnées stockées avec l'embedding
            metadata = {
                "title": title[:500],  # Limite pour ChromaDB
                "description": description[:2000] if description else "",
                "keywords": keywords[:500] if keywords else "",
            }

            ids.append(col_id)
            documents.append(document)
            metadatas.append(metadata)

        if not ids:
            logger.warning("Aucune collection valide à indexer")
            return 0

        # Génère les embeddings
        logger.info(f"Génération des embeddings pour {len(documents)} collections...")
        embeddings = model.encode(documents, show_progress_bar=True).tolist()

        # Indexe dans ChromaDB (upsert pour éviter les doublons)
        logger.info("Indexation dans ChromaDB...")
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

        logger.info(f"{len(ids)} collections indexées avec succès")
        return len(ids)

    def semantic_search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Effectue une recherche sémantique dans les collections indexées.

        Args:
            query: Requête de recherche en langage naturel
            top_k: Nombre de résultats à retourner

        Returns:
            Liste des collections les plus pertinentes avec scores
        """
        try:
            collection = self._get_collection()
            model = self._get_embedding_model()

            # Vérifie si la collection contient des données
            if collection.count() == 0:
                logger.warning("La base vectorielle est vide. Lancez l'indexation.")
                return []

            logger.info(f"Recherche sémantique: '{query}' (top_k={top_k})")

            # Génère l'embedding de la requête
            query_embedding = model.encode([query]).tolist()

            # Recherche les documents similaires
            results = collection.query(
                query_embeddings=query_embedding,
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )

            # Formate les résultats
            formatted_results = []
            if results and results["ids"] and len(results["ids"]) > 0:
                for i, doc_id in enumerate(results["ids"][0]):
                    # Convertit la distance en score de similarité (0-1)
                    # ChromaDB utilise la distance L2, on la convertit en similarité
                    distance = results["distances"][0][i] if results["distances"] else 0
                    similarity = 1 / (1 + distance)  # Plus la distance est petite, plus le score est élevé

                    result = {
                        "id": doc_id,
                        "title": results["metadatas"][0][i].get("title", ""),
                        "description": results["metadatas"][0][i].get("description", ""),
                        "keywords": results["metadatas"][0][i].get("keywords", ""),
                        "relevance_score": round(similarity, 4),
                        "document": results["documents"][0][i] if results["documents"] else ""
                    }
                    formatted_results.append(result)

            logger.info(f"Trouvé {len(formatted_results)} résultats")
            return formatted_results

        except Exception as e:
            logger.error(f"Erreur lors de la recherche sémantique: {e}")
            raise

    def get_collection_count(self) -> int:
        """
        Retourne le nombre de collections indexées.

        Returns:
            Nombre de documents dans la base vectorielle
        """
        try:
            collection = self._get_collection()
            return collection.count()
        except Exception as e:
            logger.error(f"Erreur lors du comptage: {e}")
            return 0

    def clear_index(self) -> bool:
        """
        Supprime toutes les données de l'index.

        Returns:
            True si la suppression a réussi
        """
        try:
            client = self._get_client()
            client.delete_collection(self.collection_name)
            self._collection = None
            logger.info("Index effacé")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la suppression de l'index: {e}")
            return False


# Instance singleton pour utilisation globale
vector_store = VectorStoreService()
