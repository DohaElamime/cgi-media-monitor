# audit_google_news_data_quality.py

import csv
from pathlib import Path
from collections import Counter


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "google_news_v2_results.csv"

OUTPUT_REPORT = (
    BASE_DIR / "google_news_v2_data_quality_report.csv"
)

OUTPUT_NEEDS_ENRICHMENT = (
    BASE_DIR / "google_news_v2_needs_enrichment.csv"
)

OUTPUT_DATA_QUALITY = (
    BASE_DIR / "google_news_v2_data_quality.csv"
)


# ============================================================
# SEUILS
# ============================================================

MIN_SUMMARY_CHARS = 80
MIN_SUMMARY_WORDS = 12

MIN_CONTENT_CHARS = 250
MIN_CONTENT_WORDS = 45


# ============================================================
# LECTURE CSV
# ============================================================

def read_csv(path):

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        return list(
            csv.DictReader(f)
        )


# ============================================================
# ÉCRITURE CSV
# ============================================================

def write_csv(path, rows):

    if not rows:

        with open(
            path,
            "w",
            encoding="utf-8-sig",
            newline=""
        ) as f:

            f.write("")

        return

    fields = []

    for row in rows:

        for key in row:

            if key not in fields:

                fields.append(key)

    with open(
        path,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# UTILITAIRES
# ============================================================

def clean(value):

    return str(
        value or ""
    ).strip()


def word_count(text):

    text = clean(text)

    if not text:

        return 0

    return len(
        text.split()
    )


def is_real_summary(summary, title):

    summary = clean(summary)
    title = clean(title)

    if not summary:

        return False

    if len(summary) < MIN_SUMMARY_CHARS:

        return False

    if word_count(summary) < MIN_SUMMARY_WORDS:

        return False

    # Résumé pratiquement identique au titre
    if title and summary.lower() == title.lower():

        return False

    # Résumé très court comparé au titre
    if (
        title
        and len(summary) <= len(title) + 20
    ):

        return False

    return True


def is_full_content(content):

    content = clean(content)

    if not content:

        return False

    if len(content) < MIN_CONTENT_CHARS:

        return False

    if word_count(content) < MIN_CONTENT_WORDS:

        return False

    return True


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("AUDIT QUALITÉ DES DONNÉES - GOOGLE NEWS V2")
    print("=" * 70)
    print()

    if not INPUT_FILE.exists():

        print(
            "[ERREUR] Fichier introuvable :"
        )

        print(
            INPUT_FILE
        )

        return

    rows = read_csv(
        INPUT_FILE
    )

    if not rows:

        print(
            "[ERREUR] CSV vide."
        )

        return

    print(
        f"Articles dans le CSV : {len(rows)}"
    )

    print()

    # ========================================================
    # COMPTEURS
    # ========================================================

    total = len(rows)

    relevant_count = 0
    non_relevant_count = 0

    full_content_count = 0
    usable_summary_count = 0
    title_only_count = 0
    no_text_count = 0

    full_content_relevant = 0
    summary_relevant = 0
    title_only_relevant = 0
    no_text_relevant = 0

    neutral_review_count = 0
    content_mismatch_count = 0

    sentiment_counts = Counter()
    review_counts = Counter()

    input_modes = Counter()
    collection_sources = Counter()
    sources = Counter()

    needs_enrichment = []

    quality_rows = []

    # ========================================================
    # ANALYSE
    # ========================================================

    for row in rows:

        title = clean(
            row.get("title")
        )

        summary = clean(
            row.get("summary")
        )

        content = clean(
            row.get("content")
        )

        sentiment = clean(
            row.get("sentiment")
        )

        review = clean(
            row.get("review")
        ).lower()

        relevant = clean(
            row.get("relevant")
        ).lower()

        input_mode = clean(
            row.get("input_mode")
        )

        collection_source = clean(
            row.get("collection_source")
        )

        source = clean(
            row.get("source")
        )

        # ----------------------------------------------------
        # RELEVANCE
        # ----------------------------------------------------

        is_relevant = relevant in {
            "true",
            "1",
            "yes",
            "oui"
        }

        if is_relevant:

            relevant_count += 1

        else:

            non_relevant_count += 1

        # ----------------------------------------------------
        # QUALITÉ DU TEXTE
        # ----------------------------------------------------

        has_content = is_full_content(
            content
        )

        has_summary = is_real_summary(
            summary,
            title
        )

        if has_content:

            text_mode = "FULL_CONTENT"

            full_content_count += 1

            if is_relevant:

                full_content_relevant += 1

        elif has_summary:

            text_mode = "RSS_SUMMARY"

            usable_summary_count += 1

            if is_relevant:

                summary_relevant += 1

        elif title:

            text_mode = "TITLE_ONLY"

            title_only_count += 1

            if is_relevant:

                title_only_relevant += 1

        else:

            text_mode = "NO_TEXT"

            no_text_count += 1

            if is_relevant:

                no_text_relevant += 1

        # ----------------------------------------------------
        # SENTIMENT
        # ----------------------------------------------------

        if is_relevant:

            sentiment_counts[
                sentiment
            ] += 1

            if (
                sentiment == "Neutral"
                and review in {
                    "true",
                    "1",
                    "yes"
                }
            ):

                neutral_review_count += 1

        # ----------------------------------------------------
        # CONTENT MISMATCH
        # ----------------------------------------------------

        mismatch = clean(
            row.get("content_mismatch")
        ).lower()

        if mismatch in {
            "true",
            "1",
            "yes"
        }:

            content_mismatch_count += 1

        # ----------------------------------------------------
        # AUTRES STATISTIQUES
        # ----------------------------------------------------

        if review in {
            "true",
            "1",
            "yes"
        }:

            review_counts[
                "REVIEW"
            ] += 1

        else:

            review_counts[
                "NO_REVIEW"
            ] += 1

        input_modes[
            input_mode or "UNKNOWN"
        ] += 1

        collection_sources[
            collection_source or "UNKNOWN"
        ] += 1

        sources[
            source or "UNKNOWN"
        ] += 1

        # ----------------------------------------------------
        # BESOIN D'ENRICHISSEMENT
        # ----------------------------------------------------

        enrichment_reason = ""

        if is_relevant:

            if text_mode == "TITLE_ONLY":

                enrichment_reason = (
                    "Article pertinent avec titre seul"
                )

            elif text_mode == "NO_TEXT":

                enrichment_reason = (
                    "Article pertinent sans texte"
                )

            elif (
                sentiment == "Neutral"
                and review in {
                    "true",
                    "1",
                    "yes"
                }
            ):

                enrichment_reason = (
                    "Neutral + Review"
                )

            if enrichment_reason:

                enriched = dict(row)

                enriched[
                    "data_quality_mode"
                ] = text_mode

                enriched[
                    "enrichment_reason"
                ] = enrichment_reason

                needs_enrichment.append(
                    enriched
                )

        # ----------------------------------------------------
        # LIGNE QUALITÉ
        # ----------------------------------------------------

        quality_row = dict(row)

        quality_row[
            "data_quality_mode"
        ] = text_mode

        quality_row[
            "summary_chars"
        ] = len(summary)

        quality_row[
            "summary_words"
        ] = word_count(summary)

        quality_row[
            "content_chars"
        ] = len(content)

        quality_row[
            "content_words"
        ] = word_count(content)

        quality_row[
            "usable_summary"
        ] = has_summary

        quality_row[
            "usable_full_content"
        ] = has_content

        quality_rows.append(
            quality_row
        )

    # ========================================================
    # RAPPORT CONSOLE
    # ========================================================

    print("=" * 70)
    print("VOLUME")
    print("=" * 70)

    print(
        f"Articles total          : {total}"
    )

    print(
        f"Articles pertinents     : "
        f"{relevant_count}"
    )

    print(
        f"Articles non pertinents : "
        f"{non_relevant_count}"
    )

    print()

    print("=" * 70)
    print("QUALITÉ DU TEXTE")
    print("=" * 70)

    print(
        f"Contenu complet         : "
        f"{full_content_count}"
    )

    print(
        f"Résumé exploitable      : "
        f"{usable_summary_count}"
    )

    print(
        f"Titre seulement        : "
        f"{title_only_count}"
    )

    print(
        f"Aucun texte             : "
        f"{no_text_count}"
    )

    print()

    print("POUR LES ARTICLES PERTINENTS")

    print(
        f"Contenu complet         : "
        f"{full_content_relevant}"
    )

    print(
        f"Résumé exploitable      : "
        f"{summary_relevant}"
    )

    print(
        f"Titre seulement        : "
        f"{title_only_relevant}"
    )

    print(
        f"Aucun texte             : "
        f"{no_text_relevant}"
    )

    print()

    print("=" * 70)
    print("SENTIMENT")
    print("=" * 70)

    print(
        f"Positive                : "
        f"{sentiment_counts['Positive']}"
    )

    print(
        f"Neutral                 : "
        f"{sentiment_counts['Neutral']}"
    )

    print(
        f"Negative               : "
        f"{sentiment_counts['Negative']}"
    )

    print(
        f"Neutral + Review       : "
        f"{neutral_review_count}"
    )

    print(
        f"Content mismatch       : "
        f"{content_mismatch_count}"
    )

    print()

    print("=" * 70)
    print("REVIEW")
    print("=" * 70)

    print(
        f"Review                  : "
        f"{review_counts['REVIEW']}"
    )

    print(
        f"Sans Review             : "
        f"{review_counts['NO_REVIEW']}"
    )

    print()

    print("=" * 70)
    print("BESOIN D'ENRICHISSEMENT")
    print("=" * 70)

    print(
        f"Articles à enrichir    : "
        f"{len(needs_enrichment)}"
    )

    print()

    print("=" * 70)
    print("MODE D'ENTRÉE")
    print("=" * 70)

    for key, value in input_modes.most_common():

        print(
            f"{key:<30} : {value}"
        )

    print()

    print("=" * 70)
    print("SOURCE DE COLLECTE")
    print("=" * 70)

    for key, value in collection_sources.most_common():

        print(
            f"{key:<30} : {value}"
        )

    print()

    print("=" * 70)
    print("TOP SOURCES")
    print("=" * 70)

    for key, value in sources.most_common(15):

        print(
            f"{key:<35} : {value}"
        )

    print()

    # ========================================================
    # SAUVEGARDE
    # ========================================================

    write_csv(
        OUTPUT_REPORT,
        [
            {
                "metric": "total_articles",
                "value": total
            },
            {
                "metric": "relevant_articles",
                "value": relevant_count
            },
            {
                "metric": "non_relevant_articles",
                "value": non_relevant_count
            },
            {
                "metric": "full_content",
                "value": full_content_count
            },
            {
                "metric": "usable_summary",
                "value": usable_summary_count
            },
            {
                "metric": "title_only",
                "value": title_only_count
            },
            {
                "metric": "no_text",
                "value": no_text_count
            },
            {
                "metric": "full_content_relevant",
                "value": full_content_relevant
            },
            {
                "metric": "summary_relevant",
                "value": summary_relevant
            },
            {
                "metric": "title_only_relevant",
                "value": title_only_relevant
            },
            {
                "metric": "no_text_relevant",
                "value": no_text_relevant
            },
            {
                "metric": "neutral_review",
                "value": neutral_review_count
            },
            {
                "metric": "content_mismatch",
                "value": content_mismatch_count
            },
            {
                "metric": "needs_enrichment",
                "value": len(needs_enrichment)
            }
        ]
    )

    write_csv(
        OUTPUT_NEEDS_ENRICHMENT,
        needs_enrichment
    )

    write_csv(
        OUTPUT_DATA_QUALITY,
        quality_rows
    )

    # ========================================================
    # FIN
    # ========================================================

    print("=" * 70)
    print("FICHIERS CRÉÉS")
    print("=" * 70)

    print(
        OUTPUT_REPORT.name
    )

    print(
        OUTPUT_NEEDS_ENRICHMENT.name
    )

    print(
        OUTPUT_DATA_QUALITY.name
    )

    print()

    print("=" * 70)
    print("SQLITE")
    print("=" * 70)

    print(
        "AUCUNE MODIFICATION"
    )

    print()

    print("=" * 70)


if __name__ == "__main__":
    main()