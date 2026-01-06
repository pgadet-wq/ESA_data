"""
Définition des outils pour le function calling avec Mistral.
Ces outils permettent au chatbot d'interagir avec le catalogue ESA.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# Définitions des outils pour Mistral Function Calling
# ============================================================================

ESA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_esa_collections",
            "description": """Recherche des collections de données satellites dans le catalogue ESA.
            Utilisez cet outil quand l'utilisateur cherche des données sur un thème spécifique
            (forêts, océans, climat, etc.) ou un type de capteur (radar, optique, etc.).""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Terme de recherche en langage naturel (ex: 'données forestières', 'images radar', 'température océan')"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Nombre de résultats à retourner (défaut: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_collection_details",
            "description": """Récupère les détails complets d'une collection de données ESA.
            Utilisez cet outil quand l'utilisateur veut plus d'informations sur une collection
            spécifique identifiée par son ID.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "collection_id": {
                        "type": "string",
                        "description": "Identifiant unique de la collection ESA"
                    }
                },
                "required": ["collection_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_term",
            "description": """Explique un terme technique lié à l'observation de la Terre.
            Utilisez cet outil quand l'utilisateur ne comprend pas un terme technique
            comme SAR, multispectral, GeoTIFF, STAC, etc.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Le terme technique à expliquer"
                    }
                },
                "required": ["term"]
            }
        }
    }
]


# ============================================================================
# Dictionnaire des termes techniques pour explain_term
# ============================================================================

EARTH_OBSERVATION_GLOSSARY = {
    "sar": {
        "term": "SAR (Synthetic Aperture Radar)",
        "explanation": """Le SAR est un type de radar qui crée des images haute résolution de la surface terrestre.
Contrairement aux capteurs optiques, le SAR fonctionne de jour comme de nuit et peut voir à travers les nuages.
Il est particulièrement utile pour surveiller les déformations du sol, la glace, et les structures.""",
        "examples": ["Sentinel-1", "ALOS PALSAR", "TerraSAR-X"]
    },
    "radar": {
        "term": "Radar",
        "explanation": """Le radar (Radio Detection and Ranging) émet des ondes radio et mesure leur réflexion.
En observation de la Terre, il permet d'obtenir des images indépendamment des conditions météo et de luminosité.""",
        "examples": ["Sentinel-1", "ERS", "Envisat ASAR"]
    },
    "multispectral": {
        "term": "Imagerie Multispectrale",
        "explanation": """L'imagerie multispectrale capture des données dans plusieurs bandes du spectre électromagnétique
(visible, proche infrarouge, etc.). Chaque bande révèle des informations différentes sur la surface :
végétation, eau, sols, etc.""",
        "examples": ["Sentinel-2", "Landsat", "SPOT"]
    },
    "sentinel": {
        "term": "Programme Sentinel",
        "explanation": """Les satellites Sentinel font partie du programme Copernicus de l'Union Européenne.
- Sentinel-1 : Radar SAR (surveillance terrestre et maritime)
- Sentinel-2 : Imagerie optique haute résolution (végétation, sols)
- Sentinel-3 : Océan et atmosphère
- Sentinel-5P : Qualité de l'air""",
        "examples": ["Sentinel-1A/B", "Sentinel-2A/B", "Sentinel-3A/B"]
    },
    "copernicus": {
        "term": "Programme Copernicus",
        "explanation": """Copernicus est le programme européen d'observation de la Terre, géré par la Commission Européenne
en partenariat avec l'ESA. Il fournit des données satellites gratuites et ouvertes via les satellites Sentinel
et d'autres missions contributives.""",
        "examples": ["Sentinels", "Services Copernicus (CLMS, CEMS, CMS, etc.)"]
    },
    "stac": {
        "term": "STAC (SpatioTemporal Asset Catalog)",
        "explanation": """STAC est un standard ouvert pour décrire et cataloguer des données géospatiales.
Il permet de rechercher facilement des données satellites par localisation, date, et caractéristiques.
Le catalogue ESA utilise ce standard.""",
        "examples": ["EO-CAT", "Microsoft Planetary Computer", "AWS Earth Search"]
    },
    "geotiff": {
        "term": "GeoTIFF",
        "explanation": """GeoTIFF est un format de fichier image qui inclut des informations de géoréférencement.
Il permet de localiser précisément chaque pixel sur la Terre. C'est le format le plus courant
pour les données satellites.""",
        "examples": ["Images Sentinel-2", "Modèles numériques de terrain"]
    },
    "cog": {
        "term": "COG (Cloud Optimized GeoTIFF)",
        "explanation": """Le COG est un GeoTIFF optimisé pour le cloud. Il permet d'accéder à une partie
de l'image sans télécharger le fichier entier, ce qui accélère considérablement l'analyse.""",
        "examples": ["Données Sentinel sur AWS", "Google Earth Engine"]
    },
    "ndvi": {
        "term": "NDVI (Normalized Difference Vegetation Index)",
        "explanation": """Le NDVI est un indicateur de la végétation calculé à partir des bandes rouge et proche infrarouge.
Formule : (NIR - Rouge) / (NIR + Rouge). Valeurs de -1 à 1, où les valeurs élevées indiquent une végétation dense.""",
        "examples": ["Suivi des cultures", "Détection de la sécheresse", "Déforestation"]
    },
    "bbox": {
        "term": "Bounding Box (BBOX)",
        "explanation": """Une bounding box est un rectangle qui définit une zone géographique.
Format : [longitude_min, latitude_min, longitude_max, latitude_max].
Utilisée pour filtrer les données par zone géographique.""",
        "examples": ["France métropolitaine : [-5.5, 41.3, 9.6, 51.1]"]
    },
    "granule": {
        "term": "Granule / Item",
        "explanation": """Un granule (ou item) est l'unité de base des données satellites.
C'est une image individuelle acquise à un moment donné sur une zone donnée.
Une collection contient plusieurs granules.""",
        "examples": ["Une tuile Sentinel-2", "Une image Landsat"]
    },
    "resolution": {
        "term": "Résolution Spatiale",
        "explanation": """La résolution spatiale est la taille du plus petit détail visible dans une image.
- Haute résolution : < 5 mètres (détails fins, petites zones)
- Moyenne résolution : 5-30 mètres (Sentinel-2, Landsat)
- Basse résolution : > 100 mètres (couverture globale)""",
        "examples": ["Sentinel-2 : 10m", "Landsat : 30m", "MODIS : 250m-1km"]
    },
    "level": {
        "term": "Niveaux de Traitement (Level)",
        "explanation": """Les données satellites sont traitées à différents niveaux :
- Level 0 : Données brutes
- Level 1 : Données calibrées et géoréférencées
- Level 2 : Données corrigées atmosphériquement
- Level 3 : Produits dérivés (mosaïques, composites)""",
        "examples": ["Sentinel-2 Level-2A (corrigé atmosphère)"]
    }
}


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Exécute un outil et retourne le résultat.

    Args:
        tool_name: Nom de l'outil à exécuter
        arguments: Arguments de l'outil

    Returns:
        Résultat de l'exécution
    """
    logger.info(f"Exécution de l'outil: {tool_name} avec arguments: {arguments}")

    try:
        if tool_name == "search_esa_collections":
            return _search_esa_collections(
                query=arguments.get("query", ""),
                top_k=arguments.get("top_k", 5)
            )

        elif tool_name == "get_collection_details":
            return _get_collection_details(
                collection_id=arguments.get("collection_id", "")
            )

        elif tool_name == "explain_term":
            return _explain_term(
                term=arguments.get("term", "")
            )

        else:
            return {
                "error": f"Outil inconnu: {tool_name}",
                "available_tools": ["search_esa_collections", "get_collection_details", "explain_term"]
            }

    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de {tool_name}: {e}")
        return {"error": str(e)}


def _search_esa_collections(query: str, top_k: int = 5) -> Dict[str, Any]:
    """
    Recherche des collections ESA (sémantique + STAC).
    """
    from ..services.vector_store import vector_store
    from ..services.esa_catalog import esa_catalog

    results = []

    # 1. Recherche sémantique dans la base vectorielle
    try:
        semantic_results = vector_store.semantic_search(query, top_k=top_k)
        for res in semantic_results:
            results.append({
                "id": res["id"],
                "title": res["title"],
                "description": res["description"][:300] + "..." if len(res.get("description", "")) > 300 else res.get("description", ""),
                "relevance_score": res["relevance_score"],
                "source": "semantic_search"
            })
    except Exception as e:
        logger.warning(f"Recherche sémantique échouée: {e}")

    # 2. Si peu de résultats, complète avec STAC direct
    if len(results) < 3:
        try:
            stac_results = esa_catalog.search_collections(query=query, limit=5)
            for col in stac_results:
                # Évite les doublons
                if col["id"] not in [r["id"] for r in results]:
                    results.append({
                        "id": col["id"],
                        "title": col["title"],
                        "description": col["description"][:300] + "..." if len(col.get("description", "")) > 300 else col.get("description", ""),
                        "relevance_score": 0.5,  # Score par défaut pour STAC
                        "source": "stac_catalog"
                    })
        except Exception as e:
            logger.warning(f"Recherche STAC échouée: {e}")

    return {
        "query": query,
        "results_count": len(results),
        "collections": results[:top_k]
    }


def _get_collection_details(collection_id: str) -> Dict[str, Any]:
    """
    Récupère les détails d'une collection.
    """
    from ..services.esa_catalog import esa_catalog

    details = esa_catalog.get_collection_details(collection_id)

    if details is None:
        return {
            "error": f"Collection '{collection_id}' non trouvée",
            "suggestion": "Vérifiez l'identifiant ou recherchez d'abord les collections disponibles"
        }

    # Simplifie pour la réponse
    return {
        "id": details["id"],
        "title": details["title"],
        "description": details["description"],
        "keywords": details["keywords"],
        "temporal_extent": details["temporal_extent"],
        "spatial_extent": details["spatial_extent"],
        "providers": details["providers"],
        "access_links": [
            link for link in details.get("links", [])
            if link.get("rel") in ["self", "root", "items", "license"]
        ]
    }


def _explain_term(term: str) -> Dict[str, Any]:
    """
    Explique un terme technique de l'observation de la Terre.
    """
    term_lower = term.lower().strip()

    # Recherche le terme dans le glossaire
    if term_lower in EARTH_OBSERVATION_GLOSSARY:
        entry = EARTH_OBSERVATION_GLOSSARY[term_lower]
        return {
            "term": entry["term"],
            "explanation": entry["explanation"],
            "examples": entry.get("examples", [])
        }

    # Recherche partielle
    for key, entry in EARTH_OBSERVATION_GLOSSARY.items():
        if term_lower in key or key in term_lower:
            return {
                "term": entry["term"],
                "explanation": entry["explanation"],
                "examples": entry.get("examples", [])
            }

    # Terme non trouvé
    available_terms = list(EARTH_OBSERVATION_GLOSSARY.keys())
    return {
        "term": term,
        "explanation": f"Je n'ai pas d'explication détaillée pour '{term}'. Ce terme peut être très spécifique.",
        "suggestion": "Essayez de me poser une question plus générale sur ce concept.",
        "available_terms": available_terms[:10]
    }
