/**
 * ESA Data Assistant - Frontend Application
 * Interface de chat pour explorer le catalogue ESA
 */

// ============================================================================
// Configuration
// ============================================================================

const API_BASE_URL = '';  // Même origine que le frontend
const MAX_HISTORY = 20;   // Nombre max de messages en mémoire

// ============================================================================
// État de l'application
// ============================================================================

let conversationHistory = [];
let isLoading = false;

// ============================================================================
// Éléments DOM
// ============================================================================

const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const chatForm = document.getElementById('chat-form');
const sendBtn = document.getElementById('send-btn');
const clearBtn = document.getElementById('clear-chat');
const suggestions = document.getElementById('suggestions');
const loadingOverlay = document.getElementById('loading-overlay');
const tooltip = document.getElementById('tooltip');

// ============================================================================
// Initialisation
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initializeChat();
    setupEventListeners();
    autoResizeTextarea();
});

/**
 * Initialise le chat avec le message de bienvenue
 */
async function initializeChat() {
    try {
        // Récupère le message de bienvenue depuis l'API
        const response = await fetch(`${API_BASE_URL}/api/welcome`);
        if (response.ok) {
            const data = await response.json();
            addMessage('assistant', data.message);
        } else {
            // Message de bienvenue par défaut si l'API n'est pas disponible
            addMessage('assistant', getDefaultWelcome());
        }
    } catch (error) {
        console.warn('API non disponible, utilisation du message par défaut');
        addMessage('assistant', getDefaultWelcome());
    }
}

/**
 * Message de bienvenue par défaut
 */
function getDefaultWelcome() {
    return `🛰️ **Bienvenue sur l'Assistant ESA Data !**

Je suis là pour vous aider à explorer le catalogue de données d'observation de la Terre de l'Agence Spatiale Européenne.

**Ce que je peux faire pour vous :**
- 🔍 Rechercher des données satellites (Sentinel, Envisat, etc.)
- 📚 Expliquer les termes techniques (SAR, multispectral, NDVI...)
- 🌍 Vous guider vers les bonnes collections pour vos besoins

N'hésitez pas à poser vos questions ! 😊`;
}

// ============================================================================
// Gestion des événements
// ============================================================================

function setupEventListeners() {
    // Soumission du formulaire
    chatForm.addEventListener('submit', handleSubmit);

    // Entrée avec Enter (Shift+Enter pour nouvelle ligne)
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    });

    // Auto-resize du textarea
    userInput.addEventListener('input', autoResizeTextarea);

    // Bouton nouvelle conversation
    clearBtn.addEventListener('click', clearChat);

    // Boutons de suggestion
    document.querySelectorAll('.suggestion-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const question = btn.dataset.question;
            userInput.value = question;
            handleSubmit(new Event('submit'));
        });
    });
}

/**
 * Redimensionne automatiquement le textarea
 */
function autoResizeTextarea() {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 150) + 'px';
}

// ============================================================================
// Gestion du chat
// ============================================================================

/**
 * Gère la soumission d'un message
 */
async function handleSubmit(e) {
    e.preventDefault();

    const message = userInput.value.trim();
    if (!message || isLoading) return;

    // Ajoute le message utilisateur
    addMessage('user', message);
    conversationHistory.push({ role: 'user', content: message });

    // Réinitialise l'input
    userInput.value = '';
    autoResizeTextarea();

    // Cache les suggestions après le premier message
    hideSuggestions();

    // Envoie le message à l'API
    await sendMessage(message);
}

/**
 * Envoie un message à l'API et affiche la réponse
 */
async function sendMessage(message) {
    setLoading(true);
    showTypingIndicator();

    try {
        const response = await fetch(`${API_BASE_URL}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                conversation_history: conversationHistory.slice(-MAX_HISTORY)
            })
        });

        removeTypingIndicator();

        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }

        const data = await response.json();

        // Ajoute la réponse
        addMessage('assistant', data.response, {
            sources: data.sources || [],
            tools: data.tools_used || []
        });

        // Met à jour l'historique
        conversationHistory.push({ role: 'assistant', content: data.response });

        // Limite la taille de l'historique
        if (conversationHistory.length > MAX_HISTORY * 2) {
            conversationHistory = conversationHistory.slice(-MAX_HISTORY);
        }

    } catch (error) {
        console.error('Erreur:', error);
        removeTypingIndicator();
        addMessage('assistant',
            '😕 Désolé, une erreur s\'est produite. Vérifiez que le serveur est bien démarré et réessayez.');
    } finally {
        setLoading(false);
    }
}

/**
 * Ajoute un message au chat
 */
function addMessage(role, content, meta = {}) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = role === 'user' ? '👤' : '🛰️';

    // Formatte le contenu en HTML
    const formattedContent = formatMessage(content);

    let metaHtml = '';
    if (meta.sources && meta.sources.length > 0) {
        const sourceTags = meta.sources.map(s => `<span class="source-tag">${escapeHtml(s)}</span>`).join('');
        metaHtml += `<div class="sources"><strong>Sources:</strong> ${sourceTags}</div>`;
    }
    if (meta.tools && meta.tools.length > 0) {
        const toolTags = meta.tools.map(t => `<span class="tool-tag">${escapeHtml(t)}</span>`).join('');
        metaHtml += `<div class="tools"><strong>Outils:</strong> ${toolTags}</div>`;
    }

    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            ${formattedContent}
            ${metaHtml ? `<div class="message-meta">${metaHtml}</div>` : ''}
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

/**
 * Formatte le contenu du message (Markdown simplifié)
 */
function formatMessage(content) {
    // Échappe le HTML d'abord
    let html = escapeHtml(content);

    // Gras: **texte**
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Italique: *texte* ou _texte_
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    html = html.replace(/_(.+?)_/g, '<em>$1</em>');

    // Code inline: `code`
    html = html.replace(/`(.+?)`/g, '<code>$1</code>');

    // Liens: [texte](url)
    html = html.replace(/\[(.+?)\]\((https?:\/\/[^\s)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    // Listes à puces: - item
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');

    // Sauts de ligne
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');

    // Enveloppe dans un paragraphe
    html = '<p>' + html + '</p>';

    // Nettoie les paragraphes vides
    html = html.replace(/<p><\/p>/g, '');
    html = html.replace(/<p><ul>/g, '<ul>');
    html = html.replace(/<\/ul><\/p>/g, '</ul>');

    return html;
}

/**
 * Échappe les caractères HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// UI Helpers
// ============================================================================

/**
 * Affiche l'indicateur de chargement
 */
function setLoading(loading) {
    isLoading = loading;
    sendBtn.disabled = loading;
    userInput.disabled = loading;
}

/**
 * Affiche l'indicateur "en train d'écrire"
 */
function showTypingIndicator() {
    const indicator = document.createElement('div');
    indicator.id = 'typing-indicator';
    indicator.className = 'message assistant';
    indicator.innerHTML = `
        <div class="message-avatar">🛰️</div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    chatMessages.appendChild(indicator);
    scrollToBottom();
}

/**
 * Supprime l'indicateur "en train d'écrire"
 */
function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

/**
 * Scroll vers le bas du chat
 */
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Cache les suggestions
 */
function hideSuggestions() {
    if (suggestions) {
        suggestions.style.display = 'none';
    }
}

/**
 * Affiche les suggestions
 */
function showSuggestions() {
    if (suggestions) {
        suggestions.style.display = 'block';
    }
}

/**
 * Efface le chat et recommence
 */
function clearChat() {
    chatMessages.innerHTML = '';
    conversationHistory = [];
    showSuggestions();
    initializeChat();
}

// ============================================================================
// Tooltip pour termes techniques (optionnel)
// ============================================================================

const technicalTerms = {
    'SAR': 'Synthetic Aperture Radar - Radar à synthèse d\'ouverture',
    'NDVI': 'Normalized Difference Vegetation Index - Indice de végétation',
    'Sentinel': 'Satellites du programme Copernicus de l\'UE',
    'multispectral': 'Capture plusieurs bandes du spectre lumineux',
    'GeoTIFF': 'Format d\'image avec informations géographiques',
    'STAC': 'SpatioTemporal Asset Catalog - Standard de catalogage'
};

document.addEventListener('mouseover', (e) => {
    if (e.target.tagName === 'STRONG' || e.target.tagName === 'CODE') {
        const text = e.target.textContent.toUpperCase();
        for (const [term, definition] of Object.entries(technicalTerms)) {
            if (text.includes(term.toUpperCase())) {
                showTooltip(e.target, definition);
                return;
            }
        }
    }
});

document.addEventListener('mouseout', (e) => {
    if (e.target.tagName === 'STRONG' || e.target.tagName === 'CODE') {
        hideTooltip();
    }
});

function showTooltip(element, text) {
    const rect = element.getBoundingClientRect();
    tooltip.textContent = text;
    tooltip.style.left = rect.left + 'px';
    tooltip.style.top = (rect.bottom + 5) + 'px';
    tooltip.classList.remove('hidden');
}

function hideTooltip() {
    tooltip.classList.add('hidden');
}
