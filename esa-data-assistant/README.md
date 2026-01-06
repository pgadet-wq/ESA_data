# 🛰️ ESA Data Assistant

Chatbot intelligent pour explorer le catalogue de données satellites de l'Agence Spatiale Européenne (ESA).

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 📋 Description

ESA Data Assistant est un prototype de chatbot web qui permet aux utilisateurs (même débutants) de rechercher des données d'observation de la Terre dans le catalogue ESA via une conversation naturelle.

### Fonctionnalités

- 🔍 **Recherche sémantique** : Trouvez des collections de données avec des requêtes en langage naturel
- 💬 **Interface conversationnelle** : Posez vos questions comme à un expert
- 📚 **Explications pédagogiques** : Les termes techniques sont expliqués simplement
- 🎨 **Design spatial** : Interface moderne avec thème sombre

## 🏗️ Architecture

```
esa-data-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py              # Application FastAPI
│   │   ├── config.py            # Configuration
│   │   ├── services/
│   │   │   ├── esa_catalog.py   # Client STAC pour ESA
│   │   │   ├── vector_store.py  # ChromaDB embeddings
│   │   │   └── chat_service.py  # Logique Mistral AI
│   │   ├── models/
│   │   │   └── schemas.py       # Modèles Pydantic
│   │   └── tools/
│   │       └── esa_tools.py     # Function calling
│   ├── scripts/
│   │   └── index_esa_data.py    # Script d'indexation
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── docker-compose.yml
├── .env.example
└── README.md
```

## 🚀 Installation

### Prérequis

- Python 3.11+
- Clé API Mistral ([obtenir une clé](https://console.mistral.ai/))
- Docker (optionnel, pour le déploiement)

### Installation locale

1. **Clonez le repository**
   ```bash
   git clone <repo-url>
   cd esa-data-assistant
   ```

2. **Créez un environnement virtuel**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # ou
   .\venv\Scripts\activate   # Windows
   ```

3. **Installez les dépendances**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. **Configurez les variables d'environnement**
   ```bash
   cd ..
   cp .env.example .env
   # Éditez .env et ajoutez votre clé API Mistral
   ```

5. **Indexez les collections ESA** (première fois uniquement)
   ```bash
   cd backend
   python scripts/index_esa_data.py
   ```

6. **Lancez l'application**
   ```bash
   uvicorn app.main:app --reload
   ```

7. **Ouvrez votre navigateur** sur [http://localhost:8000](http://localhost:8000)

### Installation avec Docker

1. **Configurez l'environnement**
   ```bash
   cp .env.example .env
   # Éditez .env avec votre clé API Mistral
   ```

2. **Lancez avec Docker Compose**
   ```bash
   docker-compose up -d
   ```

3. **Indexez les données** (première fois)
   ```bash
   docker-compose exec app python scripts/index_esa_data.py
   ```

4. **Accédez à l'application** sur [http://localhost](http://localhost)

## 📖 Utilisation

### Exemples de questions

- "Quelles données sont disponibles sur les forêts ?"
- "Je cherche des images radar récentes"
- "Comment accéder aux données Sentinel-2 ?"
- "C'est quoi le SAR ?"
- "Montre-moi des données sur les océans"

### API Endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/` | GET | Interface web du chatbot |
| `/api/chat` | POST | Envoie un message au chatbot |
| `/api/collections` | GET | Liste les collections indexées |
| `/api/health` | GET | Health check |
| `/api/stats` | GET | Statistiques du système |
| `/docs` | GET | Documentation Swagger |

### Exemple de requête API

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Quelles données sur les forêts ?", "conversation_history": []}'
```

## ⚙️ Configuration

Variables d'environnement dans `.env` :

| Variable | Description | Défaut |
|----------|-------------|--------|
| `MISTRAL_API_KEY` | Clé API Mistral (obligatoire) | - |
| `MISTRAL_MODEL` | Modèle Mistral à utiliser | `mistral-small-latest` |
| `ESA_CATALOG_URL` | URL du catalogue ESA | `https://eocat.esa.int/eo-catalogue/` |
| `CHROMA_PERSIST_DIR` | Répertoire de persistance ChromaDB | `./data/chroma` |
| `LOG_LEVEL` | Niveau de log | `INFO` |

## 🔧 Développement

### Structure du code

- **`esa_catalog.py`** : Client STAC pour interroger le catalogue ESA EO-CAT
- **`vector_store.py`** : Gestion des embeddings avec ChromaDB et sentence-transformers
- **`chat_service.py`** : Logique de conversation avec Mistral AI et function calling
- **`esa_tools.py`** : Définition des outils pour le function calling

### Ajouter un nouveau terme au glossaire

Éditez `backend/app/tools/esa_tools.py` et ajoutez une entrée dans `EARTH_OBSERVATION_GLOSSARY` :

```python
"nouveau_terme": {
    "term": "Nouveau Terme",
    "explanation": "Explication détaillée...",
    "examples": ["Exemple 1", "Exemple 2"]
}
```

### Tests

```bash
cd backend
pytest tests/
```

## 🚢 Déploiement

### Scaleway

1. Créez une instance Scaleway (DEV1-S minimum)
2. Installez Docker et Docker Compose
3. Clonez le projet et configurez `.env`
4. Lancez avec `docker-compose up -d`

### Autres plateformes

L'application est compatible avec :
- AWS EC2 / ECS
- Google Cloud Run
- Azure Container Instances
- Heroku (avec adaptations)

## 📝 Licence

MIT License - voir [LICENSE](LICENSE)

## 🤝 Contribution

Les contributions sont bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

## 🙏 Remerciements

- [ESA](https://www.esa.int/) pour le catalogue EO-CAT
- [Mistral AI](https://mistral.ai/) pour le modèle de langage
- [ChromaDB](https://www.trychroma.com/) pour la base vectorielle
- [FastAPI](https://fastapi.tiangolo.com/) pour le framework web
