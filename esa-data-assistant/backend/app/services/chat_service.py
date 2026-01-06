"""
Service de conversation avec Mistral AI.
Gère le dialogue avec l'utilisateur et le function calling.
"""

import json
import logging
import uuid
from typing import List, Dict, Any, Optional
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

from ..config import settings
from ..tools.esa_tools import ESA_TOOLS, execute_tool

# Configuration du logger
logger = logging.getLogger(__name__)

# System prompt pour le chatbot
SYSTEM_PROMPT = """Tu es l'Assistant ESA Data, un expert amical qui aide les utilisateurs à trouver des données d'observation de la Terre dans le catalogue de l'Agence Spatiale Européenne (ESA).

🛰️ **Ton rôle :**
- Aider les utilisateurs (même débutants) à trouver les bonnes données satellites pour leurs besoins
- Expliquer les concepts techniques de manière simple et accessible
- Guider vers les collections de données les plus pertinentes

📋 **Comment répondre :**
1. Sois concis mais informatif
2. Utilise des exemples concrets quand c'est utile
3. Propose des suggestions si la demande est vague
4. Explique les termes techniques quand tu les utilises

🔧 **Tes outils :**
- Tu peux rechercher dans le catalogue ESA avec `search_esa_collections`
- Tu peux obtenir les détails d'une collection avec `get_collection_details`
- Tu peux expliquer des termes techniques avec `explain_term`

💡 **Exemples de questions que tu peux traiter :**
- "Quelles données existent sur la déforestation ?"
- "Je cherche des images radar de la France"
- "C'est quoi le NDVI ?"
- "Comment accéder aux données Sentinel-2 ?"

Réponds toujours en français. Sois enthousiaste mais professionnel."""


class ChatService:
    """
    Service de gestion des conversations avec Mistral AI.
    Utilise le function calling pour interroger le catalogue ESA.
    """

    def __init__(self):
        """Initialise le service de chat."""
        self._client = None

    def _get_client(self) -> MistralClient:
        """
        Retourne le client Mistral (initialisation paresseuse).

        Returns:
            Client Mistral configuré

        Raises:
            ValueError: Si la clé API n'est pas configurée
        """
        if self._client is None:
            if not settings.mistral_api_key:
                raise ValueError(
                    "La clé API Mistral n'est pas configurée. "
                    "Définissez MISTRAL_API_KEY dans le fichier .env"
                )

            logger.info("Initialisation du client Mistral")
            self._client = MistralClient(api_key=settings.mistral_api_key)

        return self._client

    async def chat(
        self,
        message: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Traite un message de l'utilisateur et génère une réponse.

        Args:
            message: Message de l'utilisateur
            conversation_history: Historique des messages précédents

        Returns:
            Dictionnaire avec la réponse et les métadonnées
        """
        try:
            client = self._get_client()

            # Construit l'historique des messages
            messages = self._build_messages(message, conversation_history or [])

            logger.info(f"Envoi du message à Mistral: {message[:100]}...")

            # Premier appel à Mistral (peut inclure des tool calls)
            response = client.chat(
                model=settings.mistral_model,
                messages=messages,
                tools=ESA_TOOLS,
                tool_choice="auto"
            )

            # Récupère la réponse
            assistant_message = response.choices[0].message
            tools_used = []
            sources = []

            # Vérifie si des outils ont été appelés
            if assistant_message.tool_calls:
                logger.info(f"Outils appelés: {len(assistant_message.tool_calls)}")

                # Exécute chaque outil
                tool_results = []
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    # Génère un ID si non fourni par l'API
                    tool_call_id = getattr(tool_call, 'id', None) or f"call_{uuid.uuid4().hex[:8]}"

                    logger.info(f"Exécution de {tool_name} avec {tool_args} (id: {tool_call_id})")
                    tools_used.append(tool_name)

                    # Exécute l'outil
                    result = execute_tool(tool_name, tool_args)

                    # Ajoute les sources si disponibles
                    if "collections" in result:
                        for col in result.get("collections", []):
                            sources.append(col.get("title", col.get("id", "")))

                    tool_results.append({
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "result": json.dumps(result, ensure_ascii=False)
                    })

                # Ajoute les résultats des outils aux messages
                # Convertit assistant_message en dict pour ajouter aux messages
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        {
                            "id": tr["tool_call_id"],
                            "type": "function",
                            "function": {
                                "name": tr["name"],
                                "arguments": tool_call.function.arguments
                            }
                        }
                        for tr, tool_call in zip(tool_results, assistant_message.tool_calls)
                    ]
                })

                for tr in tool_results:
                    messages.append({
                        "role": "tool",
                        "name": tr["name"],
                        "content": tr["result"],
                        "tool_call_id": tr["tool_call_id"]
                    })

                # Deuxième appel pour générer la réponse finale
                final_response = client.chat(
                    model=settings.mistral_model,
                    messages=messages
                )

                final_content = final_response.choices[0].message.content

            else:
                # Pas d'appel d'outil, utilise la réponse directe
                final_content = assistant_message.content

            logger.info("Réponse générée avec succès")

            return {
                "response": final_content,
                "sources": list(set(sources)),  # Déduplique
                "tools_used": tools_used
            }

        except ValueError as e:
            logger.error(f"Erreur de configuration: {e}")
            return {
                "response": f"⚠️ Erreur de configuration : {str(e)}",
                "sources": [],
                "tools_used": []
            }

        except Exception as e:
            logger.error(f"Erreur lors du chat: {e}")
            return {
                "response": (
                    "😕 Désolé, une erreur s'est produite lors du traitement de votre message. "
                    "Veuillez réessayer dans quelques instants."
                ),
                "sources": [],
                "tools_used": []
            }

    def _build_messages(
        self,
        current_message: str,
        history: List[Dict[str, str]]
    ) -> List[ChatMessage]:
        """
        Construit la liste des messages pour l'API Mistral.

        Args:
            current_message: Message actuel de l'utilisateur
            history: Historique de la conversation

        Returns:
            Liste de ChatMessage pour l'API
        """
        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT)
        ]

        # Ajoute l'historique (limité aux 10 derniers messages)
        for msg in history[-10:]:
            messages.append(ChatMessage(
                role=msg.get("role", "user"),
                content=msg.get("content", "")
            ))

        # Ajoute le message actuel
        messages.append(ChatMessage(role="user", content=current_message))

        return messages

    def get_welcome_message(self) -> str:
        """
        Retourne le message de bienvenue du chatbot.

        Returns:
            Message de bienvenue formaté
        """
        return """🛰️ **Bienvenue sur l'Assistant ESA Data !**

Je suis là pour vous aider à explorer le catalogue de données d'observation de la Terre de l'Agence Spatiale Européenne.

**Ce que je peux faire pour vous :**
- 🔍 Rechercher des données satellites (Sentinel, envisat, etc.)
- 📚 Expliquer les termes techniques (SAR, multispectral, NDVI...)
- 🌍 Vous guider vers les bonnes collections pour vos besoins

**Exemples de questions :**
- "Quelles données sont disponibles sur les forêts ?"
- "Je cherche des images radar récentes"
- "Comment accéder aux données Sentinel-2 ?"
- "C'est quoi le SAR ?"

N'hésitez pas à poser vos questions, même si vous êtes débutant ! 😊"""


# Instance singleton pour utilisation globale
chat_service = ChatService()
