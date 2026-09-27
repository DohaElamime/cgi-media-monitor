# ============================================================
# DIAGNOSTIC EXTRACTION V1
# CGI Media Monitor
# ============================================================
#
# OBJECTIF :
# Diagnostiquer automatiquement les URLs qui échouent
# pendant l'extraction des articles.
#
# IMPORTANT :
# - AUCUNE modification SQLite
# - AUCUNE classification sentiment
# - AUCUNE écriture dans la base de données
# - Génère uniquement extraction_diagnostics.csv
#
# ============================================================

import csv
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

try:
    import trafilatura
except ImportError:
    trafilatura = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from googlenewsdecoder import gnewsdecoder
except ImportError:
    gnewsdecoder = None


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

ERROR_FILE = BASE_DIR / "dryrun_errors.csv"
OUTPUT_FILE = BASE_DIR / "extraction_diagnostics.csv"

TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}


# ============================================================
# FALLBACK : URLs des 13 erreurs
# ============================================================

FALLBACK_ERRORS = [
    {
        "id": "",
        "title": "Bannière Corporate CGI | cgi",
        "url": "https://instit.cgi.ma/fr",
        "error_type": "non_article",
    },
    {
        "id": "",
        "title": "La CGI Promoteur de qualité de vie | cgi",
        "url": "https://instit.cgi.ma/fr/landing/la-cgi-promoteur-de-qualite-de-vie",
        "error_type": "extraction_empty",
    },
    {
        "id": "",
        "title": "La CGI | CGI",
        "url": "https://www.cgi.ma/fr/landing/les-cgi",
        "error_type": "extraction_empty",
    },
    {
        "id": "",
        "title": "Mot du Directeur Général | cgi",
        "url": "https://instit.cgi.ma/fr/landing/mot-du-directeur-general",
        "error_type": "extraction_empty",
    },
    {
        "id": "",
        "title": (
            "Spoliation des biens: La digitalisation en attendant "
            "une vraie réforme"
        ),
        "url": (
            "https://www.leconomiste.com/article/"
            "1029248-spoliation-des-biens-la-digitalisation-"
            "en-attendant-une-vraie-reforme"
        ),
        "error_type": "extraction_empty",
    },
    {
        "id": "",
        "title": "Immobilier: Le marché en tendance haussière - L'Economiste",
        "url": (
            "https://www.leconomiste.com/"
            "immobilier-le-marche-en-tendance-haussiere/"
        ),
        "error_type": "extraction_empty",
    },
    {
        "id": "",
        "title": (
            "Impôt: Ce que contient ce redoutable article 213 - "
            "L'Economiste"
        ),
        "url": (
            "https://www.leconomiste.com/article/"
            "1005661-impot-ce-que-contient-ce-redoutable-article-213"
        ),
        "error_type": "extraction_empty",
    },
    {
        "id": "",
        "title": (
            "Abderrahmane Ifrassen chargé de la supervision des "
            "activités urbanisme de CDG Développement"
        ),
        "url": (
            "https://www.challenge.ma/"
            "abderrahmane-ifrassen-charge-de-la-supervision-"
            "des-activites-urbanisme-de-cdg-developpement-301056/"
        ),
        "error_type": "extraction_empty",
    },
    {
        "id": "",
        "title": "COMMUNIQUÉ DE PRESSE - boursenews.ma",
        "url": (
            "https://boursenews.ma/uploads/NewFolder/"
            "CP+Alliances.pdf"
        ),
        "error_type": "extraction_empty",
    },
    {
        "id": "",
        "title": (
            "Fès. L’UEMF se mobilise pour l’insertion professionnelle "
            "des jeunes"
        ),
        "url": (
            "https://leseco.ma/business/"
            "fes-luemf-se-mobilise-pour-linsertion-"
            "professionnelle-des-jeunes.html"
        ),
        "error_type": "extraction_empty",
    },
    {
        "id": "",
        "title": (
            "Élu Service Client de l’Année Maroc : "
            "CGI doublement récompensée - vidéo"
        ),
        "url": (
            "https://leseco.ma/business/"
            "elu-service-client-de-lannee-maroc-cgi-"
            "doublement-recompensee-video.html"
        ),
        "error_type": "extraction_empty",
    },
    {
        "id": "",
        "title": (
            "Abdallah Chatila devient actionnaire unique "
            "de CGI Immobilier - Agefi.com"
        ),
        "url": (
            "https://news.google.com/rss/articles/"
            "example-agefi-1"
        ),
        "error_type": "extraction_empty",
    },
    {
        "id": "",
        "title": (
            "CGI opère un virage stratégique d’envergure "
            "et devient M3 - Agefi.com"
        ),
        "url": (
            "https://news.google.com/rss/articles/"
            "example-agefi-2"
        ),
        "error_type": "extraction_empty",
    },
    {
        "id": "",
        "title": (
            "Deux nouveaux directeurs chez M3 Real Estate - Agefi.com"
        ),
        "url": (
            "https://news.google.com/rss/articles/"
            "example-agefi-3"
        ),
        "error_type": "extraction_empty",
    },
]


# ============================================================
# UTILITAIRES
# ============================================================

def safe_int(value):
    try:
        return int(value)
    except Exception:
        return 0


def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n+", "\n", text)

    return text.strip()


def hostname(url):
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def is_pdf_url(url, content_type=""):
    url_lower = url.lower()

    if ".pdf" in url_lower:
        return True

    if "application/pdf" in content_type.lower():
        return True

    return False


def looks_blocked(text, status_code, content_type):
    text_lower = (text or "").lower()

    block_words = [
        "cloudflare",
        "just a moment",
        "checking your browser",
        "verify you are human",
        "access denied",
        "forbidden",
        "captcha",
        "attention required",
        "enable javascript",
        "security check",
        "bot detection",
        "akamai",
    ]

    for word in block_words:
        if word in text_lower:
            return True, word

    if status_code in (401, 403, 429, 503):
        return True, f"http_{status_code}"

    return False, ""


# ============================================================
# GOOGLE NEWS
# ============================================================

def resolve_google_news(url):
    """
    Résout une URL Google News vers l'article original.
    """

    if not url:
        return url, "empty"

    if "news.google.com" not in url:
        return url, "not_google_news"

    if gnewsdecoder is None:
        return url, "decoder_not_installed"

    try:
        result = gnewsdecoder(url)

        if isinstance(result, dict):
            if result.get("success"):
                decoded = result.get("decoded_url")

                if decoded:
                    return decoded, "decoded"

        return url, "decoder_failed"

    except Exception as e:
        return url, f"decoder_error:{type(e).__name__}"


# ============================================================
# DOWNLOAD
# ============================================================

def download(url):
    start = time.time()

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        elapsed = round(time.time() - start, 2)

        content_type = response.headers.get(
            "Content-Type",
            ""
        )

        return {
            "success": True,
            "status": response.status_code,
            "final_url": response.url,
            "content_type": content_type,
            "bytes": len(response.content),
            "html": response.text
            if not is_pdf_url(response.url, content_type)
            else "",
            "content": response.content,
            "elapsed": elapsed,
            "error": "",
        }

    except Exception as e:

        elapsed = round(time.time() - start, 2)

        return {
            "success": False,
            "status": 0,
            "final_url": url,
            "content_type": "",
            "bytes": 0,
            "html": "",
            "content": b"",
            "elapsed": elapsed,
            "error": f"{type(e).__name__}: {e}",
        }


# ============================================================
# TRAFILATURA
# ============================================================

def test_trafilatura(html):
    if not html:
        return 0, ""

    if trafilatura is None:
        return 0, "trafilatura_not_installed"

    try:

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_links=False,
            favor_precision=True,
        )

        text = clean_text(text or "")

        return len(text), ""

    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


# ============================================================
# BEAUTIFULSOUP
# ============================================================

def test_bs4(html):
    if not html:
        return 0, ""

    try:

        soup = BeautifulSoup(html, "html.parser")

        selectors = [
            "article",
            "[itemprop='articleBody']",
            ".article-content",
            ".article-body",
            ".article__content",
            ".article-text",
            ".td-post-content",
            ".tdb-block-inner",
            ".entry-content",
            ".post-content",
            ".post-body",
            ".content-article",
            ".single-content",
            ".story-content",
            "main article",
            "main",
        ]

        results = []

        for selector in selectors:

            try:
                nodes = soup.select(selector)
            except Exception:
                nodes = []

            for node in nodes:

                text = clean_text(
                    node.get_text(
                        " ",
                        strip=True
                    )
                )

                if text:
                    results.append(
                        (
                            len(text),
                            selector,
                            text
                        )
                    )

        if not results:
            return 0, ""

        results.sort(
            key=lambda x: x[0],
            reverse=True
        )

        best_length, best_selector, _ = results[0]

        return best_length, best_selector

    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


# ============================================================
# META DESCRIPTION
# ============================================================

def test_meta(html):
    if not html:
        return 0

    try:

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        meta = soup.find(
            "meta",
            attrs={
                "name": "description"
            }
        )

        if not meta:
            meta = soup.find(
                "meta",
                attrs={
                    "property": "og:description"
                }
            )

        if not meta:
            return 0

        text = clean_text(
            meta.get("content", "")
        )

        return len(text)

    except Exception:
        return 0


# ============================================================
# CHALLENGE
# ============================================================

def test_challenge(html):
    if not html:
        return 0, ""

    try:

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        selectors = [
            "[itemprop='articleBody']",
            "article",
            ".article-content",
            ".article-body",
            ".article__content",
            ".article-text",
            ".td-post-content",
            ".tdb-block-inner",
            ".entry-content",
            ".post-content",
            ".post-body",
            ".content-article",
            ".single-content",
            ".story-content",
            "main article",
            "main",
        ]

        candidates = []

        for selector in selectors:

            try:
                nodes = soup.select(selector)
            except Exception:
                nodes = []

            for node in nodes:

                text = clean_text(
                    node.get_text(
                        " ",
                        strip=True
                    )
                )

                if len(text) >= 100:

                    candidates.append(
                        (
                            len(text),
                            selector
                        )
                    )

        if not candidates:
            return 0, ""

        candidates.sort(
            reverse=True
        )

        return candidates[0]

    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


# ============================================================
# PDF
# ============================================================

def test_pdf(content):
    if not content:
        return {
            "pdf_signature": False,
            "pdf_pages": 0,
            "pdf_text_length": 0,
            "pdf_error": "",
        }

    signature = content[:5] == b"%PDF-"

    if not signature:
        return {
            "pdf_signature": False,
            "pdf_pages": 0,
            "pdf_text_length": 0,
            "pdf_error": "No %PDF signature",
        }

    if fitz is None:
        return {
            "pdf_signature": True,
            "pdf_pages": 0,
            "pdf_text_length": 0,
            "pdf_error": "PyMuPDF not installed",
        }

    try:

        document = fitz.open(
            stream=content,
            filetype="pdf"
        )

        pages = document.page_count

        total_text = 0

        for page in document:

            text = page.get_text(
                "text"
            )

            total_text += len(
                clean_text(text)
            )

        document.close()

        return {
            "pdf_signature": True,
            "pdf_pages": pages,
            "pdf_text_length": total_text,
            "pdf_error": "",
        }

    except Exception as e:

        return {
            "pdf_signature": True,
            "pdf_pages": 0,
            "pdf_text_length": 0,
            "pdf_error": (
                f"{type(e).__name__}: {e}"
            ),
        }


# ============================================================
# LECTURE DES ERREURS
# ============================================================

def load_errors():

    if ERROR_FILE.exists():

        print(
            f"[INFO] Lecture : {ERROR_FILE}"
        )

        rows = []

        try:

            with open(
                ERROR_FILE,
                "r",
                encoding="utf-8-sig",
                newline=""
            ) as f:

                reader = csv.DictReader(f)

                for row in reader:

                    url = (
                        row.get("url")
                        or row.get("URL")
                        or ""
                    ).strip()

                    if not url:
                        continue

                    rows.append(
                        {
                            "id": (
                                row.get("id")
                                or ""
                            ),
                            "title": (
                                row.get("title")
                                or ""
                            ),
                            "url": url,
                            "error_type": (
                                row.get(
                                    "error_type"
                                )
                                or ""
                            ),
                        }
                    )

            if rows:
                return rows

        except Exception as e:

            print(
                f"[WARN] Impossible de lire "
                f"{ERROR_FILE}: {e}"
            )

    print(
        "[INFO] Utilisation de la liste "
        "de secours."
    )

    return FALLBACK_ERRORS


# ============================================================
# DIAGNOSTIC D'UNE URL
# ============================================================

def diagnose(row, index):

    original_url = row["url"]

    print()
    print("=" * 80)
    print(
        f"[{index}] {row.get('title', '')}"
    )
    print(
        f"URL : {original_url}"
    )

    resolved_url, resolve_status = resolve_google_news(
        original_url
    )

    if resolved_url != original_url:

        print(
            f"[GOOGLE NEWS] Décodé : "
            f"{resolved_url}"
        )

    elif "news.google.com" in original_url:

        print(
            f"[GOOGLE NEWS] Résolution : "
            f"{resolve_status}"
        )

    result = download(
        resolved_url
    )

    diagnostic = {
        "index": index,
        "id": row.get("id", ""),
        "title": row.get("title", ""),
        "original_url": original_url,
        "resolved_url": resolved_url,
        "resolve_status": resolve_status,
        "hostname": hostname(resolved_url),
        "http_status": result["status"],
        "final_url": result["final_url"],
        "content_type": result["content_type"],
        "bytes": result["bytes"],
        "download_seconds": result["elapsed"],
        "download_error": result["error"],
        "blocked": False,
        "block_reason": "",
        "is_pdf": False,
        "pdf_signature": False,
        "pdf_pages": 0,
        "pdf_text_length": 0,
        "pdf_error": "",
        "html_length": len(result["html"]),
        "trafilatura_length": 0,
        "trafilatura_error": "",
        "bs4_length": 0,
        "bs4_selector": "",
        "challenge_length": 0,
        "challenge_selector": "",
        "meta_description_length": 0,
        "diagnosis": "",
    }

    if not result["success"]:

        diagnostic["diagnosis"] = (
            "DOWNLOAD_ERROR"
        )

        print(
            f"[DOWNLOAD ERROR] "
            f"{result['error']}"
        )

        return diagnostic

    print(
        f"HTTP        : "
        f"{result['status']}"
    )

    print(
        f"Final URL   : "
        f"{result['final_url']}"
    )

    print(
        f"Content-Type: "
        f"{result['content_type']}"
    )

    print(
        f"Taille      : "
        f"{result['bytes']} octets"
    )

    # --------------------------------------------------------
    # BLOCK DETECTION
    # --------------------------------------------------------

    sample_text = result["html"][:50000]

    blocked, block_reason = looks_blocked(
        sample_text,
        result["status"],
        result["content_type"]
    )

    diagnostic["blocked"] = blocked
    diagnostic["block_reason"] = block_reason

    if blocked:

        print(
            f"[BLOCK] Oui -> "
            f"{block_reason}"
        )

    else:

        print(
            "[BLOCK] Non détecté"
        )

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    pdf = is_pdf_url(
        result["final_url"],
        result["content_type"]
    )

    diagnostic["is_pdf"] = pdf

    if pdf:

        print(
            "\n[PDF] Analyse..."
        )

        pdf_info = test_pdf(
            result["content"]
        )

        diagnostic.update(
            pdf_info
        )

        print(
            f"Signature %PDF : "
            f"{pdf_info['pdf_signature']}"
        )

        print(
            f"Pages          : "
            f"{pdf_info['pdf_pages']}"
        )

        print(
            f"Texte PDF      : "
            f"{pdf_info['pdf_text_length']} caractères"
        )

        if pdf_info["pdf_error"]:

            print(
                f"Erreur PDF     : "
                f"{pdf_info['pdf_error']}"
            )

        if pdf_info["pdf_text_length"] > 200:

            diagnostic["diagnosis"] = (
                "PDF_OK"
            )

        elif pdf_info["pdf_signature"]:

            diagnostic["diagnosis"] = (
                "PDF_NO_TEXT_OR_CORRUPTED"
            )

        else:

            diagnostic["diagnosis"] = (
                "NOT_REAL_PDF"
            )

        return diagnostic

    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------

    html = result["html"]

    print(
        f"\nHTML length : "
        f"{len(html)}"
    )

    # --------------------------------------------------------
    # TRAFILATURA
    # --------------------------------------------------------

    trafilatura_length, trafilatura_error = (
        test_trafilatura(html)
    )

    diagnostic["trafilatura_length"] = (
        trafilatura_length
    )

    diagnostic["trafilatura_error"] = (
        trafilatura_error
    )

    print(
        f"Trafilatura : "
        f"{trafilatura_length} caractères"
    )

    if trafilatura_error:

        print(
            f"Trafilatura error : "
            f"{trafilatura_error}"
        )

    # --------------------------------------------------------
    # BS4
    # --------------------------------------------------------

    bs4_length, bs4_selector = test_bs4(
        html
    )

    diagnostic["bs4_length"] = bs4_length
    diagnostic["bs4_selector"] = bs4_selector

    print(
        f"BS4         : "
        f"{bs4_length} caractères"
    )

    print(
        f"BS4 selector: "
        f"{bs4_selector}"
    )

    # --------------------------------------------------------
    # CHALLENGE
    # --------------------------------------------------------

    if "challenge.ma" in hostname(
        result["final_url"]
    ):

        challenge_length, challenge_selector = (
            test_challenge(html)
        )

        diagnostic["challenge_length"] = (
            challenge_length
        )

        diagnostic["challenge_selector"] = (
            challenge_selector
        )

        print(
            f"Challenge   : "
            f"{challenge_length} caractères"
        )

        print(
            f"Challenge selector: "
            f"{challenge_selector}"
        )

    # --------------------------------------------------------
    # META
    # --------------------------------------------------------

    meta_length = test_meta(
        html
    )

    diagnostic[
        "meta_description_length"
    ] = meta_length

    print(
        f"Meta desc   : "
        f"{meta_length} caractères"
    )

    # --------------------------------------------------------
    # DIAGNOSIS
    # --------------------------------------------------------

    if blocked:

        diagnostic["diagnosis"] = (
            "BLOCKED_OR_ANTI_BOT"
        )

    elif result["status"] >= 400:

        diagnostic["diagnosis"] = (
            f"HTTP_ERROR_{result['status']}"
        )

    elif (
        trafilatura_length >= 500
        or bs4_length >= 500
        or diagnostic["challenge_length"] >= 500
    ):

        diagnostic["diagnosis"] = (
            "CONTENT_AVAILABLE_BUT_CURRENT_EXTRACTOR_FAILED"
        )

    elif meta_length >= 100:

        diagnostic["diagnosis"] = (
            "ONLY_META_CONTENT_AVAILABLE"
        )

    elif len(html) < 1000:

        diagnostic["diagnosis"] = (
            "VERY_SMALL_HTML"
        )

    elif len(html) >= 1000:

        diagnostic["diagnosis"] = (
            "HTML_PRESENT_BUT_NO_ARTICLE_TEXT"
        )

    else:

        diagnostic["diagnosis"] = (
            "UNKNOWN"
        )

    print(
        f"\nDIAGNOSTIC : "
        f"{diagnostic['diagnosis']}"
    )

    return diagnostic


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 80)
    print(" CGI MEDIA MONITOR - DIAGNOSTIC EXTRACTION V1")
    print("=" * 80)
    print()
    print("SQLite : AUCUNE MODIFICATION")
    print(
        f"Output : {OUTPUT_FILE}"
    )
    print()

    rows = load_errors()

    print(
        f"[INFO] URLs à diagnostiquer : "
        f"{len(rows)}"
    )

    results = []

    for index, row in enumerate(
        rows,
        start=1
    ):

        try:

            result = diagnose(
                row,
                index
            )

            results.append(
                result
            )

        except KeyboardInterrupt:

            print(
                "\n[STOP] Interruption utilisateur."
            )

            break

        except Exception as e:

            print(
                f"[ERROR] "
                f"{type(e).__name__}: {e}"
            )

            results.append(
                {
                    "index": index,
                    "id": row.get("id", ""),
                    "title": row.get("title", ""),
                    "original_url": row.get(
                        "url",
                        ""
                    ),
                    "resolved_url": "",
                    "resolve_status": "",
                    "hostname": "",
                    "http_status": 0,
                    "final_url": "",
                    "content_type": "",
                    "bytes": 0,
                    "download_seconds": 0,
                    "download_error": (
                        f"{type(e).__name__}: {e}"
                    ),
                    "blocked": False,
                    "block_reason": "",
                    "is_pdf": False,
                    "pdf_signature": False,
                    "pdf_pages": 0,
                    "pdf_text_length": 0,
                    "pdf_error": "",
                    "html_length": 0,
                    "trafilatura_length": 0,
                    "trafilatura_error": "",
                    "bs4_length": 0,
                    "bs4_selector": "",
                    "challenge_length": 0,
                    "challenge_selector": "",
                    "meta_description_length": 0,
                    "diagnosis": "SCRIPT_ERROR",
                }
            )

        time.sleep(0.5)

    # ========================================================
    # CSV
    # ========================================================

    if results:

        fieldnames = list(
            results[0].keys()
        )

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8-sig",
            newline=""
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames
            )

            writer.writeheader()
            writer.writerows(results)

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 80)
    print(" FIN DU DIAGNOSTIC")
    print("=" * 80)

    print(
        f"\nRésultats : "
        f"{len(results)}"
    )

    diagnosis_counts = {}

    for result in results:

        diagnosis = result.get(
            "diagnosis",
            "UNKNOWN"
        )

        diagnosis_counts[
            diagnosis
        ] = (
            diagnosis_counts.get(
                diagnosis,
                0
            ) + 1
        )

    print(
        "\n--- DIAGNOSTICS ---"
    )

    for diagnosis, count in sorted(
        diagnosis_counts.items()
    ):

        print(
            f"{diagnosis:<55} : {count}"
        )

    print()
    print(
        f"📄 Diagnostic CSV : "
        f"{OUTPUT_FILE}"
    )

    print()
    print(
        "⚠️ SQLITE : AUCUNE MODIFICATION"
    )

    print()


if __name__ == "__main__":
    main()