# ============================================================
# CGI MEDIA MONITOR
# DRY-RUN + CSV
#
# IMPORTANT :
# - Aucune modification SQLite
# - Aucun save_article()
# - Aucun UPDATE / INSERT / DELETE SQLite
# - Analyse sémantique avec GPT-OSS 120B Cloud
# ============================================================

import csv
from datetime import datetime
from urllib.parse import urlparse

from modules.aggregator import collect_articles
from modules.article_extractor import extract_article
from modules.ai_classifier import is_relevant_ai
from modules.pre_filter import is_article_candidate
from modules.sentiment_analysis import analyze_cgi_sentiment


# ============================================================
# CONFIGURATION
# ============================================================

OUTPUT_CSV = "dryrun_sentiment_results.csv"

ERROR_CSV = "dryrun_errors.csv"


# ============================================================
# UTILITAIRES
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    return str(value).strip()


# Résumé générique de Google Actualités : ce texte ne contient
# aucune information exploitable sur l'article.
GOOGLE_NEWS_GENERIC_SUMMARY = (
    "Informations complètes et à jour, compilées par Google Actualités "
    "à partir de sources d'actualités du monde entier"
)


def is_usable_summary(value):
    value = clean_text(value)

    if not value:
        return False

    normalized = " ".join(value.lower().split())
    generic = " ".join(GOOGLE_NEWS_GENERIC_SUMMARY.lower().split())

    if normalized == generic:
        return False

    if (
        "compilées par google actualités" in normalized
        and "sources d'actualités du monde entier" in normalized
    ):
        return False

    return len(value) >= 50


def safe_bool(value):

    if isinstance(value, bool):
        return value

    if isinstance(value, str):

        return value.lower().strip() in {
            "true",
            "1",
            "yes",
            "oui",
            "vrai",
        }

    return bool(value)


# ============================================================
# DETECTION PAGES NON-ARTICLES
# ============================================================

def is_obvious_non_article(article):

    """
    Rejette uniquement les pages clairement identifiables
    comme pages d'accueil / institutionnelles.

    On ne rejette pas automatiquement les articles courts.
    """

    title = clean_text(
        article.get("title")
    )

    url = clean_text(
        article.get("url")
    )

    if not url:
        return False

    try:

        parsed = urlparse(url)

    except Exception:

        return False

    host = (
        parsed.netloc
        .lower()
        .split(":")[0]
    )

    path = (
        parsed.path
        .rstrip("/")
        .lower()
    )

    # --------------------------------------------------------
    # Site institutionnel CGI
    # --------------------------------------------------------

    if host == "instit.cgi.ma":

        if path in {
            "",
            "/fr",
        }:

            return True

        if (
            "bannière corporate"
            in title.lower()
        ):

            return True

    return False


# ============================================================
# ERREUR NON-ARTICLE
# ============================================================

def add_non_article_error(
    errors_list,
    index,
    article_id,
    title,
    url,
):

    errors_list.append({

        "index": index,

        "id": article_id,

        "title": title,

        "url": url,

        "error_type": "non_article",

        "error": (
            "Page institutionnelle / "
            "page d'accueil non considérée "
            "comme un article."
        ),

        "timestamp": datetime.now().isoformat(),

    })


# ============================================================
# SAUVEGARDE RESULTATS
# ============================================================

def save_results(
    results,
):

    if not results:
        return

    fieldnames = [

        "index",

        "id",

        "title",

        "source",

        "url",

        "summary",

        "content_length",

        "extraction_method",

        "relevant",

        "sentiment",

        "score",

        "confidence",

        "margin",

        "review",

        "content_mismatch",

        "extraction_failed",

        "reason",

        "model",

        "device",

        "timestamp",

    ]

    with open(

        OUTPUT_CSV,

        "w",

        newline="",

        encoding="utf-8-sig",

    ) as f:

        writer = csv.DictWriter(

            f,

            fieldnames=fieldnames,

            extrasaction="ignore",

        )

        writer.writeheader()

        for row in results:

            writer.writerow(
                row
            )


# ============================================================
# SAUVEGARDE ERREURS
# ============================================================

def save_errors(
    errors_list,
):

    if not errors_list:
        return

    fieldnames = [

        "index",

        "id",

        "title",

        "url",

        "error_type",

        "error",

        "timestamp",

    ]

    with open(

        ERROR_CSV,

        "w",

        newline="",

        encoding="utf-8-sig",

    ) as f:

        writer = csv.DictWriter(

            f,

            fieldnames=fieldnames,

            extrasaction="ignore",

        )

        writer.writeheader()

        for row in errors_list:

            writer.writerow(
                row
            )


# ============================================================
# AJOUT RESULTAT REVIEW / ERREUR
# ============================================================

def add_error_result(
    results,
    index,
    article_id,
    title,
    source,
    url,
    summary,
    content_length,
    reason,
    extraction_failed=False,
):

    results.append({

        "index": index,

        "id": article_id,

        "title": title,

        "source": source,

        "url": url,

        "summary": summary,

        "content_length": content_length,

        "extraction_method": "",

        "relevant": False,

        "sentiment": "REVIEW",

        "score": 0.0,

        "confidence": 0.0,

        "margin": 0.0,

        "review": True,

        "content_mismatch": False,

        "extraction_failed": extraction_failed,

        "reason": reason,

        "model": "",

        "device": "",

        "timestamp": datetime.now().isoformat(),

    })


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)

    print(
        "CGI MEDIA MONITOR - DRY RUN + CSV"
    )

    print("=" * 70)

    print()

    print(
        "⚠️ MODE DRY-RUN"
    )

    print(
        "⚠️ AUCUNE MODIFICATION SQLITE"
    )

    print(
        "⚠️ GPT-OSS 120B CLOUD"
    )

    print()

    # ========================================================
    # 1. COLLECTE
    # ========================================================

    try:

        articles = collect_articles()

    except Exception as e:

        print()

        print(
            "❌ ERREUR COLLECTE"
        )

        print(
            str(e)
        )

        return

    if not articles:

        print()

        print(
            "❌ Aucun article récupéré."
        )

        return

    print(
        f"Articles récupérés : {len(articles)}"
    )

    print()

    # ========================================================
    # RESULTATS
    # ========================================================

    results = []

    errors_list = []

    # ========================================================
    # COMPTEURS
    # ========================================================

    relevant_count = 0

    analyzed_count = 0

    prefilter_rejected = 0

    non_article_rejected = 0

    prefilter_errors = 0

    extraction_errors = 0

    relevance_errors = 0

    sentiment_errors = 0

    extraction_review_count = 0

    sentiment_review_count = 0

    mismatch_count = 0

    summary_only_count = 0

    full_content_count = 0

    # ========================================================
    # TRAITEMENT
    # ========================================================

    for index, article in enumerate(

        articles,

        start=1,

    ):

        print()

        print(
            "-" * 70
        )

        print(
            f"[{index}/{len(articles)}]"
        )

        # ====================================================
        # NORMALISATION
        # ====================================================

        article_id = clean_text(
            article.get("id")
        )

        title = clean_text(
            article.get("title")
        )

        summary = clean_text(

            article.get("summary")

            or article.get("description")

        )

        # Ignorer le faux résumé générique de Google Actualités.
        if not is_usable_summary(summary):
            summary = ""

        url = clean_text(
            article.get("url")
        )

        source = clean_text(

            article.get("source")

            or article.get("publisher")

        )

        print(
            f"Titre : {title[:150]}"
        )

        # ====================================================
        # 1. PAGES NON-ARTICLES
        # ====================================================

        if is_obvious_non_article(
            article
        ):

            print(
                "⚪ Page institutionnelle / accueil "
                "→ rejetée"
            )

            non_article_rejected += 1

            add_non_article_error(

                errors_list,

                index,

                article_id,

                title,

                url,

            )

            continue

        # ====================================================
        # 2. PRE-FILTER
        # ====================================================

        try:

            candidate = is_article_candidate(
                article
            )

        except Exception as e:

            print(
                f"❌ Erreur pré-filtre : {e}"
            )

            prefilter_errors += 1

            errors_list.append({

                "index": index,

                "id": article_id,

                "title": title,

                "url": url,

                "error_type": "pre_filter",

                "error": str(e),

                "timestamp": datetime.now().isoformat(),

            })

            add_error_result(

                results,

                index,

                article_id,

                title,

                source,

                url,

                summary,

                0,

                "Erreur lors du pré-filtre.",

            )

            continue

        if not candidate:

            print(
                "⚪ Rejeté par le pré-filtre"
            )

            prefilter_rejected += 1

            continue

        print(
            "🟡 Candidat article"
        )

        # ====================================================
        # 3. EXTRACTION
        # ====================================================

        try:

            extraction_result = extract_article(

                url=url,

                title=title,

                summary=summary,

            )

        except Exception as e:

            print(
                f"❌ Erreur extraction : {e}"
            )

            extraction_errors += 1

            extraction_review_count += 1

            errors_list.append({

                "index": index,

                "id": article_id,

                "title": title,

                "url": url,

                "error_type": "extraction",

                "error": str(e),

                "timestamp": datetime.now().isoformat(),

            })

            add_error_result(

                results,

                index,

                article_id,

                title,

                source,

                url,

                summary,

                0,

                "Erreur pendant l'extraction.",

                extraction_failed=True,

            )

            continue

        # ====================================================
        # COMPATIBILITE
        #
        # Le nouvel extractor retourne un dictionnaire.
        # ====================================================

        if isinstance(
            extraction_result,
            dict,
        ):

            extracted_content = clean_text(

                extraction_result.get(
                    "content",
                    "",
                )

            )

            extracted_summary = clean_text(

                extraction_result.get(
                    "summary",
                    "",
                )

            )

            extracted_title = clean_text(

                extraction_result.get(
                    "title",
                    "",
                )

            )

            try:

                content_length = int(

                    extraction_result.get(

                        "content_length",

                        len(extracted_content),

                    )

                    or 0

                )

            except (TypeError, ValueError):

                content_length = len(extracted_content)

            extraction_failed = safe_bool(

                extraction_result.get(
                    "extraction_failed",
                    False,
                )

            )

            extraction_review = safe_bool(

                extraction_result.get(
                    "review",
                    False,
                )

            )

            extraction_method = clean_text(

                extraction_result.get(
                    "method",
                    "",
                )

            )

            extraction_error = clean_text(

                extraction_result.get(
                    "error",
                    "",
                )

            )

            # Le résumé extrait est prioritaire uniquement
            # s'il contient réellement des informations.
            if is_usable_summary(extracted_summary):

                summary = extracted_summary

            elif not is_usable_summary(summary):

                summary = ""

            if extracted_title:

                title = extracted_title

        else:

            # Compatibilité avec une ancienne version
            # de l'extractor qui retournait directement
            # une chaîne.

            extracted_content = clean_text(
                extraction_result
            )

            content_length = len(
                extracted_content
            )

            extraction_failed = False

            extraction_review = False

            extraction_method = "legacy"

            extraction_error = ""

        # ====================================================
        # AFFICHAGE EXTRACTION
        # ====================================================

        if extracted_content:

            full_content_count += 1

            print(
                f"   Contenu complet : "
                f"{content_length} caractères"
            )

            if extraction_method:

                print(
                    f"   Méthode : "
                    f"{extraction_method}"
                )

        else:

            if summary:

                summary_only_count += 1

                print(
                    "   ⚠️ Contenu complet absent"
                )

                print(
                    "   ✅ Résumé disponible "
                    "→ analyse possible"
                )

            else:

                print(
                    "   ❌ Contenu et résumé absents"
                )

        # ====================================================
        # EXTRACTION REVIEW
        #
        # Un REVIEW d'extraction n'empêche pas l'analyse si un
        # résumé exploitable est disponible.
        # ====================================================

        if extraction_review and not extracted_content and summary:

            print(

                "   ⚠️ Extraction REVIEW mais résumé exploitable "

                "→ analyse sémantique maintenue"

            )

        # ====================================================
        # SI EXTRACTION EN ÉCHEC ET AUCUN RESUME UTILISABLE
        # ====================================================

        if (
            not extracted_content
            and not summary
        ):

            extraction_errors += 1

            extraction_review_count += 1

            reason = (
                extraction_error
                or
                "Contenu et résumé absents."
            )

            print(
                f"   ⚠️ {reason}"
            )

            errors_list.append({

                "index": index,

                "id": article_id,

                "title": title,

                "url": url,

                "error_type": "extraction_empty",

                "error": reason,

                "timestamp": datetime.now().isoformat(),

            })

            add_error_result(

                results,

                index,

                article_id,

                title,

                source,

                url,

                summary,

                content_length,

                reason,

                extraction_failed=True,

            )

            continue

        # ====================================================
        # CONTENU UTILISE POUR LA PERTINENCE
        #
        # Si contenu complet disponible :
        #     contenu complet
        #
        # Sinon :
        #     résumé
        #
        # Le titre et le résumé sont aussi transmis.
        # ====================================================

        relevance_text = (

            extracted_content

            if extracted_content

            else summary

        )

        if not relevance_text:

            extraction_errors += 1
            extraction_review_count += 1

            reason = "Aucun contenu exploitable pour la pertinence."

            errors_list.append({

                "index": index,
                "id": article_id,
                "title": title,
                "url": url,
                "error_type": "relevance_input_empty",
                "error": reason,
                "timestamp": datetime.now().isoformat(),

            })

            add_error_result(

                results,
                index,
                article_id,
                title,
                source,
                url,
                summary,
                content_length,
                reason,
                extraction_failed=True,

            )

            continue

        # ====================================================
        # 4. PERTINENCE CGI
        # ====================================================

        try:

            relevant = is_relevant_ai(

                content=relevance_text,

                title=title,

                summary=summary,

                url=url,

            )

        except Exception as e:

            print(
                f"❌ Erreur pertinence : {e}"
            )

            relevance_errors += 1

            errors_list.append({

                "index": index,

                "id": article_id,

                "title": title,

                "url": url,

                "error_type": "relevance",

                "error": str(e),

                "timestamp": datetime.now().isoformat(),

            })

            add_error_result(

                results,

                index,

                article_id,

                title,

                source,

                url,

                summary,

                content_length,

                "Erreur lors de l'analyse de pertinence.",

            )

            continue

        if not relevant:

            print(
                "⚪ Article non pertinent pour CGI"
            )

            continue

        relevant_count += 1

        print(
            "🟢 Article pertinent CGI"
        )

        # ====================================================
        # 5. SENTIMENT
        # ====================================================

        try:

            sentiment_result = analyze_cgi_sentiment(

                title=title,

                summary=summary,

                content=extracted_content,

            )

        except Exception as e:

            print(
                f"❌ Erreur sentiment : {e}"
            )

            sentiment_errors += 1

            sentiment_review_count += 1

            errors_list.append({

                "index": index,

                "id": article_id,

                "title": title,

                "url": url,

                "error_type": "sentiment",

                "error": str(e),

                "timestamp": datetime.now().isoformat(),

            })

            add_error_result(

                results,

                index,

                article_id,

                title,

                source,

                url,

                summary,

                content_length,

                "Erreur lors de l'analyse sentiment.",

            )

            continue

        # ====================================================
        # 6. RESULTAT SENTIMENT
        # ====================================================

        sentiment = clean_text(

            sentiment_result.get(

                "sentiment",

                "REVIEW",

            )

        )

        score = sentiment_result.get(

            "score",

            0.0,

        )

        confidence = sentiment_result.get(

            "confidence",

            0.0,

        )

        margin = sentiment_result.get(

            "margin",

            0.0,

        )

        review = safe_bool(

            sentiment_result.get(

                "review",

                False,

            )

        )

        content_mismatch = safe_bool(

            sentiment_result.get(

                "content_mismatch",

                False,

            )

        )

        reason = clean_text(

            sentiment_result.get(

                "reason",

                "",

            )

        )

        model = clean_text(

            sentiment_result.get(

                "model",

                "",

            )

        )

        device = clean_text(

            sentiment_result.get(

                "device",

                "",

            )

        )

        # ====================================================
        # SECURITE
        #
        # IMPORTANT :
        #
        # content_mismatch NE FORCE PLUS REVIEW.
        #
        # Le modèle peut signaler un mismatch sans que le
        # pipeline transforme automatiquement le sentiment.
        # ====================================================

        if review:

            sentiment = "REVIEW"

            sentiment_review_count += 1

        if content_mismatch:

            mismatch_count += 1

            print(
                "   ⚠️ Content mismatch signalé"
            )

        # ====================================================
        # SENTIMENT INVALIDE
        # ====================================================

        if sentiment not in {

            "Positive",

            "Negative",

            "Neutral",

            "REVIEW",

        }:

            sentiment = "REVIEW"

            review = True

            sentiment_review_count += 1

            reason = (
                "Sentiment retourné par le modèle "
                "non reconnu."
            )

        # ====================================================
        # COMPTEUR
        # ====================================================

        analyzed_count += 1

        # ====================================================
        # AFFICHAGE
        # ====================================================

        print(
            f"   Sentiment : {sentiment}"
        )

        print(
            f"   Score     : {score}"
        )

        print(
            f"   Confiance : {confidence}"
        )

        print(
            f"   Review    : {review}"
        )

        print(
            f"   Mismatch  : {content_mismatch}"
        )

        print(
            f"   Raisonnement : {reason}"
        )

        # ====================================================
        # RESULTAT
        # ====================================================

        results.append({

            "index": index,

            "id": article_id,

            "title": title,

            "source": source,

            "url": url,

            "summary": summary,

            "content_length": content_length,

            "extraction_method": extraction_method,

            "relevant": True,

            "sentiment": sentiment,

            "score": score,

            "confidence": confidence,

            "margin": margin,

            "review": review,

            "content_mismatch": content_mismatch,

            "extraction_failed": extraction_failed,

            "reason": reason,

            "model": model,

            "device": device,

            "timestamp": datetime.now().isoformat(),

        })

    # ========================================================
    # SAUVEGARDE CSV
    # ========================================================

    save_results(
        results
    )

    save_errors(
        errors_list
    )

    # ========================================================
    # STATISTIQUES
    # ========================================================

    positive_count = sum(

        1

        for row in results

        if row.get(
            "sentiment"
        ) == "Positive"

    )

    negative_count = sum(

        1

        for row in results

        if row.get(
            "sentiment"
        ) == "Negative"

    )

    neutral_count = sum(

        1

        for row in results

        if row.get(
            "sentiment"
        ) == "Neutral"

    )

    review_count = sum(

        1

        for row in results

        if row.get(
            "sentiment"
        ) == "REVIEW"

    )

    # ========================================================
    # FIN
    # ========================================================

    print()

    print(
        "=" * 70
    )

    print(
        "FIN DU DRY-RUN"
    )

    print(
        "=" * 70
    )

    print()

    print(
        f"Articles récupérés     : "
        f"{len(articles)}"
    )

    print(
        f"Pré-filtre rejetés     : "
        f"{prefilter_rejected}"
    )

    print(
        f"Non-articles rejetés   : "
        f"{non_article_rejected}"
    )

    print(
        f"Articles pertinents    : "
        f"{relevant_count}"
    )

    print(
        f"Articles analysés      : "
        f"{analyzed_count}"
    )

    print(
        f"Résultats CSV          : "
        f"{len(results)}"
    )

    print()

    print(
        "--- EXTRACTION ---"
    )

    print(
        f"Contenu complet        : "
        f"{full_content_count}"
    )

    print(
        f"Résumé seul            : "
        f"{summary_only_count}"
    )

    print()

    print(
        "--- ERREURS ---"
    )

    print(
        f"Pré-filtre             : "
        f"{prefilter_errors}"
    )

    print(
        f"Extraction             : "
        f"{extraction_errors}"
    )

    print(
        f"Pertinence             : "
        f"{relevance_errors}"
    )

    print(
        f"Sentiment              : "
        f"{sentiment_errors}"
    )

    print()

    print(
        "--- SENTIMENT ---"
    )

    print(
        f"Positive               : "
        f"{positive_count}"
    )

    print(
        f"Neutral                : "
        f"{neutral_count}"
    )

    print(
        f"Negative               : "
        f"{negative_count}"
    )

    print(
        f"Review                 : "
        f"{review_count}"
    )

    print(
        f"Content mismatch       : "
        f"{mismatch_count}"
    )

    print()

    print(
        "--- REVIEW ---"
    )

    print(
        f"Extraction REVIEW      : "
        f"{extraction_review_count}"
    )

    print(
        f"Sentiment REVIEW       : "
        f"{sentiment_review_count}"
    )

    print()

    print(
        "--- FICHIERS ---"
    )

    print(
        f"Résultats : "
        f"{OUTPUT_CSV}"
    )

    print(
        f"Erreurs   : "
        f"{ERROR_CSV}"
    )

    print()

    print(
        "⚠️ SQLITE : AUCUNE MODIFICATION"
    )

    print()

    print(
        "=" * 70
    )


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":

    main()