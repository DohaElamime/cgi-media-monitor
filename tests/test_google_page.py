import os
import sys
import re
import sqlite3

import requests
from bs4 import BeautifulSoup


# ============================================================
# TROUVER LA RACINE DU PROJET
# ============================================================

CURRENT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

ROOT_DIR = os.path.dirname(
    CURRENT_DIR
)

print("ROOT DIR =", ROOT_DIR)


# ============================================================
# TROUVER LA BASE SQLITE
# ============================================================

DATABASE_PATH = os.path.join(
    ROOT_DIR,
    "database",
    "articles.db"
)

print("DATABASE =", DATABASE_PATH)


if not os.path.exists(DATABASE_PATH):
    print()
    print("[ERREUR] Base SQLite introuvable :")
    print(DATABASE_PATH)
    sys.exit(1)


# ============================================================
# RÉCUPÉRER L'ARTICLE 253
# ============================================================

conn = sqlite3.connect(
    DATABASE_PATH
)

conn.row_factory = sqlite3.Row

article = conn.execute(
    """
    SELECT
        id,
        title,
        source,
        url
    FROM articles
    WHERE id = 253
    """
).fetchone()

conn.close()


if article is None:
    print()
    print("[ERREUR] Article ID 253 introuvable.")
    sys.exit(1)


# ============================================================
# AFFICHAGE
# ============================================================

print()
print("=" * 70)
print("TEST GOOGLE NEWS")
print("=" * 70)

print()
print("ID     :", article["id"])
print("TITRE  :", article["title"])
print("SOURCE :", article["source"])
print("URL    :", article["url"])


# ============================================================
# TÉLÉCHARGER GOOGLE NEWS
# ============================================================

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


try:

    response = requests.get(
        article["url"],
        headers=headers,
        timeout=20,
        allow_redirects=True,
    )

except Exception as exc:

    print()
    print("[ERREUR HTTP]")
    print(exc)

    sys.exit(1)


# ============================================================
# INFOS
# ============================================================

print()
print("STATUS     =", response.status_code)
print("URL FINALE =", response.url)
print("HTML       =", len(response.text))


# ============================================================
# RECHERCHE LE360
# ============================================================

html = response.text

print()
print(
    "CONTIENT LE360 =",
    "le360.ma" in html.lower()
)


# ============================================================
# EXTRAIRE LES URLS LE360
# ============================================================

print()
print("=" * 70)
print("URLS LE360 DANS LE HTML")
print("=" * 70)

urls = []

matches = re.findall(
    r'https?://[^\s<>"\']+',
    html,
    re.IGNORECASE,
)

for url in matches:

    url = (
        url
        .replace("\\/", "/")
        .replace("&amp;", "&")
    )

    if "le360.ma" not in url.lower():
        continue

    if url not in urls:
        urls.append(url)


print(
    "NOMBRE =",
    len(urls)
)

for url in urls[:30]:
    print(url)


# ============================================================
# LIENS A
# ============================================================

print()
print("=" * 70)
print("LIENS <A> LE360")
print("=" * 70)

soup = BeautifulSoup(
    html,
    "html.parser"
)

count = 0

for a in soup.find_all(
    "a",
    href=True,
):

    href = (
        a.get("href")
        or ""
    ).strip()

    if "le360.ma" not in href.lower():
        continue

    text = a.get_text(
        " ",
        strip=True,
    )

    print()
    print("TEXT =", text[:300])
    print("HREF =", href)

    count += 1

    if count >= 30:
        break


# ============================================================
# RECHERCHE JSON / SCRIPT
# ============================================================

print()
print("=" * 70)
print("URLS LE360 DANS JSON / JAVASCRIPT")
print("=" * 70)

patterns = [
    r'"url"\s*:\s*"([^"]*le360\.ma[^"]*)"',
    r'"link"\s*:\s*"([^"]*le360\.ma[^"]*)"',
    r'"href"\s*:\s*"([^"]*le360\.ma[^"]*)"',
    r'https?://[^"\']*le360\.ma[^"\']*',
]

found = []

for pattern in patterns:

    results = re.findall(
        pattern,
        html,
        re.IGNORECASE,
    )

    for result in results:

        if isinstance(result, tuple):
            result = result[0]

        result = (
            result
            .replace("\\/", "/")
            .replace("\\u002F", "/")
            .replace("&amp;", "&")
        )

        if "le360.ma" not in result.lower():
            continue

        if result not in found:
            found.append(result)


print(
    "NOMBRE =",
    len(found)
)

for url in found[:30]:
    print(url)


print()
print("=" * 70)
print("FIN DU TEST")
print("=" * 70)