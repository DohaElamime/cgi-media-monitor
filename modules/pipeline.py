# ============================================================
# modules/pipeline.py
# CGI Media Monitor - PRODUCTION PIPELINE
#
# Pipeline:
#
# Google News
#     ↓
# Pre-filter
#     ↓
# Article Extractor
#     ↓
# AI Relevance - GPT-OSS 120B
#     ↓
# Semantic Sentiment - GPT-OSS 120B
#     ↓
# SQLite
#
# IMPORTANT:
# - Cette version écrit réellement dans SQLite.
# - Le dry-run doit être utilisé avant ce fichier.
# - Aucun sentiment par mots-clés.
# - Le sentiment utilise title + summary + content.
# ============================================================

from __future__ import annotations

from modules.aggregator import collect_articles

from modules.article_extractor import (
    extract_article,
    is_usable_summary,
)

from modules.ai_classifier import (
    is_relevant_ai,
)

from modules.pre_filter import (
    is_article_candidate,
)

from modules.sentiment_analysis import (
    analyze_cgi_sentiment,
)

from modules.database import (
    save_article,
)


# ============================================================
# HELPERS
# ============================================================

def safe_str(value) -> str:
    """
    Convertit une valeur en chaîne de caractères propre.
    """

    if value is None:
        return ""

    return str(value).strip()


def safe_bool(value) -> bool:
    """
    Conversion robuste vers bool.
    """

    if isinstance(value, bool):
        return value

    if isinstance(value, str):

        return value.strip().lower() in {
            "true",
            "1",
            "yes",
            "y",
            "oui",
        }

    return bool(value)


def safe_float(
    value,
    default=None,
) -> float:
    """
    Conversion robuste vers float.
    """

    if value is None:
        return default
    try:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return default
            if value.endswith("%"):
                value = float(value[:-1].strip()) / 100.0
            else:
                value = float(value)
        else:
            value = float(value)
        if value < 0:
            return 0.0
        if value > 1:
            return 1.0
        return value
    except (TypeError, ValueError):
        return default


# ============================================================
# PIPELINE
# ============================================================

def run_pipeline():

    print()
    print("=" * 80)
    print("CGI MEDIA MONITOR - PRODUCTION PIPELINE")
    print("=" * 80)
    print()

    print("⚠️ MODE PRODUCTION")
    print("⚠️ Les articles pertinents seront enregistrés dans SQLite.")
    print()

    # ========================================================
    # 1. COLLECTE
    # ========================================================

    print("-" * 80)
    print("1. COLLECTE DES ARTICLES")
    print("-" * 80)

    try:

        articles = collect_articles()

    except Exception as e:

        print()
        print(
            f"❌ Erreur lors de la collecte : {e}"
        )

        return []

    if articles is None:
        articles = []

    total_articles = len(articles)

    print(
        f"📰 Articles récupérés : "
        f"{total_articles}"
    )

    # ========================================================
    # STATISTIQUES
    # ========================================================

    candidate_count = 0

    rejected_count = 0

    extracted_count = 0

    full_content_count = 0

    summary_only_count = 0

    extraction_failed_count = 0

    relevant_count = 0

    non_relevant_count = 0

    analyzed_count = 0

    saved_count = 0

    existing_count = 0

    prefilter_errors = 0

    extraction_errors = 0

    relevance_errors = 0

    sentiment_errors = 0

    database_errors = 0

    review_count = 0

    mismatch_count = 0

    relevant_articles = []

    sentiment_counts = {
        "Positive": 0,
        "Neutral": 0,
        "Negative": 0,
    }

    # ========================================================
    # 2. TRAITEMENT
    # ========================================================

    for index, article in enumerate(
        articles,
        start=1,
    ):

        print()
        print("-" * 80)
        print(
            f"[{index}/{total_articles}]"
        )

        # ====================================================
        # BASIC ARTICLE DATA
        # ====================================================

        if not isinstance(
            article,
            dict,
        ):

            print(
                "❌ Article invalide : format inattendu"
            )

            rejected_count += 1

            continue

        title = safe_str(
            article.get("title")
            or article.get("name")
        )

        summary = safe_str(
            article.get("summary")
            or article.get("description")
        )

        url = safe_str(
            article.get("url")
            or article.get("link")
        )

        source = safe_str(
            article.get("source")
            or article.get("publisher")
        )

        published_at = safe_str(
            article.get("published_at")
            or article.get("published")
            or article.get("date")
        )

        print(
            f"📰 Titre : {title}"
        )

        print(
            f"🔗 URL : {url}"
        )

        # ====================================================
        # 2.1 PRE-FILTER
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

            continue

        if not candidate:

            print(
                "⚪ Rejeté par le pré-filtre"
            )

            rejected_count += 1

            continue

        candidate_count += 1

        print(
            "🟢 Pré-filtre : ACCEPTÉ"
        )

        # ====================================================
        # 2.2 ARTICLE EXTRACTION
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

            continue

        # ----------------------------------------------------
        # CURRENT EXTRACTOR RETURNS DICT
        # ----------------------------------------------------

        if not isinstance(
            extraction_result,
            dict,
        ):

            print(
                "❌ Erreur extraction : "
                "résultat inattendu"
            )

            extraction_errors += 1

            continue

        # ====================================================
        # EXTRACTION RESULT
        # ====================================================

        content = safe_str(
            extraction_result.get(
                "content"
            )
        )

        extracted_summary = (
            safe_str(
                extraction_result.get(
                    "summary"
                )
            )
            or summary
        )

        final_url = (
            safe_str(
                extraction_result.get(
                    "final_url"
                )
            )
            or url
        )

        extraction_method = safe_str(
            extraction_result.get(
                "method"
            )
        )

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

        extraction_error = safe_str(
            extraction_result.get(
                "error"
            )
        )

        # ====================================================
        # USABLE SUMMARY
        # ====================================================

        try:

            usable_summary = is_usable_summary(
                extracted_summary
            )

        except Exception:

            usable_summary = (
                len(
                    extracted_summary
                ) >= 80
            )

        # ====================================================
        # EXTRACTION STATUS
        # ====================================================

        if content:

            extracted_count += 1
            full_content_count += 1

            print(
                "📄 Extraction : FULL CONTENT"
            )

            print(
                f"   Taille : "
                f"{len(content):,} caractères"
            )

        elif usable_summary:

            extracted_count += 1
            summary_only_count += 1

            print(
                "📄 Extraction : SUMMARY ONLY"
            )

            print(
                f"   Taille summary : "
                f"{len(extracted_summary):,} caractères"
            )

        else:

            extraction_failed_count += 1
            extraction_errors += 1

            print(
                "❌ Aucun contenu utilisable"
            )

            if extraction_error:

                print(
                    f"   Erreur : "
                    f"{extraction_error}"
                )

            continue

        # ====================================================
        # STORE EXTRACTION DATA IN ARTICLE
        # ====================================================

        article["content"] = content

        article["summary"] = (
            extracted_summary
        )

        article["resolved_url"] = (
            final_url
        )

        article["extraction_method"] = (
            extraction_method
        )

        article["extraction_failed"] = (
            extraction_failed
        )

        article["extraction_review"] = (
            extraction_review
        )

        article["extraction_error"] = (
            extraction_error
        )

        # ====================================================
        # 2.3 AI RELEVANCE
        # ====================================================

        print()
        print(
            "🤖 Analyse de pertinence GPT-OSS..."
        )

        try:

            relevance_result = is_relevant_ai(
                content=content,
                title=title,
                summary=extracted_summary,
                url=final_url,
            )

        except Exception as e:

            print(
                f"❌ Erreur pertinence : {e}"
            )

            relevance_errors += 1

            continue

        # ====================================================
        # RELEVANCE ERROR
        # ====================================================

        relevance_error = safe_str(
            relevance_result.get(
                "error"
            )
        )

        if relevance_error:

            print(
                "❌ Erreur GPT-OSS pertinence : "
                f"{relevance_error}"
            )

            relevance_errors += 1

            continue

        # ====================================================
        # RELEVANCE DATA
        # ====================================================

        relevant = safe_bool(
            relevance_result.get(
                "relevant",
                False,
            )
        )

        relevance_confidence = safe_float(
            relevance_result.get(
                "confidence",
                None,
            )
        )

        relevance_reason = safe_str(
            relevance_result.get(
                "reason"
            )
        )

        relevance_model = safe_str(
            relevance_result.get(
                "model"
            )
        )

        relevance_device = safe_str(
            relevance_result.get(
                "device"
            )
        )

        # ====================================================
        # STORE RELEVANCE
        # ====================================================

        article["relevant"] = relevant

        article["relevance_confidence"] = round(
            relevance_confidence,
            4,
        )

        article["relevance_reason"] = (
            relevance_reason
        )

        article["relevance_model"] = (
            relevance_model
        )

        article["relevance_device"] = (
            relevance_device
        )

        print(
            "📊 Pertinence : "
            f"{'PERTINENT' if relevant else 'NON PERTINENT'}"
        )

        print(
            "📈 Confiance : "
            f"{relevance_confidence:.2%}" if relevance_confidence is not None else "N/A"
        )

        print(
            f"💬 Raisonnement : "
            f"{relevance_reason}"
        )

        # ====================================================
        # NON RELEVANT
        # ====================================================

        if not relevant:

            non_relevant_count += 1

            print(
                "⚪ Article non pertinent → ignoré"
            )

            continue

        # ====================================================
        # RELEVANT
        # ====================================================

        relevant_count += 1

        print(
            "🟢 Article pertinent"
        )

        # ====================================================
        # 2.4 SENTIMENT
        # ====================================================

        print()
        print(
            "🧠 Analyse sentimentale GPT-OSS..."
        )

        try:

            sentiment_result = (
                analyze_cgi_sentiment(
                    title=title,
                    summary=extracted_summary,
                    content=content,
                )
            )

        except Exception as e:

            print(
                f"❌ Erreur sentiment : {e}"
            )

            sentiment_errors += 1

            continue

        # ====================================================
        # SENTIMENT ERROR
        # ====================================================

        sentiment_error = safe_str(
            sentiment_result.get(
                "error"
            )
        )

        if sentiment_error:

            print(
                "❌ Erreur GPT-OSS sentiment : "
                f"{sentiment_error}"
            )

            sentiment_errors += 1

            continue

        # ====================================================
        # SENTIMENT DATA
        # ====================================================

        sentiment = safe_str(
            sentiment_result.get(
                "sentiment",
                "Neutral",
            )
        )

        sentiment = sentiment.capitalize()

        if sentiment not in {
            "Positive",
            "Neutral",
            "Negative",
        }:

            sentiment = "Neutral"

            print(
                "⚠️ Sentiment invalide → "
                "Neutral"
            )

        sentiment_score = safe_float(
            sentiment_result.get(
                "score",
                None,
            )
        )

        sentiment_confidence = safe_float(
            sentiment_result.get(
                "confidence",
                None,
            )
        )

        sentiment_margin = safe_float(
            sentiment_result.get(
                "margin",
                None,
            )
        )

        sentiment_reason = safe_str(
            sentiment_result.get(
                "reason"
            )
        )

        sentiment_review = safe_bool(
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

        sentiment_model = safe_str(
            sentiment_result.get(
                "model"
            )
        )

        sentiment_device = safe_str(
            sentiment_result.get(
                "device"
            )
        )

        sentiment_elapsed = (
            sentiment_result.get(
                "elapsed_seconds"
            )
        )

        # ====================================================
        # STORE SENTIMENT
        # ====================================================

        article["sentiment"] = sentiment

        article["sentiment_score"] = (
            sentiment_score
        )

        article["sentiment_confidence"] = (
            sentiment_confidence
        )

        article["sentiment_margin"] = (
            sentiment_margin
        )

        article["sentiment_reason"] = (
            sentiment_reason
        )

        article["sentiment_review"] = (
            sentiment_review
        )

        article["content_mismatch"] = (
            content_mismatch
        )

        article["sentiment_model"] = (
            sentiment_model
        )

        article["sentiment_device"] = (
            sentiment_device
        )

        article["sentiment_elapsed_seconds"] = (
            sentiment_elapsed
        )

        # ====================================================
        # STATISTICS
        # ====================================================

        analyzed_count += 1

        sentiment_counts[
            sentiment
        ] += 1

        if sentiment_review:

            review_count += 1

        if content_mismatch:

            mismatch_count += 1

        # ====================================================
        # DISPLAY
        # ====================================================

        print(
            f"🧠 Sentiment : "
            f"{sentiment}"
        )

        print(
            f"📊 Confiance : "
            f"{sentiment_confidence:.2%}" if sentiment_confidence is not None else "N/A"
        )

        print(
            f"🔎 Review : "
            f"{sentiment_review}"
        )

        print(
            f"⚠️ Content mismatch : "
            f"{content_mismatch}"
        )

        print(
            f"💬 Raisonnement : "
            f"{sentiment_reason}"
        )

        # ====================================================
        # ADD TO RELEVANT ARTICLES
        # ====================================================

        relevant_articles.append(
            article
        )

        # ====================================================
        # 2.5 SAVE TO SQLITE
        # ====================================================

        print()
        print(
            "💾 Sauvegarde SQLite..."
        )

        try:

            added = save_article(
                article
            )

            if added:

                saved_count += 1

                print(
                    "✅ Article enregistré "
                    "dans SQLite"
                )

            else:

                existing_count += 1

                print(
                    "ℹ️ Article déjà présent "
                    "ou mis à jour"
                )

        except Exception as e:

            print(
                "❌ Erreur sauvegarde SQLite : "
                f"{e}"
            )

            database_errors += 1

    # ========================================================
    # 3. FINAL REPORT
    # ========================================================

    print()
    print()
    print("=" * 80)
    print("FIN DU PIPELINE")
    print("=" * 80)

    print()

    print(
        f"Articles récupérés       : "
        f"{total_articles}"
    )

    print(
        f"Articles candidats       : "
        f"{candidate_count}"
    )

    print(
        f"Rejetés pré-filtre       : "
        f"{rejected_count}"
    )

    print(
        f"Articles extraits        : "
        f"{extracted_count}"
    )

    print(
        f"Full content             : "
        f"{full_content_count}"
    )

    print(
        f"Summary only             : "
        f"{summary_only_count}"
    )

    print(
        f"Extraction failures      : "
        f"{extraction_failed_count}"
    )

    print(
        f"Articles pertinents      : "
        f"{relevant_count}"
    )

    print(
        f"Articles non pertinents  : "
        f"{non_relevant_count}"
    )

    print(
        f"Articles analysés        : "
        f"{analyzed_count}"
    )

    print(
        f"Articles sauvegardés     : "
        f"{saved_count}"
    )

    print(
        f"Articles déjà présents   : "
        f"{existing_count}"
    )

    # ========================================================
    # SENTIMENT
    # ========================================================

    print()
    print(
        "--- SENTIMENT ---"
    )

    print(
        f"Positive                 : "
        f"{sentiment_counts['Positive']}"
    )

    print(
        f"Neutral                  : "
        f"{sentiment_counts['Neutral']}"
    )

    print(
        f"Negative                 : "
        f"{sentiment_counts['Negative']}"
    )

    print(
        f"Review                   : "
        f"{review_count}"
    )

    print(
        f"Content mismatch         : "
        f"{mismatch_count}"
    )

    # ========================================================
    # ERRORS
    # ========================================================

    print()
    print(
        "--- ERREURS ---"
    )

    print(
        f"Pré-filtre               : "
        f"{prefilter_errors}"
    )

    print(
        f"Extraction               : "
        f"{extraction_errors}"
    )

    print(
        f"Pertinence               : "
        f"{relevance_errors}"
    )

    print(
        f"Sentiment                : "
        f"{sentiment_errors}"
    )

    print(
        f"SQLite                   : "
        f"{database_errors}"
    )

    print()
    print("=" * 80)

    # ========================================================
    # FINAL STATUS
    # ========================================================

    if database_errors == 0:

        print(
            "✅ PIPELINE TERMINÉ"
        )

    else:

        print(
            "⚠️ PIPELINE TERMINÉ AVEC "
            "DES ERREURS SQLITE"
        )

    print("=" * 80)
    print()

    return relevant_articles


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    run_pipeline()