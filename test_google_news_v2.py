# ============================================================
# test_google_news_v2.py
# DRY-RUN Google News + Pertinence + Sentiment
# AUCUNE MODIFICATION SQLITE
# ============================================================

import csv
import os
from datetime import datetime

from modules.google_news_source_v2 import (
    collect_google_news_v2,
)

from modules.ai_classifier import (
    classify_relevance,
)

from modules.sentiment_analysis import (
    analyze_cgi_sentiment,
)


# ============================================================
# CONFIGURATION
# ============================================================

OUTPUT_CSV = (
    "google_news_v2_results.csv"
)

ERROR_CSV = (
    "google_news_v2_errors.csv"
)


# ============================================================
# UTILITAIRES
# ============================================================

def _to_bool(value):

    if isinstance(value, bool):

        return value

    if isinstance(value, str):

        return value.strip().lower() in {
            "true",
            "1",
            "yes",
            "oui",
        }

    return bool(value)


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print("=" * 80)

    print(
        "GOOGLE NEWS V2 - DRY RUN"
    )

    print("=" * 80)

    print()

    print(
        "⚠️ MODE TEST : SQLITE NE SERA PAS MODIFIÉE"
    )

    print()

    # ========================================================
    # COLLECTE
    # ========================================================

    print(
        "1. COLLECTE GOOGLE NEWS"
    )

    print("-" * 80)

    try:

        articles = collect_google_news_v2()

    except Exception as exc:

        print()

        print(
            f"ERREUR COLLECTE : {exc}"
        )

        return

    print()

    print(
        f"Articles récupérés : {len(articles)}"
    )

    # ========================================================
    # COMPTEURS
    # ========================================================

    results = []

    errors = []

    prefilter_rejected = 0

    relevance_errors = 0

    sentiment_errors = 0

    relevant_count = 0

    analyzed_count = 0

    summary_count = 0

    no_summary_count = 0

    positive_count = 0

    negative_count = 0

    neutral_count = 0

    review_count = 0

    mismatch_count = 0

    # ========================================================
    # TRAITEMENT
    # ========================================================

    for index, article in enumerate(
        articles,
        start=1,
    ):

        title = str(
            article.get(
                "title",
                "",
            )
            or ""
        ).strip()

        summary = str(
            article.get(
                "summary",
                "",
            )
            or ""
        ).strip()

        content = str(
            article.get(
                "content",
                "",
            )
            or ""
        ).strip()

        source = str(
            article.get(
                "source",
                "",
            )
            or ""
        ).strip()

        url = str(
            article.get(
                "url",
                "",
            )
            or ""
        ).strip()

        date = str(
            article.get(
                "date",
                "",
            )
            or ""
        ).strip()

        # ----------------------------------------------------
        # SUMMARY STATISTICS
        # ----------------------------------------------------

        if summary:

            summary_count += 1

        else:

            no_summary_count += 1

        print()

        print(
            f"[{index}/{len(articles)}] {title}"
        )

        print(
            f"   Source : {source}"
        )

        # ----------------------------------------------------
        # PERTINENCE
        # ----------------------------------------------------

        try:

            relevance = classify_relevance(
                title=title,
                summary=summary,
                content=content,
                url=url,
            )

        except Exception as exc:

            relevance_errors += 1

            errors.append({

                "index": index,

                "title": title,

                "url": url,

                "error_type": (
                    "relevance"
                ),

                "error": str(exc),

            })

            print(
                f"   ❌ Erreur pertinence : {exc}"
            )

            continue

        relevant = bool(
            relevance.get(
                "relevant",
                False,
            )
        )

        relevance_score = float(
            relevance.get(
                "score",
                0.0,
            )
            or 0.0
        )

        relevance_reason = str(
            relevance.get(
                "reason",
                "",
            )
            or ""
        )

        print(
            f"   Pertinent : {relevant}"
        )

        print(
            f"   Score pertinence : "
            f"{relevance_score:.2f}"
        )

        if relevance_reason:

            print(
                f"   Raison : "
                f"{relevance_reason}"
            )

        # ----------------------------------------------------
        # NON PERTINENT
        # ----------------------------------------------------

        if not relevant:

            prefilter_rejected += 1

            results.append({

                "title": title,

                "summary": summary,

                "source": source,

                "date": date,

                "url": url,

                "relevant": False,

                "relevance_score": (
                    relevance_score
                ),

                "relevance_reason": (
                    relevance_reason
                ),

                "sentiment": (
                    "NOT_ANALYZED"
                ),

                "score": "",

                "confidence": "",

                "margin": "",

                "review": "",

                "reason": "",

                "content_mismatch": "",

                "model": "",

                "device": "",

                "input_mode": (
                    "RSS_DISCOVERY"
                ),

            })

            continue

        # ----------------------------------------------------
        # PERTINENT
        # ----------------------------------------------------

        relevant_count += 1

        # ----------------------------------------------------
        # SENTIMENT
        # ----------------------------------------------------

        try:

            sentiment_result = (
                analyze_cgi_sentiment(
                    title=title,
                    summary=summary,
                    content=content,
                )
            )

        except Exception as exc:

            sentiment_errors += 1

            errors.append({

                "index": index,

                "title": title,

                "url": url,

                "error_type": (
                    "sentiment"
                ),

                "error": str(exc),

            })

            print(
                f"   ❌ Erreur sentiment : {exc}"
            )

            continue

        analyzed_count += 1

        sentiment = sentiment_result.get(
            "sentiment",
            "Neutral",
        )

        score = sentiment_result.get(
            "score",
            0.0,
        )

        confidence = (
            sentiment_result.get(
                "confidence",
                0.0,
            )
        )

        margin = (
            sentiment_result.get(
                "margin",
                0.0,
            )
        )

        review = _to_bool(
            sentiment_result.get(
                "review",
                False,
            )
        )

        reason = str(
            sentiment_result.get(
                "reason",
                "",
            )
            or ""
        )

        content_mismatch = _to_bool(
            sentiment_result.get(
                "content_mismatch",
                False,
            )
        )

        model = str(
            sentiment_result.get(
                "model",
                "",
            )
            or ""
        )

        device = str(
            sentiment_result.get(
                "device",
                "",
            )
            or ""
        )

        # ----------------------------------------------------
        # COMPTEURS SENTIMENT
        # ----------------------------------------------------

        if sentiment == "Positive":

            positive_count += 1

        elif sentiment == "Negative":

            negative_count += 1

        elif sentiment == "Neutral":

            neutral_count += 1

        if review:

            review_count += 1

        if content_mismatch:

            mismatch_count += 1

        # ----------------------------------------------------
        # AFFICHAGE
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # RESULTAT
        # ----------------------------------------------------

        results.append({

            "title": title,

            "summary": summary,

            "source": source,

            "date": date,

            "url": url,

            "relevant": True,

            "relevance_score": (
                relevance_score
            ),

            "relevance_reason": (
                relevance_reason
            ),

            "sentiment": sentiment,

            "score": score,

            "confidence": confidence,

            "margin": margin,

            "review": review,

            "reason": reason,

            "content_mismatch": (
                content_mismatch
            ),

            "model": model,

            "device": device,

            "input_mode": (
                "RSS_DISCOVERY"
            ),

        })

    # ========================================================
    # CSV RESULTS
    # ========================================================

    result_fields = [

        "title",

        "summary",

        "source",

        "date",

        "url",

        "relevant",

        "relevance_score",

        "relevance_reason",

        "sentiment",

        "score",

        "confidence",

        "margin",

        "review",

        "reason",

        "content_mismatch",

        "model",

        "device",

        "input_mode",

    ]

    with open(
        OUTPUT_CSV,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=result_fields,
        )

        writer.writeheader()

        writer.writerows(
            results
        )

    # ========================================================
    # CSV ERRORS
    # ========================================================

    error_fields = [

        "index",

        "title",

        "url",

        "error_type",

        "error",

    ]

    with open(
        ERROR_CSV,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=error_fields,
        )

        writer.writeheader()

        writer.writerows(
            errors
        )

    # ========================================================
    # STATISTIQUES
    # ========================================================

    print()

    print("=" * 80)

    print(
        "FIN DU DRY-RUN"
    )

    print("=" * 80)

    print()

    print(
        f"Articles récupérés     : "
        f"{len(articles)}"
    )

    print(
        f"Résumé disponible      : "
        f"{summary_count}"
    )

    print(
        f"Sans résumé            : "
        f"{no_summary_count}"
    )

    print()

    print(
        f"Non pertinents         : "
        f"{prefilter_rejected}"
    )

    print(
        f"Articles pertinents    : "
        f"{relevant_count}"
    )

    print(
        f"Articles analysés      : "
        f"{analyzed_count}"
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
        "--- ERREURS ---"
    )

    print(
        f"Pertinence             : "
        f"{relevance_errors}"
    )

    print(
        f"Sentiment              : "
        f"{sentiment_errors}"
    )

    print(
        f"Total erreurs          : "
        f"{len(errors)}"
    )

    print()

    print(
        "--- FICHIERS ---"
    )

    print(
        f"Résultats : "
        f"{os.path.abspath(OUTPUT_CSV)}"
    )

    print(
        f"Erreurs   : "
        f"{os.path.abspath(ERROR_CSV)}"
    )

    print()

    print(
        "⚠️ SQLITE : AUCUNE MODIFICATION"
    )

    print()

    print(
        "=" * 80
    )


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":

    main()