"""
Service de scraping pour ESA EO Gateway.
Récupère les détails techniques des collections depuis earth.esa.int/eogateway
"""

import logging
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, quote
import httpx
from bs4 import BeautifulSoup

from ..config import settings

# Configuration du logger
logger = logging.getLogger(__name__)

# URL de base du site ESA EO Gateway
ESA_GATEWAY_BASE_URL = "https://earth.esa.int/eogateway"
ESA_GATEWAY_CATALOG_URL = f"{ESA_GATEWAY_BASE_URL}/catalog"


class ESAGatewayService:
    """
    Service pour récupérer les détails techniques depuis ESA EO Gateway.
    Scrape les pages du catalogue pour obtenir les spécifications complètes.
    """

    def __init__(self):
        """Initialise le service."""
        self._client = None

    def _get_client(self) -> httpx.Client:
        """Retourne un client HTTP configuré."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "ESA-Data-Assistant/1.0 (Educational Chatbot)",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8"
                }
            )
        return self._client

    def search_catalog(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Recherche dans le catalogue ESA EO Gateway.

        Args:
            query: Terme de recherche
            limit: Nombre max de résultats

        Returns:
            Liste des résultats avec titre, URL et description courte
        """
        try:
            client = self._get_client()

            # URL de recherche ESA Gateway
            search_url = f"{ESA_GATEWAY_BASE_URL}/search"
            params = {
                "text": query,
                "category": "data"
            }

            logger.info(f"Recherche ESA Gateway: {query}")
            response = client.get(search_url, params=params)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')
            results = []

            # Parse les résultats de recherche
            # Structure typique: articles avec liens vers les pages détaillées
            articles = soup.select('article, .search-result, .result-item, .card')

            for article in articles[:limit]:
                # Cherche le lien et le titre
                link = article.find('a', href=True)
                if not link:
                    continue

                href = link.get('href', '')
                if '/catalog/' not in href and '/documents/' not in href:
                    continue

                title = link.get_text(strip=True)
                if not title:
                    title_elem = article.find(['h2', 'h3', 'h4', '.title'])
                    title = title_elem.get_text(strip=True) if title_elem else "Sans titre"

                # Description courte
                desc_elem = article.find(['p', '.description', '.summary'])
                description = desc_elem.get_text(strip=True)[:200] if desc_elem else ""

                full_url = urljoin(ESA_GATEWAY_BASE_URL, href)

                results.append({
                    "title": title,
                    "url": full_url,
                    "description": description
                })

            logger.info(f"Trouvé {len(results)} résultats")
            return results

        except Exception as e:
            logger.error(f"Erreur recherche ESA Gateway: {e}")
            return []

    def get_collection_details(self, collection_name: str) -> Dict[str, Any]:
        """
        Récupère les détails techniques d'une collection depuis ESA Gateway.

        Args:
            collection_name: Nom de la collection (ex: "swarm-level-1-b")

        Returns:
            Dictionnaire avec les détails techniques
        """
        try:
            client = self._get_client()

            # Construit l'URL de la collection
            # Format: https://earth.esa.int/eogateway/catalog/swarm-level-1-b
            slug = self._normalize_slug(collection_name)
            url = f"{ESA_GATEWAY_CATALOG_URL}/{slug}"

            logger.info(f"Récupération détails depuis: {url}")
            response = client.get(url)

            if response.status_code == 404:
                # Essaie une recherche pour trouver le bon URL
                logger.info(f"Page non trouvée, recherche de: {collection_name}")
                return self._search_and_get_details(collection_name)

            response.raise_for_status()
            return self._parse_collection_page(response.text, url)

        except Exception as e:
            logger.error(f"Erreur récupération détails: {e}")
            return {"error": str(e)}

    def _search_and_get_details(self, query: str) -> Dict[str, Any]:
        """Recherche puis récupère les détails du premier résultat."""
        results = self.search_catalog(query, limit=1)
        if results:
            # Récupère la page du premier résultat
            try:
                client = self._get_client()
                response = client.get(results[0]["url"])
                response.raise_for_status()
                return self._parse_collection_page(response.text, results[0]["url"])
            except Exception as e:
                logger.error(f"Erreur récupération: {e}")

        return {"error": f"Collection '{query}' non trouvée sur ESA Gateway"}

    def _parse_collection_page(self, html: str, url: str) -> Dict[str, Any]:
        """
        Parse une page de collection ESA Gateway pour extraire les détails.

        Args:
            html: Contenu HTML de la page
            url: URL de la page

        Returns:
            Dictionnaire structuré avec les détails
        """
        soup = BeautifulSoup(html, 'lxml')
        details = {
            "url": url,
            "source": "ESA EO Gateway"
        }

        # Titre
        title_elem = soup.find(['h1', '.page-title', '.document-title'])
        if title_elem:
            details["title"] = title_elem.get_text(strip=True)

        # Description
        desc_elem = soup.find(['article', '.description', '.abstract', '.content'])
        if desc_elem:
            # Prend les premiers paragraphes
            paragraphs = desc_elem.find_all('p')[:3]
            details["description"] = " ".join(p.get_text(strip=True) for p in paragraphs)

        # Spécifications techniques
        specs = self._extract_specifications(soup)
        if specs:
            details["technical_specifications"] = specs

        # Tables de données (DATA SET SPECIFICATIONS)
        tables_data = self._extract_tables(soup)
        if tables_data:
            details["data_specifications"] = tables_data

        # Liens de téléchargement et documentation
        links = self._extract_links(soup)
        if links:
            details["related_links"] = links

        # Métadonnées additionnelles
        metadata = self._extract_metadata(soup)
        if metadata:
            details.update(metadata)

        return details

    def _extract_specifications(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extrait les spécifications techniques."""
        specs = {}

        # Cherche les sections de spécifications
        spec_patterns = [
            'spatial coverage', 'temporal coverage', 'orbit', 'resolution',
            'date of launch', 'operators', 'mission status', 'processor version',
            'orbit height', 'orbit type', 'swath width', 'revisit time'
        ]

        # Méthode 1: Cherche dans les listes de définition
        for dl in soup.find_all('dl'):
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for dt, dd in zip(dts, dds):
                key = dt.get_text(strip=True).lower()
                value = dd.get_text(strip=True)
                if any(pattern in key for pattern in spec_patterns):
                    specs[self._normalize_key(key)] = value

        # Méthode 2: Cherche dans les tableaux
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)
                    if any(pattern in key for pattern in spec_patterns):
                        specs[self._normalize_key(key)] = value

        # Méthode 3: Cherche dans les sections avec label/value
        for elem in soup.find_all(class_=re.compile(r'(spec|detail|info|meta)')):
            text = elem.get_text(strip=True)
            for pattern in spec_patterns:
                if pattern in text.lower():
                    # Essaie d'extraire la valeur après ":"
                    match = re.search(rf'{pattern}[:\s]+([^\n]+)', text, re.IGNORECASE)
                    if match:
                        specs[self._normalize_key(pattern)] = match.group(1).strip()

        return specs

    def _extract_tables(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extrait les données des tableaux."""
        tables_data = []

        for table in soup.find_all('table'):
            # Trouve le titre du tableau
            caption = table.find('caption')
            title = caption.get_text(strip=True) if caption else "Data Table"

            headers = []
            rows_data = []

            # En-têtes
            header_row = table.find('thead') or table.find('tr')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]

            # Données
            tbody = table.find('tbody') or table
            for row in tbody.find_all('tr')[1:]:  # Skip header
                cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                if cells and any(cells):
                    rows_data.append(cells)

            if headers or rows_data:
                tables_data.append({
                    "title": title,
                    "headers": headers,
                    "rows": rows_data[:10]  # Limite à 10 lignes
                })

        return tables_data

    def _extract_links(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extrait les liens utiles (documentation, téléchargement, etc.)."""
        links = []

        link_keywords = ['download', 'access', 'documentation', 'guide', 'handbook',
                        'user', 'technical', 'browse', 'product']

        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            text = a.get_text(strip=True)

            # Filtre les liens pertinents
            if any(kw in text.lower() or kw in href.lower() for kw in link_keywords):
                full_url = urljoin(ESA_GATEWAY_BASE_URL, href)
                if full_url not in [l['url'] for l in links]:
                    links.append({
                        "title": text[:100],
                        "url": full_url
                    })

        return links[:10]  # Limite à 10 liens

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extrait les métadonnées de la page."""
        metadata = {}

        # Meta tags
        for meta in soup.find_all('meta'):
            name = meta.get('name', '') or meta.get('property', '')
            content = meta.get('content', '')
            if name and content:
                if 'date' in name.lower():
                    metadata['date'] = content
                elif 'author' in name.lower():
                    metadata['author'] = content
                elif 'keywords' in name.lower():
                    metadata['keywords'] = content

        return metadata

    def _normalize_slug(self, name: str) -> str:
        """Convertit un nom en slug URL."""
        # Remplace espaces et underscores par des tirets
        slug = re.sub(r'[\s_]+', '-', name.lower())
        # Supprime les caractères non-alphanumériques
        slug = re.sub(r'[^a-z0-9\-]', '', slug)
        # Supprime les tirets multiples
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')

    def _normalize_key(self, key: str) -> str:
        """Normalise une clé de spécification."""
        key = re.sub(r'[:\s]+', '_', key.lower())
        key = re.sub(r'[^a-z0-9_]', '', key)
        return key


# Instance singleton
esa_gateway = ESAGatewayService()
