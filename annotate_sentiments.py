
"""
CGI Media Monitor — Annotation des sentiments

Objectif:
    Construire un jeu de données fiable pour spécialiser le modèle
    de sentiment sur les articles CGI.

Sécurité:
    - NE MODIFIE PAS SQLite.
    - Les annotations sont enregistrées dans:
      data/sentiment_annotations.csv
    - Une annotation humaine est nécessaire pour considérer un article
      comme validé.

Lancement:
    streamlit run annotate_sentiments.py
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Dict

import pandas as pd
import streamlit as st

from modules.sentiment_analysis import analyze_cgi_sentiment


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "database" / "articles.db"
DATA_DIR = ROOT / "data"
ANNOTATION_PATH = DATA_DIR / "sentiment_annotations.csv"

LABELS = ["Positive", "Neutral", "Negative"]


def load_articles() -> pd.DataFrame:
    connection = sqlite3.connect(DB_PATH)

    query = """
        SELECT
            id,
            title,
            source,
            date,
            summary,
            content,
            sentiment AS existing_sentiment
        FROM articles
        WHERE relevant = 1
        ORDER BY id
    """

    frame = pd.read_sql_query(query, connection)
    connection.close()

    return frame


def load_annotations() -> pd.DataFrame:
    columns = [
        "id",
        "human_label",
        "validated",
        "model_label",
        "model_score",
        "model_confidence",
        "model_margin",
    ]

    if not ANNOTATION_PATH.exists():
        return pd.DataFrame(columns=columns)

    frame = pd.read_csv(ANNOTATION_PATH, dtype={"id": str})

    for column in columns:
        if column not in frame.columns:
            frame[column] = None

    return frame[columns]


def save_annotation(
    article_id: int,
    human_label: str,
    model_result: Dict,
) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    annotations = load_annotations()

    new_row = {
        "id": str(article_id),
        "human_label": human_label,
        "validated": True,
        "model_label": model_result.get("sentiment", ""),
        "model_score": model_result.get("score", ""),
        "model_confidence": model_result.get("confidence", ""),
        "model_margin": model_result.get("margin", ""),
    }

    annotations = annotations[
        annotations["id"].astype(str) != str(article_id)
    ]

    annotations = pd.concat(
        [
            annotations,
            pd.DataFrame([new_row]),
        ],
        ignore_index=True,
    )

    annotations.to_csv(
        ANNOTATION_PATH,
        index=False,
        encoding="utf-8-sig",
    )


def model_result(article: pd.Series) -> Dict:
    cache_key = f"sentiment_{article['id']}"

    if cache_key not in st.session_state:
        st.session_state[cache_key] = analyze_cgi_sentiment(
            title=str(article["title"] or ""),
            content=str(article["content"] or article["summary"] or ""),
        )

    return st.session_state[cache_key]


st.set_page_config(
    page_title="CGI — Annotation Sentiment",
    page_icon="📰",
    layout="wide",
)

st.title("📰 CGI Media Monitor — Annotation du sentiment")

st.info(
    "Cette interface ne modifie pas la base SQLite. "
    "Elle construit uniquement un dataset d'annotations humaines "
    "pour spécialiser le futur modèle CGI."
)

if not DB_PATH.exists():
    st.error(f"Base SQLite introuvable : {DB_PATH}")
    st.stop()

articles = load_articles()
annotations = load_annotations()

if articles.empty:
    st.warning("Aucun article pertinent trouvé.")
    st.stop()

validated_ids = set(
    annotations.loc[
        annotations["validated"] == True,
        "id",
    ].astype(str)
)

articles["validated"] = (
    articles["id"].astype(str).isin(validated_ids)
)

remaining = articles[~articles["validated"]].copy()

# ------------------------------------------------------------------
# Priorité :
# 1. articles jamais validés
# 2. garder l'ordre des IDs
# ------------------------------------------------------------------

if remaining.empty:
    st.success("Tous les articles ont été annotés.")
    st.stop()

article_index = st.number_input(
    "Article à annoter",
    min_value=0,
    max_value=len(remaining) - 1,
    value=0,
    step=1,
)

article = remaining.iloc[int(article_index)]
result = model_result(article)

# ------------------------------------------------------------------
# Progression
# ------------------------------------------------------------------

validated_count = len(validated_ids)
total_count = len(articles)
progress = validated_count / total_count if total_count else 0

st.progress(progress)

st.caption(
    f"{validated_count} / {total_count} articles validés "
    f"({progress:.1%})"
)

# ------------------------------------------------------------------
# Article
# ------------------------------------------------------------------

left, right = st.columns([2, 1])

with left:
    st.subheader(article["title"])

    metadata = []

    if article["source"]:
        metadata.append(f"Source : {article['source']}")

    if article["date"]:
        metadata.append(f"Date : {article['date']}")

    st.caption(" | ".join(metadata))

with right:
    st.metric(
        "Sentiment actuel SQLite",
        article["existing_sentiment"] or "Unknown",
    )

st.divider()

st.subheader("Contenu")

content = str(
    article["content"]
    or article["summary"]
    or ""
)

st.text_area(
    "Article",
    value=content,
    height=420,
    disabled=True,
    label_visibility="collapsed",
)

# ------------------------------------------------------------------
# IA : suggestion uniquement
# ------------------------------------------------------------------

st.divider()

st.subheader("Suggestion du modèle IA")

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric(
        "Modèle",
        "Finance CamemBERT",
    )

with m2:
    st.metric(
        "Suggestion",
        result["sentiment"],
    )

with m3:
    st.metric(
        "Score",
        f"{result['score']:.1%}",
    )

with m4:
    st.metric(
        "Confiance",
        f"{result['confidence']:.1%}",
    )

distribution = result["distribution"]

st.write(
    pd.DataFrame(
        {
            "Classe": list(distribution.keys()),
            "Probabilité": [
                round(value, 4)
                for value in distribution.values()
            ],
        }
    )
)

if result["review"]:
    st.warning(
        "Le modèle considère cet article comme incertain. "
        "La décision humaine est particulièrement importante."
    )

# ------------------------------------------------------------------
# Annotation humaine
# ------------------------------------------------------------------

st.divider()

st.subheader("Annotation humaine")

st.write(
    "Lis le titre et le contenu. "
    "Classe le sentiment exprimé à propos de la CGI."
)

with st.form("annotation_form"):
    human_label = st.radio(
        "Choisir le sentiment",
        LABELS,
        horizontal=True,
    )

    submitted = st.form_submit_button(
        "✅ Valider cet article",
        type="primary",
    )

if submitted:
    save_annotation(
        article_id=int(article["id"]),
        human_label=human_label,
        model_result=result,
    )

    st.success(
        f"Article ID {article['id']} validé comme {human_label}."
    )

    st.rerun()

# ------------------------------------------------------------------
# Instructions
# ------------------------------------------------------------------

st.divider()

st.subheader("Règle d'annotation")

st.markdown(
    """
**Positive** : le contenu présente globalement la CGI ou son activité
de manière favorable.

**Negative** : le contenu présente globalement la CGI ou son activité
de manière défavorable.

**Neutral** : le contenu rapporte principalement des faits sans
orientation positive ou négative claire envers la CGI.

Ne cherche pas des mots isolés. Prends en compte le **sens global du
contenu**.
"""
)

st.caption(
    f"Fichier d'annotations : {ANNOTATION_PATH}"
)
