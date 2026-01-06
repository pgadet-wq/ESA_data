"""
Service d'accès au catalogue ESA EO-CAT via STAC.
Permet de rechercher et récupérer des collections et items de données satellites.
"""

import logging
from typing import List, Optional, Dict, Any
from pystac_client import Client
from pystac import Collection
import httpx

from ..config import settings

# Configuration du logger
logger = logging.getLogger(__name__)


class ESACatalogService:
    """
    Client pour interroger le catalogue STAC de l'ESA (EO-CAT).
    Utilise pystac-client pour les requêtes STAC.
    """

    def __init__(self):
        """Initialise la connexion au catalogue ESA."""
        self.catalog_url = settings.esa_catalog_url
        self._client = None

    def _get_client(self) -> Client:
        """
        Retourne le client STAC, avec initialisation paresseuse.
        Gère les erreurs de connexion.
        """
        if self._client is None:
            try:
                logger.info(f"Connexion au catalogue ESA: {self.catalog_url}")
                self._client = Client.open(self.catalog_url)
                logger.info("Connexion réussie au catalogue ESA")
            except Exception as e:
                logger.error(f"Erreur de connexion au catalogue ESA: {e}")
                raise ConnectionError(
                    f"Impossible de se connecter au catalogue ESA: {e}"
                )
        return self._client

    def search_collections(
        self,
        query: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Recherche des collections dans le catalogue ESA.

        Args:
            query: Terme de recherche (optionnel)
            limit: Nombre max de résultats

        Returns:
            Liste de collections avec leurs métadonnées
        """
        try:
            client = self._get_client()
            collections = []

            logger.info(f"Recherche de collections (query={query}, limit={limit})")

            # Parcourt les collections du catalogue
            for i, collection in enumerate(client.get_collections()):
                if i >= limit:
                    break

                # Filtre par query si spécifié
                if query:
                    query_lower = query.lower()
                    title = (collection.title or "").lower()
                    description = (collection.description or "").lower()
                    keywords = " ".join(collection.keywords or []).lower()

                    # Vérifie si le terme de recherche est présent
                    if not any(query_lower in text for text in [title, description, keywords]):
                        continue

                # Extrait les métadonnées
                col_data = self._collection_to_dict(collection)
                collections.append(col_data)

            logger.info(f"Trouvé {len(collections)} collections")
            return collections

        except Exception as e:
            logger.error(f"Erreur lors de la recherche de collections: {e}")
            raise

    def get_collection_details(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les détails complets d'une collection.

        Args:
            collection_id: Identifiant de la collection

        Returns:
            Dictionnaire avec les détails ou None si non trouvée
        """
        try:
            client = self._get_client()
            logger.info(f"Récupération des détails de la collection: {collection_id}")

            collection = client.get_collection(collection_id)

            if collection is None:
                logger.warning(f"Collection non trouvée: {collection_id}")
                return None

            return self._collection_to_dict(collection)

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la collection {collection_id}: {e}")
            return None

    def search_items(
        self,
        collections: Optional[List[str]] = None,
        bbox: Optional[List[float]] = None,
        datetime: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Recherche des items (granules) dans les collections.

        Args:
            collections: Liste des IDs de collections à rechercher
            bbox: Bounding box [minX, minY, maxX, maxY]
            datetime: Filtre temporel (ex: '2023-01-01/2023-12-31')
            limit: Nombre max de résultats

        Returns:
            Liste d'items avec leurs métadonnées
        """
        try:
            client = self._get_client()

            logger.info(
                f"Recherche d'items (collections={collections}, "
                f"bbox={bbox}, datetime={datetime}, limit={limit})"
            )

            # Construit la requête de recherche
            search_params = {"limit": limit}

            if collections:
                search_params["collections"] = collections
            if bbox:
                search_params["bbox"] = bbox
            if datetime:
                search_params["datetime"] = datetime

            # Exécute la recherche
            search = client.search(**search_params)
            items = []

            for item in search.items():
                item_data = {
                    "id": item.id,
                    "collection": item.collection_id,
                    "datetime": item.datetime.isoformat() if item.datetime else None,
                    "geometry": item.geometry,
                    "bbox": list(item.bbox) if item.bbox else None,
                    "properties": dict(item.properties),
                    "assets": {
                        name: {
                            "href": asset.href,
                            "type": asset.media_type,
                            "title": asset.title
                        }
                        for name, asset in item.assets.items()
                    },
                    "links": [
                        {"rel": link.rel, "href": link.href}
                        for link in item.links
                    ]
                }
                items.append(item_data)

            logger.info(f"Trouvé {len(items)} items")
            return items

        except Exception as e:
            logger.error(f"Erreur lors de la recherche d'items: {e}")
            raise

    def get_all_collections_for_indexing(self) -> List[Dict[str, Any]]:
        """
        Récupère toutes les collections pour l'indexation.
        Utilisé par le script d'indexation initial.

        Returns:
            Liste complète des collections avec métadonnées
        """
        try:
            client = self._get_client()
            collections = []

            logger.info("Récupération de toutes les collections pour indexation...")

            for collection in client.get_collections():
                col_data = self._collection_to_dict(collection)
                collections.append(col_data)

            logger.info(f"Total: {len(collections)} collections récupérées")
            return collections

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des collections: {e}")
            raise

    def _collection_to_dict(self, collection: Collection) -> Dict[str, Any]:
        """
        Convertit un objet Collection STAC en dictionnaire.

        Args:
            collection: Objet Collection pystac

        Returns:
            Dictionnaire avec les métadonnées
        """
        # Extrait l'étendue temporelle
        temporal_extent = None
        if collection.extent and collection.extent.temporal:
            intervals = collection.extent.temporal.intervals
            if intervals and len(intervals) > 0:
                temporal_extent = {
                    "start": intervals[0][0].isoformat() if intervals[0][0] else None,
                    "end": intervals[0][1].isoformat() if intervals[0][1] else None
                }

        # Extrait l'étendue spatiale
        spatial_extent = None
        if collection.extent and collection.extent.spatial:
            bboxes = collection.extent.spatial.bboxes
            if bboxes and len(bboxes) > 0:
                spatial_extent = {"bbox": list(bboxes[0])}

        # Extrait les fournisseurs
        providers = []
        if collection.providers:
            providers = [p.name for p in collection.providers if p.name]

        return {
            "id": collection.id,
            "title": collection.title or collection.id,
            "description": collection.description or "",
            "keywords": list(collection.keywords) if collection.keywords else [],
            "temporal_extent": temporal_extent,
            "spatial_extent": spatial_extent,
            "providers": providers,
            "license": collection.license if hasattr(collection, 'license') else None,
            "links": [
                {"rel": link.rel, "href": link.href, "title": link.title or ""}
                for link in collection.links
            ]
        }


# Instance singleton pour utilisation globale
esa_catalog = ESACatalogService()
