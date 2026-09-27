"""
Google News V7
--------------
Pipeline d'extraction uniquement.

Flux :
Google News RSS URL
        ↓
googlenewsdecoder
        ↓
URL réelle du média
        ↓
requests
        ↓
Trafilatura
        ↓
JSON-LD / HTML fallback
        ↓
contenu exploitable ou erreur

IMPORTANT :
- Aucun appel GPT-OSS
- Aucun sentiment
- Aucun SQLite
- Aucune modification de la base
- Lecture seule de google_news_v2_results.csv
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import pandas as pd
import requests
import trafilatura
from bs4 import BeautifulSoup

try:
    from googlenewsdecoder import gnewsdecoder
except ImportError:
    raise SystemExit(
        "\n[ERREUR] googlenewsdecoder n'est pas installé.\n"
        "Installe-le avec :\n"
        "    pip install -U googlenewsdecoder\n"
    )


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "google_news_v2_results.csv"
OUTPUT_FILE = BASE_DIR / "google_news_v7_results.csv"
ERROR_FILE = BASE_DIR / "google_news_v7_errors.csv"

REQUEST_TIMEOUT = 25
DECODER_TIMEOUT = 20

# Petite pause pour éviter de marteler Google News / les médias
DECODER_INTERVAL = 0.5
REQUEST_DELAY = 0.25

MIN_CONTENT_CHARS = 500
MIN_CONTENT_WORDS = 80

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/153.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.7,en;q=0.5",
    "Cache-Control": "no-cache",
}


# ============================================================
# UTILITAIRES
# ============================================================

def clean_text(text: Any) -> str:
    """Nettoie un texte HTML / extrait."""
    if text is None:
        return ""

    text = str(text)

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n+", "\n", text)

    return text.strip()


def word_count(text: str) -> int:
    if not text:
        return 0

    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


def is_google_news_url(url: str) -> bool:
    """Détermine si l'URL est une URL Google News."""
    if not url:
        return False

    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()

        return (
            "news.google.com" in host
            and (
                "/rss/articles/" in parsed.path
                or "/articles/" in parsed.path
                or "/read/" in parsed.path
            )
        )

    except Exception:
        return False


def is_valid_article_url(url: str) -> bool:
    """Vérifie qu'une URL semble être une vraie URL média."""
    if not url:
        return False

    url = url.strip()

    if not url.startswith(("http://", "https://")):
        return False

    if "news.google.com" in url.lower():
        return False

    parsed = urlparse(url)

    if not parsed.netloc:
        return False

    return True


# ============================================================
# 1. RESOLUTION GOOGLE NEWS
# ============================================================

def resolve_google_news_url(
    google_url: str,
) -> tuple[Optional[str], str]:
    """
    Résout une URL Google News avec googlenewsdecoder.

    Retourne :
        (url_finale, méthode)
    """

    if not google_url:
        return None, "EMPTY_URL"

    if not is_google_news_url(google_url):
        if is_valid_article_url(google_url):
            return google_url, "DIRECT_URL"

        return None, "INVALID_URL"

    try:
        print("      [DECODER] Résolution Google News...")

        result = gnewsdecoder(
            google_url,
            interval=DECODER_INTERVAL,
            timeout=DECODER_TIMEOUT,
        )

        if result is None:
            return None, "DECODER_EMPTY"

        # ----------------------------------------------------
        # Format récent :
        # {
        #   "success": True,
        #   "decoded_url": "https://..."
        # }
        # ----------------------------------------------------

        if isinstance(result, dict):

            success = result.get("success")

            if success is True:
                decoded_url = result.get("decoded_url")

                if is_valid_article_url(decoded_url):
                    return decoded_url.strip(), "GNEWSDECODER"

                return None, "DECODER_INVALID_URL"

            # ------------------------------------------------
            # Ancien format :
            # {
            #   "status": True,
            #   "decoded_url": "..."
            # }
            # ------------------------------------------------

            status = result.get("status")

            if status is True:
                decoded_url = result.get("decoded_url")

                if is_valid_article_url(decoded_url):
                    return decoded_url.strip(), "GNEWSDECODER"

                return None, "DECODER_INVALID_URL"

            message = result.get("message", "unknown decoder error")

            return None, f"DECODER_FAILED: {message}"

        # ----------------------------------------------------
        # Certains anciens formats peuvent retourner
        # directement une string.
        # ----------------------------------------------------

        if isinstance(result, str):

            decoded_url = result.strip()

            if is_valid_article_url(decoded_url):
                return decoded_url, "GNEWSDECODER_STRING"

            return None, "DECODER_STRING_INVALID"

        return None, "DECODER_UNKNOWN_FORMAT"

    except Exception as exc:

        return None, f"DECODER_EXCEPTION: {type(exc).__name__}: {exc}"


# ============================================================
# 2. DOWNLOAD PAGE
# ============================================================

def download_page(url: str) -> tuple[Optional[str], int, str]:
    """
    Télécharge la page média.

    Retour :
        html, status_code, error
    """

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        status_code = response.status_code

        final_url = response.url

        # Certains sites redirigent vers une page générique.
        if status_code != 200:

            return (
                None,
                status_code,
                f"HTTP_{status_code}",
            )

        html = response.text

        if not html or len(html.strip()) < 1000:

            return (
                None,
                status_code,
                "HTML_TOO_SHORT",
            )

        return (
            html,
            status_code,
            "",
        )

    except requests.Timeout:

        return (
            None,
            0,
            "REQUEST_TIMEOUT",
        )

    except requests.RequestException as exc:

        return (
            None,
            0,
            f"REQUEST_ERROR: {type(exc).__name__}: {exc}",
        )

    except Exception as exc:

        return (
            None,
            0,
            f"DOWNLOAD_EXCEPTION: {type(exc).__name__}: {exc}",
        )


# ============================================================
# 3. TRAFILATURA
# ============================================================

def extract_with_trafilatura(
    html: str,
    url: str,
) -> str:
    """Extraction principale avec Trafilatura."""

    if not html:
        return ""

    try:

        extracted = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            include_links=False,
            include_images=False,
            favor_precision=True,
            deduplicate=True,
            output_format="txt",
        )

        return clean_text(extracted)

    except Exception:

        return ""


# ============================================================
# 4. JSON-LD
# ============================================================

def extract_jsonld_article(html: str) -> str:
    """
    Cherche :
      articleBody
      description
      headline

    dans les JSON-LD.
    """

    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    scripts = soup.find_all(
        "script",
        attrs={"type": "application/ld+json"},
    )

    candidates: list[str] = []

    def inspect_json(data: Any) -> None:

        if isinstance(data, dict):

            # articleBody est le plus intéressant.
            article_body = data.get("articleBody")

            if isinstance(article_body, str):
                candidates.append(article_body)

            description = data.get("description")

            if isinstance(description, str):
                candidates.append(description)

            # @graph
            graph = data.get("@graph")

            if isinstance(graph, list):
                for item in graph:
                    inspect_json(item)

        elif isinstance(data, list):

            for item in data:
                inspect_json(item)

    for script in scripts:

        raw = script.string or script.get_text()

        if not raw:
            continue

        raw = raw.strip()

        try:

            data = json.loads(raw)

            inspect_json(data)

        except Exception:

            continue

    if not candidates:
        return ""

    # On préfère articleBody au contenu court.
    candidates.sort(
        key=lambda x: word_count(x),
        reverse=True,
    )

    best = clean_text(candidates[0])

    return best


# ============================================================
# 5. HTML FALLBACK
# ============================================================

def extract_html_fallback(html: str) -> str:
    """
    Fallback HTML :
      1. <article>
      2. blocs contenant beaucoup de paragraphes
      3. <p>
    """

    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Nettoyage
    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "nav",
            "footer",
            "header",
            "form",
            "aside",
        ]
    ):
        tag.decompose()

    # --------------------------------------------------------
    # Priorité 1 : article
    # --------------------------------------------------------

    article = soup.find("article")

    if article:

        paragraphs = article.find_all("p")

        texts = [
            clean_text(p.get_text(" ", strip=True))
            for p in paragraphs
        ]

        texts = [
            text
            for text in texts
            if word_count(text) >= 5
        ]

        content = clean_text(" ".join(texts))

        if word_count(content) >= MIN_CONTENT_WORDS:
            return content

    # --------------------------------------------------------
    # Priorité 2 : tous les paragraphes
    # --------------------------------------------------------

    paragraphs = soup.find_all("p")

    texts = []

    for p in paragraphs:

        text = clean_text(
            p.get_text(" ", strip=True)
        )

        if word_count(text) < 5:
            continue

        # Évite les textes minuscules / menus.
        if len(text) < 30:
            continue

        texts.append(text)

    content = clean_text(" ".join(texts))

    if word_count(content) >= MIN_CONTENT_WORDS:
        return content

    return ""


# ============================================================
# 6. META DESCRIPTION
# ============================================================

def extract_meta_description(html: str) -> str:

    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    candidates = []

    # description standard
    meta = soup.find(
        "meta",
        attrs={"name": re.compile("^description$", re.I)},
    )

    if meta and meta.get("content"):
        candidates.append(meta["content"])

    # og:description
    meta = soup.find(
        "meta",
        attrs={"property": "og:description"},
    )

    if meta and meta.get("content"):
        candidates.append(meta["content"])

    candidates = [
        clean_text(x)
        for x in candidates
        if x
    ]

    if not candidates:
        return ""

    return max(
        candidates,
        key=word_count,
    )


# ============================================================
# 7. EXTRACTION COMPLETE
# ============================================================

def extract_article_content(
    html: str,
    url: str,
) -> tuple[str, str]:
    """
    Essaie plusieurs méthodes.

    Retour :
        content, extraction_method
    """

    # --------------------------------------------------------
    # 1. Trafilatura
    # --------------------------------------------------------

    content = extract_with_trafilatura(
        html,
        url,
    )

    if (
        len(content) >= MIN_CONTENT_CHARS
        and word_count(content) >= MIN_CONTENT_WORDS
    ):

        return content, "TRAFILATURA"

    # --------------------------------------------------------
    # 2. JSON-LD
    # --------------------------------------------------------

    jsonld = extract_jsonld_article(html)

    if (
        len(jsonld) >= MIN_CONTENT_CHARS
        and word_count(jsonld) >= MIN_CONTENT_WORDS
    ):

        return jsonld, "JSON_LD"

    # --------------------------------------------------------
    # 3. HTML
    # --------------------------------------------------------

    html_content = extract_html_fallback(html)

    if (
        len(html_content) >= MIN_CONTENT_CHARS
        and word_count(html_content) >= MIN_CONTENT_WORDS
    ):

        return html_content, "HTML_FALLBACK"

    # --------------------------------------------------------
    # 4. Meta description
    # --------------------------------------------------------

    meta = extract_meta_description(html)

    if meta:

        return meta, "META_DESCRIPTION"

    return "", "EMPTY"


# ============================================================
# 8. TRAITEMENT D'UN ARTICLE
# ============================================================

def process_article(
    row: pd.Series,
    index: int,
    total: int,
) -> dict[str, Any]:

    google_url = str(
        row.get("url", "") or ""
    ).strip()

    title = clean_text(
        row.get("title", "")
    )

    source = clean_text(
        row.get("source", "")
    )

    date = row.get("date", "")

    print()
    print("=" * 80)
    print(
        f"[{index}/{total}] {title[:100]}"
    )
    print(
        f"      Source : {source}"
    )

    result = {
        "title": title,
        "source": source,
        "date": date,
        "google_news_url": google_url,
        "resolved_url": "",
        "resolver_method": "",
        "http_status": "",
        "final_http_url": "",
        "content": "",
        "content_chars": 0,
        "content_words": 0,
        "extraction_method": "",
        "extraction_status": "",
        "error": "",
    }

    # --------------------------------------------------------
    # Résolution URL
    # --------------------------------------------------------

    resolved_url, resolver_method = (
        resolve_google_news_url(
            google_url
        )
    )

    result["resolved_url"] = (
        resolved_url or ""
    )

    result["resolver_method"] = (
        resolver_method
    )

    if not resolved_url:

        result["extraction_status"] = (
            "RESOLUTION_FAILED"
        )

        result["error"] = resolver_method

        print(
            f"      [FAIL] {resolver_method}"
        )

        return result

    print(
        f"      [OK] URL : {resolved_url}"
    )

    # --------------------------------------------------------
    # Téléchargement
    # --------------------------------------------------------

    html, status_code, download_error = (
        download_page(
            resolved_url
        )
    )

    result["http_status"] = status_code

    if html:

        result["final_http_url"] = (
            resolved_url
        )

    if not html:

        result["extraction_status"] = (
            "DOWNLOAD_FAILED"
        )

        result["error"] = (
            download_error
        )

        print(
            f"      [FAIL] {download_error}"
        )

        return result

    print(
        f"      [HTTP {status_code}] "
        f"HTML={len(html):,} chars"
    )

    # --------------------------------------------------------
    # Extraction
    # --------------------------------------------------------

    content, extraction_method = (
        extract_article_content(
            html,
            resolved_url,
        )
    )

    content = clean_text(content)

    result["content"] = content
    result["content_chars"] = len(content)
    result["content_words"] = word_count(
        content
    )
    result["extraction_method"] = (
        extraction_method
    )

    if (
        len(content) >= MIN_CONTENT_CHARS
        and word_count(content) >= MIN_CONTENT_WORDS
    ):

        result["extraction_status"] = (
            "FULL_CONTENT"
        )

        print(
            f"      [OK] {extraction_method} "
            f"→ {len(content):,} chars / "
            f"{word_count(content):,} mots"
        )

    elif extraction_method == "META_DESCRIPTION":

        result["extraction_status"] = (
            "SUMMARY_ONLY"
        )

        print(
            f"      [SUMMARY] Meta description "
            f"→ {len(content):,} chars"
        )

    else:

        result["extraction_status"] = (
            "EXTRACTION_EMPTY"
        )

        result["error"] = (
            "No usable article content"
        )

        print(
            "      [EMPTY] Aucun contenu "
            "article exploitable"
        )

    return result


# ============================================================
# 9. MAIN
# ============================================================

def main():

    print()
    print("=" * 80)
    print("GOOGLE NEWS V7 — EXTRACTION DRY-RUN")
    print("=" * 80)

    print(
        f"\n[INPUT] {INPUT_FILE}"
    )

    if not INPUT_FILE.exists():

        raise SystemExit(
            f"\n[ERREUR] Fichier introuvable :\n"
            f"{INPUT_FILE}\n"
        )

    # --------------------------------------------------------
    # Lecture CSV
    # --------------------------------------------------------

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig",
    )

    print(
        f"[OK] {len(df)} lignes chargées"
    )

    # --------------------------------------------------------
    # Filtre pertinence
    # --------------------------------------------------------

    if "relevant" in df.columns:

        relevant_values = (
            df["relevant"]
            .astype(str)
            .str.lower()
            .str.strip()
        )

        relevant_mask = relevant_values.isin(
            [
                "true",
                "1",
                "yes",
                "oui",
            ]
        )

        work_df = df[relevant_mask].copy()

    else:

        print(
            "[WARNING] Colonne 'relevant' "
            "absente → traitement de toutes les lignes"
        )

        work_df = df.copy()

    print(
        f"[INFO] Articles pertinents : "
        f"{len(work_df)}"
    )

    # --------------------------------------------------------
    # Vérification colonne URL
    # --------------------------------------------------------

    if "url" not in work_df.columns:

        raise SystemExit(
            "\n[ERREUR] La colonne 'url' "
            "est absente du CSV.\n"
        )

    # --------------------------------------------------------
    # Traitement
    # --------------------------------------------------------

    results = []

    start_time = time.time()

    total = len(work_df)

    for position, (_, row) in enumerate(
        work_df.iterrows(),
        start=1,
    ):

        try:

            result = process_article(
                row,
                position,
                total,
            )

        except KeyboardInterrupt:

            print(
                "\n[STOP] Interruption utilisateur."
            )

            break

        except Exception as exc:

            result = {
                "title": clean_text(
                    row.get("title", "")
                ),
                "source": clean_text(
                    row.get("source", "")
                ),
                "date": row.get("date", ""),
                "google_news_url": str(
                    row.get("url", "")
                ),
                "resolved_url": "",
                "resolver_method": "",
                "http_status": "",
                "final_http_url": "",
                "content": "",
                "content_chars": 0,
                "content_words": 0,
                "extraction_method": "",
                "extraction_status": "ERROR",
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
            }

            print(
                f"      [ERROR] "
                f"{type(exc).__name__}: {exc}"
            )

        results.append(result)

        time.sleep(REQUEST_DELAY)

    # --------------------------------------------------------
    # DataFrame
    # --------------------------------------------------------

    result_df = pd.DataFrame(results)

    # --------------------------------------------------------
    # Statistiques
    # --------------------------------------------------------

    elapsed = time.time() - start_time

    full_content = (
        result_df[
            "extraction_status"
        ]
        == "FULL_CONTENT"
    ).sum()

    summary_only = (
        result_df[
            "extraction_status"
        ]
        == "SUMMARY_ONLY"
    ).sum()

    empty = (
        result_df[
            "extraction_status"
        ]
        == "EXTRACTION_EMPTY"
    ).sum()

    resolution_failed = (
        result_df[
            "extraction_status"
        ]
        == "RESOLUTION_FAILED"
    ).sum()

    download_failed = (
        result_df[
            "extraction_status"
        ]
        == "DOWNLOAD_FAILED"
    ).sum()

    errors = (
        result_df[
            "extraction_status"
        ]
        == "ERROR"
    ).sum()

    resolved = (
        result_df["resolved_url"]
        .astype(str)
        .str.len()
        .gt(0)
        .sum()
    )

    # --------------------------------------------------------
    # Sauvegarde
    # --------------------------------------------------------

    result_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Fichier erreurs
    # --------------------------------------------------------

    error_mask = (
        result_df["extraction_status"]
        .isin(
            [
                "RESOLUTION_FAILED",
                "DOWNLOAD_FAILED",
                "EXTRACTION_EMPTY",
                "ERROR",
            ]
        )
    )

    error_df = result_df[
        error_mask
    ].copy()

    error_df.to_csv(
        ERROR_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Résultats
    # --------------------------------------------------------

    success_rate = (
        full_content / total * 100
        if total
        else 0
    )

    resolution_rate = (
        resolved / total * 100
        if total
        else 0
    )

    print()
    print("=" * 80)
    print("DIAGNOSTIC V7 TERMINÉ")
    print("=" * 80)

    print()
    print(
        f"Articles CSV             : {len(df)}"
    )

    print(
        f"Articles pertinents      : {total}"
    )

    print()
    print("RÉSOLUTION GOOGLE NEWS")
    print(
        f"URLs résolues            : {resolved}"
    )
    print(
        f"URLs non résolues        : "
        f"{total - resolved}"
    )
    print(
        f"Taux résolution          : "
        f"{resolution_rate:.2f}%"
    )

    print()
    print("EXTRACTION")

    print(
        f"Contenu complet          : "
        f"{full_content}"
    )

    print(
        f"Résumé seulement         : "
        f"{summary_only}"
    )

    print(
        f"Extraction vide          : "
        f"{empty}"
    )

    print(
        f"Échec résolution         : "
        f"{resolution_failed}"
    )

    print(
        f"Échec téléchargement     : "
        f"{download_failed}"
    )

    print(
        f"Erreurs techniques       : "
        f"{errors}"
    )

    print()
    print(
        f"Taux contenu complet     : "
        f"{success_rate:.2f}%"
    )

    print()
    print("MÉTHODES D'EXTRACTION")

    if not result_df.empty:

        method_counts = (
            result_df[
                "extraction_method"
            ]
            .fillna("")
            .replace("", "NONE")
            .value_counts()
        )

        for method, count in (
            method_counts.items()
        ):

            print(
                f"  {method:<25} : {count}"
            )

    print()
    print(
        f"Durée totale             : "
        f"{elapsed:.1f} sec"
    )

    if total:

        print(
            f"Temps moyen/article      : "
            f"{elapsed / total:.2f} sec"
        )

    print()
    print(
        f"Résultats : {OUTPUT_FILE}"
    )

    print(
        f"Erreurs   : {ERROR_FILE}"
    )

    print()
    print(
        "SQLite                   : "
        "AUCUNE MODIFICATION"
    )

    print(
        "GPT-OSS                  : "
        "NON UTILISÉ"
    )

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()