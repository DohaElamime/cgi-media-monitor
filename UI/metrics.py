"""
UI/metrics.py
----------------------------------------------------
Indicateurs clés du dashboard CGI Media Monitor.
"""

import pandas as pd
import streamlit as st


# ============================================================
# NORMALISATION DE LA PERTINENCE
# ============================================================

def normalize_relevance(value):
    """
    Convertit les différentes représentations possibles
    de la pertinence en True / False / None.
    """

    if pd.isna(value):
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):

        if value == 1:
            return True

        if value == 0:
            return False

    normalized = (
        str(value)
        .strip()
        .lower()
    )

    if normalized in {
        "1",
        "true",
        "yes",
        "oui",
        "pertinent",
        "relevant",
    }:
        return True

    if normalized in {
        "0",
        "false",
        "no",
        "non",
        "non pertinent",
        "non-relevant",
        "irrelevant",
    }:
        return False

    return None


# ============================================================
# RENDER METRICS
# ============================================================

def render_metrics(df: pd.DataFrame):
    """
    Affiche les indicateurs clés du dashboard.

    Règles :
    - Articles = articles actuellement filtrés.
    - Pertinents = articles pertinents parmi les articles affichés.
    - Positifs / Négatifs / Neutres = uniquement les articles pertinents.
    - Sources = nombre de sources distinctes.
    - Le taux de pertinence est calculé sur les articles affichés.
    """

    st.subheader("📊 Indicateurs clés")

    if df.empty:

        st.info(
            "Aucune donnée disponible."
        )

        return

    # ========================================================
    # COPIE DE TRAVAIL
    # ========================================================

    data = df.copy()


    # ========================================================
    # ARTICLES
    # ========================================================

    total_articles = len(data)


    # ========================================================
    # NORMALISATION DE LA PERTINENCE
    # ========================================================

    if "relevant" in data.columns:

        relevant_values = (
            data["relevant"]
            .map(normalize_relevance)
        )

        relevant_mask = (
            relevant_values
            .eq(True)
        )

        relevant = int(
            relevant_mask.sum()
        )

    else:

        relevant_mask = pd.Series(
            False,
            index=data.index,
        )

        relevant = 0


    # ========================================================
    # ARTICLES PERTINENTS
    # ========================================================

    relevant_df = data.loc[
        relevant_mask
    ].copy()


    # ========================================================
    # SENTIMENTS
    # ========================================================

    positives = 0
    negatives = 0
    neutrals = 0

    if (
        not relevant_df.empty
        and "sentiment" in relevant_df.columns
    ):

        sentiments = (
            relevant_df["sentiment"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )

        # ----------------------------------------------------
        # POSITIFS
        # ----------------------------------------------------

        positives = int(
            sentiments.isin(
                [
                    "positive",
                    "positif",
                ]
            ).sum()
        )

        # ----------------------------------------------------
        # NÉGATIFS
        # ----------------------------------------------------

        negatives = int(
            sentiments.isin(
                [
                    "negative",
                    "negatif",
                    "négatif",
                ]
            ).sum()
        )

        # ----------------------------------------------------
        # NEUTRES
        # ----------------------------------------------------

        neutrals = int(
            sentiments.isin(
                [
                    "neutral",
                    "neutre",
                ]
            ).sum()
        )


    # ========================================================
    # SOURCES
    # ========================================================

    if "source" in data.columns:

        sources_series = (
            data["source"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        sources_series = (
            sources_series[
                sources_series != ""
            ]
        )

        sources = int(
            sources_series.nunique()
        )

    else:

        sources = 0


    # ========================================================
    # TAUX DE PERTINENCE
    # ========================================================

    taux = (
        round(
            (relevant / total_articles) * 100,
            1,
        )
        if total_articles > 0
        else 0.0
    )


    # ========================================================
    # CARTES KPI
    # ========================================================

    cards = [

        {
            "icon": "📄",
            "title": "Articles",
            "value": total_articles,
            "color": "#2563EB",
        },

        {
            "icon": "✅",
            "title": "Pertinents",
            "value": relevant,
            "color": "#16A34A",
        },

        {
            "icon": "😊",
            "title": "Positifs",
            "value": positives,
            "color": "#22C55E",
        },

        {
            "icon": "🚨",
            "title": "Négatifs",
            "value": negatives,
            "color": "#DC2626",
        },

        {
            "icon": "😐",
            "title": "Neutres",
            "value": neutrals,
            "color": "#F59E0B",
        },

        {
            "icon": "📰",
            "title": "Sources",
            "value": sources,
            "color": "#EA580C",
        },
    ]


    # ========================================================
    # AFFICHAGE DES CARTES
    # ========================================================

    columns = st.columns(
        len(cards)
    )

    for col, card in zip(
        columns,
        cards,
    ):

        with col:

            card_html = f"""
<div style="
    background: #ffffff;
    border-radius: 16px;
    padding: 20px 12px;
    box-shadow: 0 6px 15px rgba(0, 0, 0, 0.08);
    border-top: 5px solid {card['color']};
    text-align: center;
    min-height: 180px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    box-sizing: border-box;
">

    <div style="
        font-size: 30px;
        line-height: 1.2;
        margin-bottom: 10px;
    ">
        {card['icon']}
    </div>

    <div style="
        color: #6B7280;
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 4px;
    ">
        {card['title']}
    </div>

    <div style="
        font-size: 32px;
        font-weight: 700;
        color: #111827;
        line-height: 1.2;
    ">
        {card['value']}
    </div>

</div>
"""

            # IMPORTANT :
            # st.html() rend directement le HTML.
            # Cela évite que Streamlit affiche le HTML
            # comme du texte brut.

            st.html(card_html)


    # ========================================================
    # ESPACEMENT
    # ========================================================

    st.markdown(
        "<div style='height: 12px;'></div>",
        unsafe_allow_html=True,
    )


    # ========================================================
    # BARRE DE PROGRESSION
    # ========================================================

    progress_value = min(
        max(
            taux / 100,
            0.0,
        ),
        1.0,
    )

    st.progress(
        progress_value
    )


    # ========================================================
    # TAUX DE PERTINENCE
    # ========================================================

    st.caption(
        f"🎯 Taux de pertinence des articles : **{taux}%**"
    )


    # ========================================================
    # INFORMATIONS COMPLÉMENTAIRES
    # ========================================================

    if relevant > 0:

        sentiment_total = (
            positives
            + negatives
            + neutrals
        )

        if sentiment_total > 0:

            st.caption(
                "📌 Analyse du sentiment calculée "
                "uniquement sur les articles pertinents."
            )