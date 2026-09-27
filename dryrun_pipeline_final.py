# ============================================================
# dryrun_pipeline_final.py
# CGI Media Monitor - FINAL DRY-RUN PIPELINE
#
# IMPORTANT:
# - Aucune modification SQLite
# - save_article() n'est jamais appelé
# - Test complet:
#     Google News
#       -> pre-filter
#       -> article extraction
#       -> AI relevance
#       -> semantic sentiment
#       -> CSV audit
# ============================================================

from __future__ import annotations

import csv
import os
import sys
import time
from typing import Any, Dict, List


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = os.path.dirname(
    os.path.abspath(__file__)
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ============================================================
# IMPORTS
# ============================================================

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


# ============================================================
# OUTPUT FILES
# ============================================================

RESULTS_FILE = os.path.join(
    PROJECT_ROOT,
    "dryrun_pipeline_final_results.csv",
)

ERRORS_FILE = os.path.join(
    PROJECT_ROOT,
    "dryrun_pipeline_final_errors.csv",
)


# ============================================================
# HELPERS
# ============================================================

def safe_str(value: Any) -> str:
    """
    Convert any value safely to string.
    """

    if value is None:
        return ""

    return str(value).strip()


def safe_bool(value: Any) -> bool:
    """
    Safely convert a value to bool.
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
    value: Any,
    default: Any = None,
) -> Any:
    """
    Safely convert a value to float.
    """

    try:
        return float(value)

    except Exception:
        return default


def get_article_value(
    article: Dict[str, Any],
    *keys: str,
) -> str:
    """
    Return the first non-empty value
    among several possible keys.
    """

    for key in keys:

        value = safe_str(
            article.get(key)
        )

        if value:
            return value

    return ""


def write_csv(
    filepath: str,
    rows: List[Dict[str, Any]],
) -> None:
    """
    Write rows to CSV.
    """

    if not rows:
        return

    fieldnames = []

    for row in rows:

        for key in row.keys():

            if key not in fieldnames:
                fieldnames.append(key)

    with open(
        filepath,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in rows:

            clean_row = {}

            for key in fieldnames:

                value = row.get(
                    key,
                    "",
                )

                if value is None:
                    value = ""

                clean_row[key] = value

            writer.writerow(clean_row)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    started_at = time.time()

    print()
    print("=" * 80)
    print("CGI MEDIA MONITOR")
    print("FINAL DRY-RUN PIPELINE")
    print("=" * 80)
    print()

    print("MODE:")
    print("  DRY-RUN")
    print("  SQLite modification: DISABLED")
    print("  save_article(): NOT CALLED")
    print()

    # ========================================================
    # STEP 1 - COLLECT
    # ========================================================

    print("-" * 80)
    print("STEP 1 - COLLECT ARTICLES")
    print("-" * 80)

    try:

        articles = collect_articles()

    except Exception as exc:

        print()
        print(
            "ERREUR collect_articles():"
        )
        print(exc)
        print()

        return

    if articles is None:
        articles = []

    total_articles = len(articles)

    print(
        f"Articles collectés : "
        f"{total_articles}"
    )

    print()

    # ========================================================
    # STATISTICS
    # ========================================================

    candidates = 0
    rejected_prefilter = 0

    extraction_attempted = 0
    extraction_full_content = 0
    extraction_summary_only = 0
    extraction_failed = 0

    relevant_count = 0
    non_relevant_count = 0
    relevance_errors = 0

    analyzed_count = 0
    classified_count = 0
    sentiment_errors = 0

    positive_count = 0
    neutral_count = 0
    negative_count = 0

    review_count = 0
    mismatch_count = 0

    processing_errors = 0

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    # ========================================================
    # STEP 2 - PROCESS ARTICLES
    # ========================================================

    print("-" * 80)
    print("STEP 2 - PROCESS ARTICLES")
    print("-" * 80)
    print()

    for index, article in enumerate(
        articles,
        start=1,
    ):

        article_started = time.time()

        if not isinstance(
            article,
            dict,
        ):

            article = {
                "raw_article": safe_str(
                    article
                )
            }

        # ====================================================
        # ARTICLE INFORMATION
        # ====================================================

        title = get_article_value(
            article,
            "title",
            "name",
        )

        url = get_article_value(
            article,
            "url",
            "link",
        )

        summary = get_article_value(
            article,
            "summary",
            "description",
        )

        source = get_article_value(
            article,
            "source",
            "publisher",
        )

        published_at = get_article_value(
            article,
            "published_at",
            "published",
            "date",
        )

        query = get_article_value(
            article,
            "query",
        )

        collection_source = get_article_value(
            article,
            "collection_source",
        )

        print(
            f"[{index:03d}/{total_articles:03d}] "
            f"{title[:90]}"
        )

        # ====================================================
        # STEP 2.1 - PRE-FILTER
        # ====================================================

        try:

            candidate = is_article_candidate(
                article
            )

        except Exception as exc:

            candidate = False

            processing_errors += 1

            errors.append(
                {
                    "stage": "pre_filter",
                    "title": title,
                    "url": url,
                    "error": safe_str(exc),
                    "error_type": "prefilter_exception",
                }
            )

        if not candidate:

            rejected_prefilter += 1

            print(
                "      -> PRE-FILTER: REJECTED"
            )

            continue

        candidates += 1

        print(
            "      -> PRE-FILTER: ACCEPTED"
        )

        # ====================================================
        # STEP 2.2 - EXTRACTION
        # ====================================================

        extraction_attempted += 1

        content = ""
        extracted_summary = summary
        final_url = url

        extraction_method = ""
        extraction_failed_flag = False
        extraction_review = False
        extraction_error = ""
        extraction_error_type = ""

        try:

            extraction_result = extract_article(
                url=url,
                title=title,
                summary=summary,
            )

            # ------------------------------------------------
            # CURRENT EXTRACTOR RETURNS DICT
            # ------------------------------------------------

            if isinstance(
                extraction_result,
                dict,
            ):

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

                extraction_failed_flag = safe_bool(
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

                extraction_error_type = safe_str(
                    extraction_result.get(
                        "error_type"
                    )
                )

            else:

                # ------------------------------------------------
                # COMPATIBILITY FALLBACK
                # ------------------------------------------------

                content = safe_str(
                    extraction_result
                )

                extracted_summary = summary

        except Exception as exc:

            extraction_failed_flag = True
            extraction_review = True
            extraction_error = safe_str(exc)
            extraction_error_type = "extraction_exception"

            errors.append(
                {
                    "stage": "extraction",
                    "title": title,
                    "url": url,
                    "error": extraction_error,
                    "error_type": extraction_error_type,
                }
            )

        # ====================================================
        # EXTRACTION STATISTICS
        # ====================================================

        try:

            usable_summary = is_usable_summary(
                extracted_summary
            )

        except Exception:

            usable_summary = (
                len(
                    safe_str(
                        extracted_summary
                    )
                ) >= 80
            )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Count each article only once:
        #
        # FULL CONTENT
        # OR
        # SUMMARY ONLY
        # OR
        # EXTRACTION FAILURE
        #
        # Do NOT increment extraction_failed again
        # based on extraction_failed_flag.
        # ----------------------------------------------------

        if content:

            extraction_full_content += 1

            print(
                "      -> EXTRACTION: FULL CONTENT "
                f"({len(content):,} chars)"
            )

        elif usable_summary:

            extraction_summary_only += 1

            print(
                "      -> EXTRACTION: SUMMARY ONLY"
            )

        else:

            extraction_failed += 1

            print(
                "      -> EXTRACTION: NO USABLE CONTENT"
            )

        # ====================================================
        # EXTRACTION REVIEW
        # ====================================================

        if extraction_review:
            review_count += 1

        # ====================================================
        # NO USABLE TEXT
        # ====================================================

        if not content and not usable_summary:

            errors.append(
                {
                    "stage": "extraction_empty",
                    "title": title,
                    "url": final_url,
                    "error": (
                        extraction_error
                        or
                        "No usable content or summary"
                    ),
                    "error_type": (
                        extraction_error_type
                        or
                        "no_usable_content"
                    ),
                }
            )

            print(
                "      -> SKIP: "
                "no usable article text"
            )

            continue

        # ====================================================
        # STEP 2.3 - AI RELEVANCE
        # ====================================================

        try:

            relevance_result = is_relevant_ai(
                content=content,
                title=title,
                summary=extracted_summary,
                url=final_url,
            )

        except Exception as exc:

            relevance_result = {
                "relevant": None,
                "confidence": None,
                "reason": (
                    f"Technical error: {exc}"
                ),
                "model": "",
                "device": "",
                "error": safe_str(exc),
                "error_type": "relevance_exception",
            }

        raw_relevant = relevance_result.get(
            "relevant"
        )

        relevant = (
            None
            if raw_relevant is None
            else safe_bool(raw_relevant)
        )

        relevance_confidence = safe_float(
            relevance_result.get(
                "confidence",
                0.0,
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

        relevance_error = safe_str(
            relevance_result.get(
                "error"
            )
        )

        relevance_error_type = safe_str(
            relevance_result.get(
                "error_type"
            )
        )

        if relevance_error:

            errors.append(
                {
                    "stage": "relevance",
                    "title": title,
                    "url": final_url,
                    "error": relevance_error,
                    "error_type": (
                        relevance_error_type
                        or
                        "relevance_error"
                    ),
                }
            )

        # ====================================================
        # RELEVANCE MODEL ERROR
        # ====================================================

        if relevant is None:

            relevance_errors += 1
            review_count += 1

            print(
                "      -> RELEVANCE: MODEL ERROR"
            )

            errors.append(
                {
                    "stage": "relevance",
                    "title": title,
                    "url": final_url,
                    "error": (
                        relevance_error
                        or relevance_reason
                        or "Relevance not classified"
                    ),
                    "error_type": (
                        relevance_error_type
                        or "not_classified"
                    ),
                }
            )

            results.append(
                {
                    "index": index,
                    "title": title,
                    "url": url,
                    "resolved_url": final_url,
                    "source": source,
                    "published_at": published_at,
                    "query": query,
                    "collection_source": collection_source,
                    "extraction_method": extraction_method,
                    "extraction_failed": extraction_failed_flag,
                    "extraction_review": extraction_review,
                    "extraction_error": extraction_error,
                    "extraction_error_type": extraction_error_type,
                    "content_length": len(content),
                    "summary_length": len(extracted_summary),
                    "relevant": "",
                    "relevance_confidence": relevance_confidence,
                    "relevance_reason": relevance_reason,
                    "relevance_model": relevance_model,
                    "relevance_device": relevance_device,
                    "relevance_error": relevance_error,
                    "relevance_error_type": (
                        relevance_error_type
                        or "not_classified"
                    ),
                    "sentiment": "",
                    "sentiment_score": "",
                    "sentiment_confidence": "",
                    "sentiment_margin": "",
                    "sentiment_review": "",
                    "classified": False,
                    "content_mismatch": "",
                    "sentiment_reason": "",
                    "sentiment_model": "",
                    "sentiment_device": "",
                    "sentiment_error": "",
                    "sentiment_error_type": "",
                    "elapsed_seconds": round(
                        time.time() - article_started,
                        3,
                    ),
                    "summary": extracted_summary,
                    "content": content,
                }
            )

            continue

        # ====================================================
        # NON-RELEVANT
        # ====================================================

        if not relevant:

            non_relevant_count += 1

            print(
                "      -> RELEVANCE: NOT RELEVANT"
            )

            results.append(
                {
                    "index": index,
                    "title": title,
                    "url": url,
                    "resolved_url": final_url,
                    "source": source,
                    "published_at": published_at,
                    "query": query,
                    "collection_source": collection_source,
                    "extraction_method":
                        extraction_method,
                    "extraction_failed":
                        extraction_failed_flag,
                    "extraction_review":
                        extraction_review,
                    "extraction_error":
                        extraction_error,
                    "extraction_error_type":
                        extraction_error_type,
                    "content_length":
                        len(content),
                    "summary_length":
                        len(extracted_summary),
                    "relevant":
                        False,
                    "relevance_confidence":
                        relevance_confidence,
                    "relevance_reason":
                        relevance_reason,
                    "relevance_model":
                        relevance_model,
                    "relevance_device":
                        relevance_device,
                    "relevance_error":
                        relevance_error,
                    "relevance_error_type":
                        relevance_error_type,
                    "sentiment":
                        "",
                    "sentiment_score":
                        "",
                    "sentiment_confidence":
                        "",
                    "sentiment_margin":
                        "",
                    "sentiment_review":
                        "",
                    "classified":
                        False,
                    "content_mismatch":
                        "",
                    "sentiment_reason":
                        "",
                    "sentiment_model":
                        "",
                    "sentiment_device":
                        "",
                    "sentiment_error":
                        "",
                    "sentiment_error_type":
                        "",
                    "elapsed_seconds":
                        round(
                            time.time()
                            - article_started,
                            3,
                        ),
                    "summary":
                        extracted_summary,
                    "content":
                        content,
                }
            )

            continue

        relevant_count += 1

        print(
            "      -> RELEVANCE: RELEVANT"
        )

        # ====================================================
        # STEP 2.4 - SENTIMENT
        # ====================================================

        analyzed_count += 1

        try:

            sentiment_result = (
                analyze_cgi_sentiment(
                    title=title,
                    summary=extracted_summary,
                    content=content,
                )
            )

        except Exception as exc:

            sentiment_result = {
                "sentiment": None,
                "score": None,
                "confidence": None,
                "margin": None,
                "review": True,
                "content_mismatch": False,
                "classified": False,
                "reason": (
                    f"Technical error: {exc}"
                ),
                "model": "",
                "device": "",
                "error": safe_str(exc),
                "error_type": "sentiment_exception",
            }

        raw_sentiment = sentiment_result.get(
            "sentiment"
        )

        sentiment = (
            safe_str(raw_sentiment)
            if raw_sentiment is not None
            else ""
        )

        sentiment_score = safe_float(
            sentiment_result.get("score")
        )

        sentiment_confidence = safe_float(
            sentiment_result.get("confidence")
        )

        sentiment_margin = safe_float(
            sentiment_result.get("margin")
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

        sentiment_reason = safe_str(
            sentiment_result.get(
                "reason"
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

        sentiment_error = safe_str(
            sentiment_result.get(
                "error"
            )
        )

        sentiment_error_type = safe_str(
            sentiment_result.get(
                "error_type"
            )
        )

        classified = (
            sentiment_result.get(
                "classified"
            ) is True
        )

        # ====================================================
        # SENTIMENT ERROR
        # ====================================================

        if sentiment_error:

            errors.append(
                {
                    "stage": "sentiment",
                    "title": title,
                    "url": final_url,
                    "error": sentiment_error,
                    "error_type": (
                        sentiment_error_type
                        or "sentiment_error"
                    ),
                }
            )

        # ====================================================
        # VALIDATE SENTIMENT
        # ====================================================

        if not classified:

            sentiment_errors += 1
            sentiment_review = True

            # IMPORTANT:
            # Count review also when the model fails.
            review_count += 1

            error_message = (
                sentiment_error
                or sentiment_reason
                or "Sentiment not classified"
            )

            error_type = (
                sentiment_error_type
                or "not_classified"
            )

            errors.append(
                {
                    "stage": "sentiment",
                    "title": title,
                    "url": final_url,
                    "error": error_message,
                    "error_type": error_type,
                }
            )

            print(
                "      -> SENTIMENT: MODEL ERROR"
            )

            print(
                "         reason="
                + error_message
            )

            print(
                "         classified=False"
            )

            print(
                "         REVIEW = YES"
            )

            results.append(
                {
                    "index": index,
                    "title": title,
                    "url": url,
                    "resolved_url": final_url,
                    "source": source,
                    "published_at": published_at,
                    "query": query,
                    "collection_source": collection_source,
                    "extraction_method": extraction_method,
                    "extraction_failed": extraction_failed_flag,
                    "extraction_review": extraction_review,
                    "extraction_error": extraction_error,
                    "extraction_error_type": extraction_error_type,
                    "content_length": len(content),
                    "summary_length": len(extracted_summary),
                    "relevant": True,
                    "relevance_confidence": relevance_confidence,
                    "relevance_reason": relevance_reason,
                    "relevance_model": relevance_model,
                    "relevance_device": relevance_device,
                    "relevance_error": relevance_error,
                    "relevance_error_type": relevance_error_type,
                    "sentiment": "",
                    "sentiment_score": sentiment_score,
                    "sentiment_confidence": sentiment_confidence,
                    "sentiment_margin": sentiment_margin,
                    "sentiment_review": True,
                    "classified": False,
                    "content_mismatch": content_mismatch,
                    "sentiment_reason": sentiment_reason,
                    "sentiment_model": sentiment_model,
                    "sentiment_device": sentiment_device,
                    "sentiment_error": sentiment_error,
                    "sentiment_error_type": error_type,
                    "elapsed_seconds": round(
                        time.time() - article_started,
                        3,
                    ),
                    "summary": extracted_summary,
                    "content": content,
                }
            )

            continue

        # ====================================================
        # NORMALIZE SENTIMENT
        # ====================================================

        normalized_sentiment = sentiment.capitalize()

        if normalized_sentiment not in {
            "Positive",
            "Neutral",
            "Negative",
        }:

            sentiment_errors += 1
            sentiment_review = True
            classified = False

            # IMPORTANT:
            # Invalid sentiment also requires review.
            review_count += 1

            error_message = (
                "Invalid sentiment returned by model"
            )

            error_type = "invalid_sentiment"

            errors.append(
                {
                    "stage": "sentiment",
                    "title": title,
                    "url": final_url,
                    "error": error_message,
                    "error_type": error_type,
                }
            )

            print(
                "      -> SENTIMENT: MODEL ERROR"
            )

            print(
                "         reason="
                + error_message
            )

            print(
                "         classified=False"
            )

            print(
                "         REVIEW = YES"
            )

            # IMPORTANT:
            # Keep the article in the CSV audit.
            results.append(
                {
                    "index": index,
                    "title": title,
                    "url": url,
                    "resolved_url": final_url,
                    "source": source,
                    "published_at": published_at,
                    "query": query,
                    "collection_source": collection_source,
                    "extraction_method": extraction_method,
                    "extraction_failed": extraction_failed_flag,
                    "extraction_review": extraction_review,
                    "extraction_error": extraction_error,
                    "extraction_error_type": extraction_error_type,
                    "content_length": len(content),
                    "summary_length": len(extracted_summary),
                    "relevant": True,
                    "relevance_confidence": relevance_confidence,
                    "relevance_reason": relevance_reason,
                    "relevance_model": relevance_model,
                    "relevance_device": relevance_device,
                    "relevance_error": relevance_error,
                    "relevance_error_type": relevance_error_type,
                    "sentiment": "",
                    "sentiment_score": sentiment_score,
                    "sentiment_confidence": sentiment_confidence,
                    "sentiment_margin": sentiment_margin,
                    "sentiment_review": True,
                    "classified": False,
                    "content_mismatch": content_mismatch,
                    "sentiment_reason": sentiment_reason,
                    "sentiment_model": sentiment_model,
                    "sentiment_device": sentiment_device,
                    "sentiment_error": error_message,
                    "sentiment_error_type": error_type,
                    "elapsed_seconds": round(
                        time.time() - article_started,
                        3,
                    ),
                    "summary": extracted_summary,
                    "content": content,
                }
            )

            continue

        # ====================================================
        # VALID SENTIMENT
        # ====================================================

        sentiment = normalized_sentiment

        classified_count += 1

        if sentiment == "Positive":

            positive_count += 1

        elif sentiment == "Negative":

            negative_count += 1

        else:

            neutral_count += 1

        if sentiment_review:
            review_count += 1

        if content_mismatch:
            mismatch_count += 1

        print(
            f"      -> SENTIMENT: {sentiment}"
        )

        print(
            "         confidence="
            + (
                f"{sentiment_confidence:.2f}"
                if sentiment_confidence is not None
                else "N/A"
            )
        )

        if sentiment_review:
            print(
                "         REVIEW = YES"
            )

        if content_mismatch:
            print(
                "         CONTENT MISMATCH = YES"
            )

        # ====================================================
        # SAVE TO CSV ONLY
        # ====================================================

        results.append(
            {
                "index":
                    index,

                "title":
                    title,

                "url":
                    url,

                "resolved_url":
                    final_url,

                "source":
                    source,

                "published_at":
                    published_at,

                "query":
                    query,

                "collection_source":
                    collection_source,

                "extraction_method":
                    extraction_method,

                "extraction_failed":
                    extraction_failed_flag,

                "extraction_review":
                    extraction_review,

                "extraction_error":
                    extraction_error,

                "extraction_error_type":
                    extraction_error_type,

                "content_length":
                    len(content),

                "summary_length":
                    len(extracted_summary),

                "relevant":
                    relevant,

                "relevance_confidence":
                    relevance_confidence,

                "relevance_reason":
                    relevance_reason,

                "relevance_model":
                    relevance_model,

                "relevance_device":
                    relevance_device,

                "relevance_error":
                    relevance_error,

                "relevance_error_type":
                    relevance_error_type,

                "sentiment":
                    sentiment,

                "sentiment_score":
                    sentiment_score,

                "sentiment_confidence":
                    sentiment_confidence,

                "sentiment_margin":
                    sentiment_margin,

                "sentiment_review":
                    sentiment_review,

                "content_mismatch":
                    content_mismatch,

                "sentiment_reason":
                    sentiment_reason,

                "sentiment_model":
                    sentiment_model,

                "sentiment_device":
                    sentiment_device,

                "sentiment_error":
                    sentiment_error,

                "sentiment_error_type":
                    sentiment_error_type,

                "classified":
                    classified,

                "elapsed_seconds":
                    round(
                        time.time()
                        - article_started,
                        3,
                    ),

                "summary":
                    extracted_summary,

                "content":
                    content,
            }
        )

    # ========================================================
    # STEP 3 - WRITE RESULTS
    # ========================================================

    print()
    print("-" * 80)
    print("STEP 3 - WRITE DRY-RUN RESULTS")
    print("-" * 80)

    try:

        write_csv(
            RESULTS_FILE,
            results,
        )

        print()
        print(
            f"Résultats : "
            f"{RESULTS_FILE}"
        )

    except Exception as exc:

        print()
        print(
            "Erreur écriture résultats CSV:"
        )

        print(exc)

    # ========================================================
    # STEP 4 - WRITE ERRORS
    # ========================================================

    try:

        write_csv(
            ERRORS_FILE,
            errors,
        )

        print(
            f"Erreurs   : "
            f"{ERRORS_FILE}"
        )

    except Exception as exc:

        print(
            "Erreur écriture erreurs CSV:"
        )

        print(exc)

    # ========================================================
    # FINAL REPORT
    # ========================================================

    elapsed = (
        time.time()
        - started_at
    )

    print()
    print("=" * 80)
    print("FINAL DRY-RUN REPORT")
    print("=" * 80)
    print()

    print(
        f"Total articles collectés : "
        f"{total_articles}"
    )

    print(
        f"Articles candidats       : "
        f"{candidates}"
    )

    print(
        f"Rejetés pre-filter       : "
        f"{rejected_prefilter}"
    )

    print()

    print(
        f"Extraction tentée        : "
        f"{extraction_attempted}"
    )

    print(
        f"Full content             : "
        f"{extraction_full_content}"
    )

    print(
        f"Summary only             : "
        f"{extraction_summary_only}"
    )

    print(
        f"Extraction failures      : "
        f"{extraction_failed}"
    )

    print()

    print(
        f"Relevant                 : "
        f"{relevant_count}"
    )

    print(
        f"Non-relevant             : "
        f"{non_relevant_count}"
    )

    print(
        f"Relevance errors         : "
        f"{relevance_errors}"
    )

    print()

    print(
        f"Articles analysés        : "
        f"{analyzed_count}"
    )

    print(
        f"Sentiments classifiés    : "
        f"{classified_count}"
    )

    print(
        f"Sentiment errors         : "
        f"{sentiment_errors}"
    )

    print()

    print(
        f"Positive                 : "
        f"{positive_count}"
    )

    print(
        f"Neutral                  : "
        f"{neutral_count}"
    )

    print(
        f"Negative                 : "
        f"{negative_count}"
    )

    print()

    print(
        f"Review                   : "
        f"{review_count}"
    )

    print(
        f"Content mismatch         : "
        f"{mismatch_count}"
    )

    print()

    print(
        f"Erreurs pipeline         : "
        f"{processing_errors}"
    )

    print()

    print(
        f"Temps total              : "
        f"{elapsed:.2f} secondes"
    )

    if total_articles > 0:

        print(
            f"Temps moyen/article      : "
            f"{elapsed / total_articles:.2f} secondes"
        )

    print()

    # ========================================================
    # SAFETY CONFIRMATION
    # ========================================================

    print("=" * 80)
    print("IMPORTANT")
    print("=" * 80)
    print()

    print(
        "SQLite AUCUNE MODIFICATION"
    )

    print(
        "save_article() NON APPELÉ"
    )

    print(
        "Aucune donnée n'a été enregistrée "
        "dans la base."
    )

    print()

    print(
        "Les résultats sont uniquement "
        "sauvegardés dans:"
    )

    print(
        f"  {RESULTS_FILE}"
    )

    print(
        f"  {ERRORS_FILE}"
    )

    print()

    print("=" * 80)
    print("DRY-RUN TERMINÉ")
    print("=" * 80)
    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print("=" * 80)
        print("DRY-RUN INTERROMPU PAR L'UTILISATEUR")
        print("=" * 80)
        print("SQLite AUCUNE MODIFICATION")
        print("Les résultats déjà écrits dans les CSV sont conservés.")
        print("=" * 80)