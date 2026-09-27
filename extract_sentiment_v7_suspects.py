import os
import pandas as pd

# ============================================================
# CONFIGURATION
# ============================================================

AUDIT_FILE = "sentiment_v7_audit.csv"
ARTICLES_FILE = "google_news_v7_results.csv"

OUTPUT_FILE = "sentiment_v7_suspects.csv"


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("EXTRACTION DES CAS SUSPECTS - SENTIMENT V7")
    print("=" * 80)

    # --------------------------------------------------------
    # Vérification fichiers
    # --------------------------------------------------------

    if not os.path.exists(AUDIT_FILE):
        print(f"\nERREUR : fichier introuvable : {AUDIT_FILE}")
        return

    if not os.path.exists(ARTICLES_FILE):
        print(f"\nERREUR : fichier introuvable : {ARTICLES_FILE}")
        return

    # --------------------------------------------------------
    # Chargement
    # --------------------------------------------------------

    audit = pd.read_csv(
        AUDIT_FILE,
        encoding="utf-8-sig"
    )

    articles = pd.read_csv(
        ARTICLES_FILE,
        encoding="utf-8-sig"
    )

    print(f"\nAudit chargé       : {len(audit)} lignes")
    print(f"Articles chargés   : {len(articles)} lignes")

    # --------------------------------------------------------
    # Vérifications
    # --------------------------------------------------------

    required_audit = [
        "title",
        "initial_sentiment",
        "audit_sentiment",
        "audit_review",
        "decision",
        "final_sentiment"
    ]

    required_articles = [
        "title",
        "content",
        "resolved_url"
    ]

    for column in required_audit:
        if column not in audit.columns:
            print(
                f"\nERREUR : colonne absente dans audit : {column}"
            )
            return

    for column in required_articles:
        if column not in articles.columns:
            print(
                f"\nERREUR : colonne absente dans articles : {column}"
            )
            return

    # --------------------------------------------------------
    # Identification des suspects
    # --------------------------------------------------------

    # 1. Tous les REVIEW_HUMAN
    review_mask = (
        audit["decision"].astype(str).str.strip()
        == "REVIEW_HUMAN"
    )

    # 2. Tous les désaccords
    disagreement_mask = (
        audit["agreement"].astype(str).str.lower()
        == "false"
    )

    suspects = audit[
        review_mask | disagreement_mask
    ].copy()

    # --------------------------------------------------------
    # Suppression des doublons
    # --------------------------------------------------------

    suspects = suspects.drop_duplicates(
        subset=["title"]
    ).copy()

    print(
        f"\nCas REVIEW_HUMAN       : "
        f"{review_mask.sum()}"
    )

    print(
        f"Désaccords             : "
        f"{disagreement_mask.sum()}"
    )

    print(
        f"Cas suspects uniques   : "
        f"{len(suspects)}"
    )

    # --------------------------------------------------------
    # Jointure avec le contenu complet
    # --------------------------------------------------------

    # On récupère uniquement les colonnes utiles
    article_data = articles[
        [
            "title",
            "source",
            "date",
            "google_news_url",
            "resolved_url",
            "content",
            "content_chars",
            "content_words",
            "extraction_method",
            "extraction_status"
        ]
    ].copy()

    # Protection contre les titres dupliqués :
    # on garde la première occurrence
    article_data = article_data.drop_duplicates(
        subset=["title"]
    )

    suspects = suspects.merge(
        article_data,
        on="title",
        how="left",
        suffixes=("_audit", "_article")
    )

    # --------------------------------------------------------
    # Source du contenu
    # --------------------------------------------------------

    suspects["content_available"] = (
        suspects["content"]
        .fillna("")
        .astype(str)
        .str.strip()
        .ne("")
    )

    # --------------------------------------------------------
    # Classification du type de suspect
    # --------------------------------------------------------

    def classify(row):

        disagreement = str(
            row.get("agreement", "")
        ).lower() == "false"

        review = (
            str(row.get("decision", "")).strip()
            == "REVIEW_HUMAN"
        )

        if disagreement and review:
            return "DISAGREEMENT_AND_REVIEW"

        if disagreement:
            return "DISAGREEMENT"

        if review:
            return "REVIEW_HUMAN"

        return "OTHER"

    suspects["suspect_type"] = suspects.apply(
        classify,
        axis=1
    )

    # --------------------------------------------------------
    # Ordre des colonnes
    # --------------------------------------------------------

    columns = [
        "suspect_type",

        "title",
        "source",
        "date",

        "initial_sentiment",
        "audit_sentiment",
        "audit_confidence",
        "audit_review",

        "agreement",
        "decision",
        "final_sentiment",

        "audit_reason",

        "resolved_url",
        "google_news_url",

        "content_available",
        "content_chars",
        "content_words",
        "extraction_method",
        "extraction_status",

        "content"
    ]

    # Garder seulement les colonnes présentes
    columns = [
        column
        for column in columns
        if column in suspects.columns
    ]

    suspects = suspects[columns]

    # --------------------------------------------------------
    # Sauvegarde
    # --------------------------------------------------------

    suspects.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # Statistiques
    # --------------------------------------------------------

    with_content = suspects[
        "content_available"
    ].sum()

    without_content = (
        len(suspects) - with_content
    )

    print("\n" + "=" * 80)
    print("EXTRACTION TERMINÉE")
    print("=" * 80)

    print(
        f"\nCas suspects            : "
        f"{len(suspects)}"
    )

    print(
        f"Contenu disponible      : "
        f"{with_content}"
    )

    print(
        f"Contenu absent          : "
        f"{without_content}"
    )

    print("\nTYPES")

    print(
        suspects["suspect_type"]
        .value_counts()
        .to_string()
    )

    print(
        f"\nFichier créé : "
        f"{os.path.abspath(OUTPUT_FILE)}"
    )

    print("\nSQLite                  : AUCUNE MODIFICATION")
    print("GPT-OSS                  : NON UTILISÉ")
    print("=" * 80)


if __name__ == "__main__":
    main()