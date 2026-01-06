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
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9"
                }
            )
        return self._client

    def get_collection_details(self, collection_name: str) -> Dict[str, Any]:
        """
        Récupère les détails techniques d'une collection depuis ESA Gateway.

        Args:
            collection_name: Nom de la collection (ex: "Swarm Level 1B")

        Returns:
            Dictionnaire avec les détails techniques
        """
        try:
            client = self._get_client()

            # Essaie plusieurs variantes de slug
            slugs_to_try = self._generate_slug_variants(collection_name)

            for slug in slugs_to_try:
                url = f"{ESA_GATEWAY_CATALOG_URL}/{slug}"
                logger.info(f"Tentative URL: {url}")

                response = client.get(url)

                if response.status_code == 200:
                    logger.info(f"Page trouvée: {url}")
                    return self._parse_collection_page(response.text, url)

            # Si aucun slug ne fonctionne, essaie une recherche
            logger.info(f"Aucun slug trouvé, recherche de: {collection_name}")
            return self._search_and_get_details(collection_name)

        except Exception as e:
            logger.error(f"Erreur récupération détails: {e}")
            return {"error": str(e)}

    def _generate_slug_variants(self, name: str) -> List[str]:
        """
        Génère plusieurs variantes de slug pour un nom de collection.
        Ex: "Swarm Level 1B" -> ["swarm-level-1-b", "swarm-level-1b", "swarm-level1b"]
        """
        name_lower = name.lower().strip()
        variants = []

        # Variante 1: Tirets entre tous les éléments, y compris chiffre-lettre
        # "Swarm Level 1B" -> "swarm-level-1-b"
        slug1 = re.sub(r'[\s_]+', '-', name_lower)
        # Ajoute un tiret entre chiffre et lettre (1B -> 1-b)
        slug1 = re.sub(r'(\d)([a-z])', r'\1-\2', slug1)
        slug1 = re.sub(r'[^a-z0-9\-]', '', slug1)
        slug1 = re.sub(r'-+', '-', slug1).strip('-')
        variants.append(slug1)

        # Variante 2: Sans tiret entre chiffre et lettre
        # "Swarm Level 1B" -> "swarm-level-1b"
        slug2 = re.sub(r'[\s_]+', '-', name_lower)
        slug2 = re.sub(r'[^a-z0-9\-]', '', slug2)
        slug2 = re.sub(r'-+', '-', slug2).strip('-')
        if slug2 != slug1:
            variants.append(slug2)

        # Variante 3: Tout collé
        # "Swarm Level 1B" -> "swarmlevel1b"
        slug3 = re.sub(r'[^a-z0-9]', '', name_lower)
        if slug3 not in variants:
            variants.append(slug3)

        return variants

    def _search_and_get_details(self, query: str) -> Dict[str, Any]:
        """Recherche dans le catalogue puis récupère les détails."""
        try:
            client = self._get_client()

            # Recherche sur le site ESA
            search_url = f"{ESA_GATEWAY_BASE_URL}/search"
            params = {"text": query, "category": "data"}

            logger.info(f"Recherche ESA Gateway: {query}")
            response = client.get(search_url, params=params)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')

            # Cherche les liens vers le catalogue
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if '/catalog/' in href:
                    full_url = urljoin(ESA_GATEWAY_BASE_URL, href)
                    logger.info(f"Trouvé lien catalogue: {full_url}")

                    page_response = client.get(full_url)
                    if page_response.status_code == 200:
                        return self._parse_collection_page(page_response.text, full_url)

            return {"error": f"Collection '{query}' non trouvée sur ESA Gateway"}

        except Exception as e:
            logger.error(f"Erreur recherche: {e}")
            return {"error": str(e)}

    def _parse_collection_page(self, html: str, url: str) -> Dict[str, Any]:
        """
        Parse une page de collection ESA Gateway pour extraire les détails.
        """
        soup = BeautifulSoup(html, 'lxml')
        details = {
            "url": url,
            "source": "ESA EO Gateway"
        }

        # Titre principal (h1)
        h1 = soup.find('h1')
        if h1:
            details["title"] = h1.get_text(strip=True)

        # Description - cherche dans la section "Collection Description"
        description = self._extract_section_content(soup,
            ["collection description", "description", "abstract", "overview"])
        if description:
            details["description"] = description

        # Spécifications techniques - cherche "Technical Details" ou "DATA SET SPECIFICATIONS"
        specs = self._extract_technical_specs(soup)
        if specs:
            details["technical_specifications"] = specs

        # Comment accéder aux données
        access_info = self._extract_section_content(soup,
            ["how to access", "access data", "data access"])
        if access_info:
            details["access_information"] = access_info

        # Ressources et liens
        resources = self._extract_resources(soup)
        if resources:
            details["resources"] = resources

        # Termes et conditions
        terms = self._extract_section_content(soup,
            ["terms", "conditions", "license", "policy"])
        if terms:
            details["terms_and_conditions"] = terms[:500]

        return details

    def _extract_section_content(self, soup: BeautifulSoup, keywords: List[str]) -> Optional[str]:
        """
        Extrait le contenu d'une section basée sur son titre.
        """
        # Cherche les headings (h2, h3, h4) contenant les keywords
        for heading in soup.find_all(['h2', 'h3', 'h4', 'h5']):
            heading_text = heading.get_text(strip=True).lower()
            if any(kw in heading_text for kw in keywords):
                # Récupère le contenu après ce heading jusqu'au prochain heading
                content_parts = []
                for sibling in heading.find_next_siblings():
                    if sibling.name in ['h2', 'h3', 'h4', 'h5']:
                        break
                    text = sibling.get_text(strip=True)
                    if text:
                        content_parts.append(text)

                if content_parts:
                    return " ".join(content_parts)

        return None

    def _extract_technical_specs(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Extrait les spécifications techniques de la page.
        Cherche dans les sections "Technical Details" et les tableaux/listes.
        """
        specs = {}

        # Liste des spécifications à chercher
        spec_keys = [
            ("spatial coverage", "spatial_coverage"),
            ("temporal coverage", "temporal_coverage"),
            ("date of launch", "launch_date"),
            ("operators", "operators"),
            ("mission status", "mission_status"),
            ("orbit height", "orbit_height"),
            ("orbit type", "orbit_type"),
            ("current processor version", "processor_version"),
            ("processing level", "processing_level"),
            ("resolution", "resolution"),
            ("swath width", "swath_width"),
            ("revisit time", "revisit_time"),
        ]

        # Méthode 1: Cherche dans les definition lists (dl/dt/dd)
        for dl in soup.find_all('dl'):
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for dt, dd in zip(dts, dds):
                key_text = dt.get_text(strip=True).lower()
                value_text = dd.get_text(strip=True)
                for pattern, key_name in spec_keys:
                    if pattern in key_text:
                        specs[key_name] = value_text
                        break

        # Méthode 2: Cherche les patterns "Label: Value" dans le texte
        page_text = soup.get_text()
        for pattern, key_name in spec_keys:
            if key_name not in specs:
                # Regex pour trouver "Pattern: Value" ou "Pattern Value"
                regex = rf'{pattern}[:\s]*([^\n]+?)(?:\n|$)'
                match = re.search(regex, page_text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    # Nettoie la valeur
                    value = re.sub(r'\s+', ' ', value)
                    if value and len(value) < 200:
                        specs[key_name] = value

        # Méthode 3: Cherche dans les tableaux
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key_text = cells[0].get_text(strip=True).lower()
                    value_text = cells[1].get_text(strip=True)
                    for pattern, key_name in spec_keys:
                        if pattern in key_text and key_name not in specs:
                            specs[key_name] = value_text
                            break

        # Méthode 4: Cherche dans les divs avec classes spécifiques
        for div in soup.find_all(['div', 'section'], class_=re.compile(r'(spec|detail|info|meta|field)')):
            div_text = div.get_text(strip=True)
            for pattern, key_name in spec_keys:
                if pattern in div_text.lower() and key_name not in specs:
                    # Essaie d'extraire la valeur
                    match = re.search(rf'{pattern}[:\s]*([^\n]+)', div_text, re.IGNORECASE)
                    if match:
                        specs[key_name] = match.group(1).strip()[:200]

        return specs

    def _extract_resources(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        Extrait les liens vers les ressources (documentation, téléchargements).
        """
        resources = []
        seen_urls = set()

        # Mots-clés pour identifier les ressources utiles
        keywords = ['download', 'document', 'guide', 'handbook', 'algorithm',
                   'format', 'product', 'manual', 'specification', 'quality',
                   'processor', 'software', 'tool', 'dissemination', 'access']

        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            text = a.get_text(strip=True)

            # Filtre les liens pertinents
            if not text or len(text) < 3:
                continue

            text_lower = text.lower()
            href_lower = href.lower()

            if any(kw in text_lower or kw in href_lower for kw in keywords):
                full_url = urljoin(ESA_GATEWAY_BASE_URL, href)

                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    resources.append({
                        "title": text[:100],
                        "url": full_url
                    })

        return resources[:15]  # Limite à 15 ressources


# Instance singleton
esa_gateway = ESAGatewayService()
