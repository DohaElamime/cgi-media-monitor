# test_google_news_v3.py

import csv
import time
from pathlib import Path

from modules.google_news_enricher_v3 import enrich_article


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "google_news_v2_results.csv"

OUTPUT_FILE = BASE_DIR / "google_news_v3_results.csv"

OUTPUT_ERRORS = BASE_DIR / "google_news_v3_errors.csv"


# ============================================================
# CSV - LECTURE
# ============================================================

def read_csv(path):
    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        return list(csv.DictReader(f))


# ============================================================
# CSV - ÉCRITURE
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

    fieldnames = []

    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with open(
        path,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("GOOGLE NEWS V3 - TEST D'ENRICHISSEMENT")
    print("=" * 70)
    print()

    # --------------------------------------------------------
    # Vérification fichier entrée
    # --------------------------------------------------------

    if not INPUT_FILE.exists():

        print("[ERREUR] Fichier introuvable :")
        print(INPUT_FILE)
        print()

        return

    # --------------------------------------------------------
    # Lecture
    # --------------------------------------------------------

    rows = read_csv(INPUT_FILE)

    if not rows:

        print("[ERREUR] Le fichier CSV est vide.")
        return

    print(
        f"Articles dans V2 : {len(rows)}"
    )

    print()

    # --------------------------------------------------------
    # Résultats
    # --------------------------------------------------------

    results = []
    errors = []

    relevant_total = 0

    content_success = 0
    summary_only = 0
    failed = 0
    skipped = 0

    start_time = time.time()

    # ========================================================
    # TRAITEMENT
    # ========================================================

    for index, article in enumerate(
        rows,
        start=1
    ):

        title = str(
            article.get(
                "title",
                ""
            )
        ).strip()

        relevant = str(
            article.get(
                "relevant",
                ""
            )
        ).strip().lower()

        print(
            f"[{index}/{len(rows)}] "
            f"{title[:100]}"
        )

        # ----------------------------------------------------
        # Article non pertinent
        # ----------------------------------------------------

        if relevant not in {
            "true",
            "1",
            "yes",
            "oui"
        }:

            result = dict(article)

            result[
                "enrichment_source"
            ] = "NOT_RELEVANT"

            result[
                "extraction_status"
            ] = "SKIPPED"

            result[
                "extraction_method"
            ] = ""

            result[
                "resolved_url"
            ] = ""

            result[
                "content"
            ] = ""

            result[
                "content_chars"
            ] = 0

            result[
                "content_words"
            ] = 0

            results.append(result)

            skipped += 1

            print(
                "    -> SKIPPED "
                "(non pertinent)"
            )

            continue

        # ----------------------------------------------------
        # Article pertinent
        # ----------------------------------------------------

        relevant_total += 1

        try:

            result = enrich_article(
                article
            )

            results.append(result)

            status = str(
                result.get(
                    "extraction_status",
                    ""
                )
            ).strip()

            method = str(
                result.get(
                    "extraction_method",
                    ""
                )
            ).strip()

            content_words = result.get(
                "content_words",
                0
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if status == "SUCCESS":

                content_success += 1

                print(
                    f"    -> SUCCESS | "
                    f"{method} | "
                    f"{content_words} mots"
                )

            # ------------------------------------------------
            # SUMMARY ONLY
            # ------------------------------------------------

            elif status == "SUMMARY_ONLY":

                summary_only += 1

                print(
                    "    -> SUMMARY_ONLY"
                )

            # ------------------------------------------------
            # FAILED
            # ------------------------------------------------

            else:

                failed += 1

                errors.append(result)

                error_text = str(
                    result.get(
                        "extraction_error",
                        ""
                    )
                ).strip()

                print(
                    "    -> FAILED | "
                    f"{error_text[:180]}"
                )

        except Exception as exc:

            failed += 1

            result = dict(article)

            result[
                "enrichment_source"
            ] = "ORIGINAL_ARTICLE_PAGE"

            result[
                "extraction_status"
            ] = "ERROR"

            result[
                "extraction_method"
            ] = ""

            result[
                "resolved_url"
            ] = ""

            result[
                "content"
            ] = ""

            result[
                "content_chars"
            ] = 0

            result[
                "content_words"
            ] = 0

            result[
                "extraction_error"
            ] = str(exc)

            results.append(result)

            errors.append(result)

            print(
                "    -> ERROR | "
                f"{str(exc)[:180]}"
            )

        # ----------------------------------------------------
        # Petite pause entre les requêtes
        # ----------------------------------------------------

        time.sleep(0.25)

    # ========================================================
    # SAUVEGARDE
    # ========================================================

    write_csv(
        OUTPUT_FILE,
        results
    )

    write_csv(
        OUTPUT_ERRORS,
        errors
    )

    # ========================================================
    # STATISTIQUES
    # ========================================================

    elapsed = (
        time.time()
        - start_time
    )

    print()
    print("=" * 70)
    print("FIN DU TEST GOOGLE NEWS V3")
    print("=" * 70)
    print()

    print("ARTICLES")
    print(
        f"Articles V2            : {len(rows)}"
    )

    print(
        f"Articles pertinents    : {relevant_total}"
    )

    print(
        f"Articles ignorés       : {skipped}"
    )

    print()

    print("EXTRACTION")

    print(
        f"Contenu complet        : "
        f"{content_success}"
    )

    print(
        f"Résumé seulement       : "
        f"{summary_only}"
    )

    print(
        f"Échecs                 : "
        f"{failed}"
    )

    print()

    print("TAUX DE RÉUSSITE")

    if relevant_total > 0:

        success_rate = (
            content_success
            / relevant_total
        ) * 100

        print(
            f"Contenu complet        : "
            f"{success_rate:.2f}%"
        )

    else:

        print(
            "Contenu complet        : N/A"
        )

    print()

    print("TEMPS")

    print(
        f"Durée totale           : "
        f"{elapsed:.1f} secondes"
    )

    if relevant_total > 0:

        print(
            f"Temps moyen/article    : "
            f"{elapsed / relevant_total:.2f} secondes"
        )

    print()

    print("FICHIERS CRÉÉS")

    print(
        f"  {OUTPUT_FILE.name}"
    )

    print(
        f"  {OUTPUT_ERRORS.name}"
    )

    print()

    print("SQLITE")
    print(
        "AUCUNE MODIFICATION"
    )

    print()

    print("=" * 70)


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":
    main()