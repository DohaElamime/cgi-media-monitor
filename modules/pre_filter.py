"""
Pré-filtre des articles.

Élimine uniquement les pages qui ne correspondent pas
à de véritables articles de presse concernant
la Compagnie Générale Immobilière (CGI Maroc).
"""

# -------------------------------------------------------
# URL à ignorer
# -------------------------------------------------------

BAD_URLS = [
    "/login",
    "/register",
    "/account",
    "/user",
    "/users",
    "/contact",
    "/about",
    "/apropos",
    "/careers",
    "/jobs",
    "/privacy",
    "/terms",
    "/mentions-legales",
    "/cookies",
    "/faq",
    "/tag/",
    "/tags/",
    "/category/",
    "/categories/",
    "/author/",
    "/authors/",
    "/search",
]

# -------------------------------------------------------
# Titres à ignorer
# -------------------------------------------------------

BAD_TITLES = [
    "login",
    "register",
    "home page",
    "privacy policy",
    "mentions légales",
    "conditions",
    "faq",
]

# -------------------------------------------------------
# Pages exactes
# -------------------------------------------------------

BAD_EXACT_URLS = [
    "https://www.cgi.ma/",
    "https://cgi.ma/",
    "https://www.cgi.ma/fr",
    "https://cgi.ma/fr",
    "https://www.cgi.ma/en",
    "https://cgi.ma/en",
    "https://cdgdev.ma/",
    "https://cdgdev.ma/fr",
]

# -------------------------------------------------------
# CGI Canada
# -------------------------------------------------------

CGI_CANADA = [
    "cgi inc",
    "cgi group",
    "apside",
    "didier thérond",
    "didier therond",
    "fès shore",
    "fez shore",
]

# -------------------------------------------------------
# Code Général des Impôts
# -------------------------------------------------------

TAX_KEYWORDS = [
    "code général des impôts",
    "code general des impots",
    "fiscalité",
    "fiscalite",
    "impôts",
    "impot",
    "tva",
    "dgi",
    "direction générale des impôts",
]

# -------------------------------------------------------
# Fonction principale
# -------------------------------------------------------

def is_article_candidate(article):

    url = article.get("url", "").lower().strip()
    title = article.get("title", "").lower().strip()
    body = article.get("body", "").lower().strip()

    text = f"{title} {body}"

    # Pages exactes
    if url in BAD_EXACT_URLS:
        return False

    # URL interdites
    for bad in BAD_URLS:
        if bad in url:
            return False

    # Titres interdits
    for bad in BAD_TITLES:
        if bad in title:
            return False

    # Titre vide ou trop court
    if len(title.split()) < 3:
        return False

    # CGI Canada
    for keyword in CGI_CANADA:
        if keyword in text:
            return False

    # Code Général des Impôts
    if "cgi" not in text and "compagnie générale immobilière" not in text:
        for keyword in TAX_KEYWORDS:
            if keyword in text:
                return False

    return True