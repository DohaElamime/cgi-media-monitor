# ==========================================================
# CGI MEDIA MONITOR
# Configuration
# ==========================================================

# ===========================
# DATABASE
# ===========================

DATABASE_PATH = "database/articles.db"


# ===========================
# LOGS
# ===========================

LOG_FOLDER = "logs"


# ===========================
# SEARCH
# ===========================

MAX_RESULTS = 20

GOOGLE_NEWS_BASE_URL = "https://news.google.com/rss/search?q="

SEARCH_QUERIES = [

    # ==========================================
    # Requêtes principales
    # ==========================================

    '"Compagnie Générale Immobilière"',
    '"Compagnie Générale Immobilière Maroc"',
    '"CGI Maroc"',
    '"CGI immobilier"',
    '"CGI" promoteur immobilier',
    '"CGI" immobilier Maroc',
    '"CDG Développement" CGI',

    # ==========================================
    # Médias économiques
    # ==========================================

    'site:medias24.com "Compagnie Générale Immobilière"',
    'site:medias24.com "CGI Maroc"',

    'site:leconomiste.com "Compagnie Générale Immobilière"',
    'site:leconomiste.com "CGI Maroc"',

    'site:lematin.ma "Compagnie Générale Immobilière"',
    'site:lematin.ma "CGI Maroc"',

    'site:challenge.ma "Compagnie Générale Immobilière"',
    'site:challenge.ma "CGI Maroc"',

    'site:boursenews.ma "Compagnie Générale Immobilière"',
    'site:boursenews.ma "CGI Maroc"',

    'site:lavieeco.com "Compagnie Générale Immobilière"',
    'site:lavieeco.com "CGI Maroc"',

    'site:leseco.ma "Compagnie Générale Immobilière"',
    'site:leseco.ma "CGI Maroc"',

    'site:le360.ma "Compagnie Générale Immobilière"',
    'site:le360.ma "CGI Maroc"',

    'site:mapnews.ma "Compagnie Générale Immobilière"',
    'site:mapnews.ma "CGI Maroc"',
]


# ===========================
# ALLOWED DOMAINS
# ===========================

ALLOWED_DOMAINS = {

    # Sites officiels
    "cgi.ma",
    "cdgdev.ma",

    # Presse économique
    "medias24.com",
    "lematin.ma",
    "leconomiste.com",
    "challenge.ma",
    "boursenews.ma",
    "leseco.ma",
    "lavieeco.com",
    "le360.ma",
    "mapnews.ma",
    "hespress.com",

}


# ===========================
# ARTICLE EXTRACTION
# ===========================

REQUEST_TIMEOUT = 20

MAX_ARTICLE_LENGTH = 10000


# ===========================
# AI
# ===========================

RELEVANCE_MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"

SENTIMENT_MODEL = "tabularisai/multilingual-sentiment-analysis"

# ===========================
# STREAMLIT
# ===========================

PAGE_TITLE = "CGI Media Monitor"

PAGE_ICON = "📰"

LAYOUT = "wide"