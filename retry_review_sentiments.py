import pandas as pd

from modules.sentiment_analysis import analyze_cgi_sentiment
from modules.article_extractor import extract_article


INPUT_CSV = "dryrun_sentiment_results.csv"
OUTPUT_CSV = "dryrun_review_retry.csv"


def main():

    df = pd.read_csv(INPUT_CSV)

    review_mask = (
        df["review"]
        .astype(str)
        .str.lower()
        .eq("true")
    )

    review_df = df[review_mask].copy()

    print("=" * 70)
    print("RETRY DES ARTICLES EN REVIEW")
    print("=" * 70)

    print(f"Articles à réanalyser : {len(review_df)}")

    results = []

    for i, row in review_df.iterrows():

        title = str(row.get("title") or "")
        url = str(row.get("url") or "")

        print("\n" + "-" * 70)
        print(f"Titre : {title}")

        # ---------------------------------------------------------
        # CONTENT MISMATCH
        # ---------------------------------------------------------

        if str(row.get("content_mismatch")).lower() == "true":

            print("⚠️ Content mismatch détecté")
            print("→ Nouvelle extraction...")

            try:
                content = extract_article(url)

            except Exception as e:

                print(f"❌ Extraction impossible : {e}")

                results.append({
                    "id": row.get("id"),
                    "title": title,
                    "url": url,
                    "sentiment": "REVIEW",
                    "confidence": 0,
                    "content_mismatch": True,
                    "reason": f"Extraction error: {e}",
                })

                continue

        else:

            # Pour les autres reviews, on récupère à nouveau
            # le contenu afin de refaire une analyse propre.

            try:
                content = extract_article(url)

            except Exception as e:

                print(f"❌ Extraction impossible : {e}")

                results.append({
                    "id": row.get("id"),
                    "title": title,
                    "url": url,
                    "sentiment": "REVIEW",
                    "confidence": 0,
                    "content_mismatch": False,
                    "reason": f"Extraction error: {e}",
                })

                continue

        if not content:

            print("❌ Aucun contenu")

            results.append({
                "id": row.get("id"),
                "title": title,
                "url": url,
                "sentiment": "REVIEW",
                "confidence": 0,
                "content_mismatch": True,
                "reason": "Contenu vide",
            })

            continue

        print(f"Contenu : {len(content)} caractères")

        # ---------------------------------------------------------
        # RETRY GPT-OSS
        # ---------------------------------------------------------

        try:

            result = analyze_cgi_sentiment(
                title=title,
                summary="",
                content=content,
            )

        except Exception as e:

            print(f"❌ Erreur modèle : {e}")

            results.append({
                "id": row.get("id"),
                "title": title,
                "url": url,
                "sentiment": "REVIEW",
                "confidence": 0,
                "content_mismatch": False,
                "reason": str(e),
            })

            continue

        print(f"🧠 Sentiment : {result.get('sentiment')}")
        print(f"📊 Confiance : {result.get('confidence')}")
        print(f"🔎 Review : {result.get('review')}")
        print(f"⚠️ Mismatch : {result.get('content_mismatch')}")
        print(f"💬 {result.get('reason')}")

        results.append({

            "id": row.get("id"),
            "title": title,
            "url": url,
            "sentiment": result.get("sentiment"),
            "confidence": result.get("confidence"),
            "review": result.get("review"),
            "content_mismatch": result.get("content_mismatch"),
            "reason": result.get("reason"),

        })

    # ---------------------------------------------------------
    # SAVE
    # ---------------------------------------------------------

    output = pd.DataFrame(results)

    output.to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n" + "=" * 70)
    print("FIN")
    print("=" * 70)

    print(f"Résultats sauvegardés : {OUTPUT_CSV}")

    print("\n⚠️ SQLITE : AUCUNE MODIFICATION")


if __name__ == "__main__":
    main()