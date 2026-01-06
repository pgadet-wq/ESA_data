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

# Mapping français -> anglais pour les termes de recherche courants
FR_EN_MAPPING = {
    # Types de données
    "optique": "optical",
    "optiques": "optical",
    "radar": "radar",
    "images": "imagery",
    "image": "imagery",
    "satellite": "satellite",
    "satellites": "satellite",
    "données": "data",
    "mesures": "measurements",
    "mesure": "measurement",

    # Thématiques
    "forêt": "forest",
    "forêts": "forest",
    "forestier": "forest",
    "forestières": "forest",
    "océan": "ocean",
    "océans": "ocean",
    "mer": "sea",
    "mers": "ocean sea",
    "maritime": "marine ocean",
    "climat": "climate",
    "climatique": "climate",
    "atmosphère": "atmosphere",
    "atmosphérique": "atmosphere atmospheric",
    "température": "temperature",
    "végétation": "vegetation",
    "agriculture": "agriculture",
    "agricole": "agriculture crop",
    "sol": "soil land",
    "sols": "soil land",
    "terre": "land earth",
    "glace": "ice",
    "neige": "snow",
    "eau": "water",
    "inondation": "flood",
    "sécheresse": "drought",
    "urbain": "urban",
    "ville": "urban city",
    "pollution": "pollution",
    "qualité de l'air": "air quality",

    # Caractéristiques
    "haute résolution": "high resolution",
    "résolution": "resolution",
    "multispectral": "multispectral",
    "multispectrales": "multispectral",
    "hyperspectral": "hyperspectral",
    "infrarouge": "infrared",
    "thermique": "thermal",
    "altimétrie": "altimetry",
    "altimétrique": "altimetry",
    "gravité": "gravity",
    "magnétique": "magnetic",
    "géolocalisé": "geolocated geolocation",
    "géolocalisation": "geolocation",
    "topographie": "topography elevation",

    # Missions
    "sentinel": "sentinel",
    "copernicus": "copernicus",
    "envisat": "envisat",
    "swarm": "swarm",
    "cryosat": "cryosat",
    "smos": "smos",
    "goce": "goce",
    "aeolus": "aeolus",
    "biomass": "biomass",
}


class ESACatalogService:
    """
    Client pour interroger le catalogue STAC de l'ESA (EO-CAT).
    Utilise pystac-client pour les requêtes STAC.
    """

    def __init__(self):
        """Initialise la connexion au catalogue ESA."""
        self.catalog_url = settings.esa_catalog_url
        self._client = None
        self._all_collections_cache = None

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

    def _translate_query(self, query: str) -> List[str]:
        """
        Traduit une requête française en termes anglais pour la recherche.
        Retourne une liste de termes de recherche.
        """
        query_lower = query.lower()
        search_terms = set()

        # Ajoute les termes originaux
        for word in query_lower.split():
            search_terms.add(word)

            # Traduit si le mot existe dans le mapping
            if word in FR_EN_MAPPING:
                for en_term in FR_EN_MAPPING[word].split():
                    search_terms.add(en_term)

        # Cherche aussi les expressions complètes
        for fr_term, en_terms in FR_EN_MAPPING.items():
            if fr_term in query_lower:
                for en_term in en_terms.split():
                    search_terms.add(en_term)

        return list(search_terms)

    def search_collections(
        self,
        query: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Recherche des collections dans le catalogue ESA.
        Supporte les requêtes en français grâce à un mapping automatique.

        Args:
            query: Terme de recherche (optionnel)
            limit: Nombre max de résultats

        Returns:
            Liste de collections avec leurs métadonnées
        """
        try:
            client = self._get_client()
            collections = []
            seen_count = 0
            max_to_scan = 500  # Scan plus de collections pour trouver des matchs

            logger.info(f"Recherche de collections (query={query}, limit={limit})")

            # Traduit la requête en termes anglais
            search_terms = self._translate_query(query) if query else []
            logger.info(f"Termes de recherche: {search_terms}")

            # Parcourt les collections du catalogue
            for collection in client.get_collections():
                seen_count += 1
                if seen_count > max_to_scan:
                    break

                if len(collections) >= limit:
                    break

                # Si pas de query, retourne les premières collections
                if not query:
                    col_data = self._collection_to_dict(collection)
                    collections.append(col_data)
                    continue

                # Recherche avec les termes traduits
                title = (collection.title or "").lower()
                description = (collection.description or "").lower()
                keywords = " ".join(collection.keywords or []).lower()
                collection_text = f"{title} {description} {keywords}"

                # Vérifie si au moins un terme de recherche est présent
                match_count = sum(1 for term in search_terms if term in collection_text)

                if match_count > 0:
                    col_data = self._collection_to_dict(collection)
                    col_data["_match_score"] = match_count  # Score pour le tri
                    collections.append(col_data)

            # Trie par score de correspondance si disponible
            if query:
                collections.sort(key=lambda x: x.get("_match_score", 0), reverse=True)
                # Supprime le score du résultat final
                for col in collections:
                    col.pop("_match_score", None)

            logger.info(f"Trouvé {len(collections)} collections (scanné {seen_count})")
            return collections[:limit]

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
