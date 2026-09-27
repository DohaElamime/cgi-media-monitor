"""
UI/charts.py
----------------------------------------------------
Graphiques du dashboard CGI Media Monitor.

Les graphiques d'analyse média utilisent uniquement les articles
pertinents CGI. Le DataFrame reçu peut toutefois contenir tous les
articles lorsque le dashboard est configuré sur "Pertinence = Tous".

Dans ce cas :
    - les métriques et le tableau peuvent afficher tous les articles ;
    - les graphiques de sentiment restent basés uniquement sur
      les articles pertinents ;
    - les articles non pertinents ne sont jamais comptés comme
      "Neutres" artificiellement.

Important :
    - confidence       = confiance du classifieur de pertinence
    - sentiment_score  = score associé à l'analyse de sentiment

Le score de sentiment nul (0.0) est considéré comme
"non disponible" et n'entre pas dans les moyennes.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st


# ============================================================
# COULEURS
# ============================================================

COLORS = {
    "Positive": "#16A34A",
    "Negative": "#DC2626",
    "Neutral": "#EAB308",
    "Unknown": "#9CA3AF",
}


SENTIMENT_ORDER = [
    "Negative",
    "Neutral",
    "Positive",
]


# ============================================================
# NORMALISATION
# ============================================================

def _normalize_relevance(value):
    """
    Convertit les différentes représentations de la pertinence
    en True / False / None.
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


def _normalize_sentiment(series: pd.Series) -> pd.Series:
    """
    Normalise les libellés de sentiment.
    """

    normalized = (
        series
        .fillna("")
        .astype(str)
        .str.strip()
    )

    normalized = normalized.replace(
        {
            "positive": "Positive",
            "positif": "Positive",
            "Positif": "Positive",

            "negative": "Negative",
            "negatif": "Negative",
            "négatif": "Negative",
            "Négatif": "Negative",

            "neutral": "Neutral",
            "neutre": "Neutral",
            "Neutre": "Neutral",
        }
    )

    normalized.loc[
        normalized.eq("")
    ] = "Neutral"

    normalized.loc[
        normalized.eq("Unknown")
    ] = "Neutral"

    return normalized


# ============================================================
# RENDER CHARTS
# ============================================================

def render_charts(df: pd.DataFrame):
    """
    Affiche les graphiques principaux du dashboard.

    Le DataFrame reçu est normalement déjà filtré par le sidebar.

    IMPORTANT :
    On ne filtre plus directement df avec :
        df["relevant"] == 1

    car le dashboard peut maintenant être "dégelé" et afficher
    les 202 articles. On construit donc un sous-ensemble local
    d'articles pertinents uniquement pour les analyses de sentiment.

    Ainsi :
        - Pertinence = Tous -> les graphiques utilisent les 99 pertinents
        - Pertinence = Pertinents -> les graphiques utilisent les articles affichés
        - Pertinence = Non pertinents -> les graphiques indiquent qu'aucune
          analyse de sentiment CGI n'est disponible.
    """

    st.subheader(
        "📊 Analyse des articles"
    )

    # ========================================================
    # VÉRIFICATION DES DONNÉES
    # ========================================================

    if df is None or df.empty:

        st.info(
            "Aucune donnée disponible."
        )

        return

    dashboard_df = df.copy()

    # ========================================================
    # IDENTIFICATION DES ARTICLES PERTINENTS
    # ========================================================

    if "relevant" in dashboard_df.columns:

        relevance_values = (
            dashboard_df["relevant"]
            .map(_normalize_relevance)
        )

        relevant_mask = (
            relevance_values
            .eq(True)
        )

        relevant_df = dashboard_df.loc[
            relevant_mask
        ].copy()

    else:

        relevant_df = dashboard_df.copy()

    # ========================================================
    # AUCUN ARTICLE PERTINENT
    # ========================================================

    if relevant_df.empty:

        st.info(
            "Aucun article pertinent disponible "
            "dans le filtre actuel pour produire "
            "les graphiques de sentiment CGI."
        )

        return

    # ========================================================
    # NORMALISATION DES SENTIMENTS
    # ========================================================

    if "sentiment" in relevant_df.columns:

        relevant_df["sentiment"] = (
            _normalize_sentiment(
                relevant_df["sentiment"]
            )
        )

    # ==========================================================
    # PREMIÈRE LIGNE
    # ==========================================================

    col1, col2 = st.columns(2)

    # ==========================================================
    # RÉPARTITION DES SENTIMENTS
    # ==========================================================

    with col1:

        if "sentiment" in relevant_df.columns:

            sentiment_df = (
                relevant_df["sentiment"]
                .value_counts()
                .reindex(
                    [
                        "Positive",
                        "Negative",
                        "Neutral",
                    ],
                    fill_value=0,
                )
                .reset_index()
            )

            sentiment_df.columns = [
                "Sentiment",
                "Articles",
            ]

            fig = px.pie(
                sentiment_df,
                names="Sentiment",
                values="Articles",
                hole=0.60,
                color="Sentiment",
                color_discrete_map=COLORS,
            )

            fig.update_traces(
                textposition="inside",
                textinfo="percent+label",
                pull=[
                    0.03 if value > 0 else 0
                    for value
                    in sentiment_df["Articles"]
                ],
            )

            fig.update_layout(
                title="Répartition des sentiments",
                height=420,
                margin=dict(
                    l=10,
                    r=10,
                    t=45,
                    b=10,
                ),
                showlegend=True,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )

            st.plotly_chart(
                fig,
                width="stretch",
                config={
                    "displayModeBar": False
                },
            )

    # ==========================================================
    # TOP SOURCES
    # ==========================================================

    with col2:

        if "source" in relevant_df.columns:

            source_df = (
                relevant_df["source"]
                .fillna("Inconnue")
                .astype(str)
                .str.strip()
                .replace(
                    "",
                    "Inconnue",
                )
                .value_counts()
                .head(10)
                .reset_index()
            )

            source_df.columns = [
                "Source",
                "Articles",
            ]

            fig = px.bar(
                source_df,
                x="Articles",
                y="Source",
                orientation="h",
                text="Articles",
                color="Articles",
                color_continuous_scale="Reds",
            )

            fig.update_layout(
                title="Top 10 des sources",
                height=420,
                margin=dict(
                    l=10,
                    r=10,
                    t=45,
                    b=10,
                ),
                coloraxis_showscale=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="Nombre d'articles",
                yaxis_title="",
            )

            fig.update_traces(
                textposition="outside"
            )

            fig.update_yaxes(
                categoryorder="total ascending"
            )

            st.plotly_chart(
                fig,
                width="stretch",
                config={
                    "displayModeBar": False
                },
            )

    # ==========================================================
    # DEUXIÈME LIGNE
    # ==========================================================

    col3, col4 = st.columns(2)

    # ==========================================================
    # SENTIMENTS PAR MÉDIA
    # ==========================================================

    with col3:

        if {
            "source",
            "sentiment",
        }.issubset(relevant_df.columns):

            st.subheader(
                "📰 Sentiments par média"
            )

            sentiment_source = (
                relevant_df
                .groupby(
                    [
                        "source",
                        "sentiment",
                    ]
                )
                .size()
                .reset_index(
                    name="Articles"
                )
            )

            sentiment_source["sentiment"] = (
                pd.Categorical(
                    sentiment_source["sentiment"],
                    categories=SENTIMENT_ORDER,
                    ordered=True,
                )
            )

            sentiment_source = (
                sentiment_source
                .sort_values(
                    [
                        "source",
                        "sentiment",
                    ]
                )
            )

            fig = px.bar(
                sentiment_source,
                x="source",
                y="Articles",
                color="sentiment",
                text="Articles",
                barmode="stack",
                color_discrete_map=COLORS,
                category_orders={
                    "sentiment": SENTIMENT_ORDER
                },
            )

            fig.update_layout(
                height=420,
                xaxis_title="",
                yaxis_title="Nombre d'articles",
                legend_title="",
                margin=dict(
                    l=10,
                    r=10,
                    t=45,
                    b=10,
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )

            fig.update_xaxes(
                tickangle=-30
            )

            fig.update_traces(
                textposition="inside"
            )

            st.plotly_chart(
                fig,
                width="stretch",
                config={
                    "displayModeBar": False
                },
            )

    # ==========================================================
    # SCORE MOYEN DU SENTIMENT
    # ==========================================================

    with col4:

        if {
            "sentiment",
            "sentiment_score",
        }.issubset(relevant_df.columns):

            st.subheader(
                "🤖 Score moyen du sentiment"
            )

            # --------------------------------------------------
            # Préparation des scores
            # --------------------------------------------------

            score_df = relevant_df[
                [
                    "sentiment",
                    "sentiment_score",
                ]
            ].copy()

            score_df["sentiment_score"] = pd.to_numeric(
                score_df["sentiment_score"],
                errors="coerce",
            )

            # --------------------------------------------------
            # IMPORTANT :
            # 0.0 = score non disponible dans nos corrections
            #
            # Un vrai score de sentiment doit être > 0.
            # On exclut donc :
            #   - NaN
            #   - valeurs négatives
            #   - 0.0
            # --------------------------------------------------

            score_df = score_df[
                score_df["sentiment_score"] > 0
            ].copy()

            # Sécurité : bornes du score
            score_df["sentiment_score"] = (
                score_df["sentiment_score"]
                .clip(
                    lower=0.0,
                    upper=1.0,
                )
            )

            if score_df.empty:

                st.info(
                    "Aucun score de sentiment disponible."
                )

            else:

                # --------------------------------------------------
                # Moyenne par sentiment
                # --------------------------------------------------

                confidence_df = (
                    score_df
                    .groupby(
                        "sentiment"
                    )["sentiment_score"]
                    .mean()
                    .reindex(
                        SENTIMENT_ORDER
                    )
                    .dropna()
                    .reset_index()
                )

                confidence_df.columns = [
                    "Sentiment",
                    "Score",
                ]

                # --------------------------------------------------
                # Nombre d'articles réellement utilisés
                # --------------------------------------------------

                analyzed_count = len(
                    score_df
                )

                total_relevant = len(
                    relevant_df
                )

                # --------------------------------------------------
                # Graphique
                # --------------------------------------------------

                fig = px.bar(
                    confidence_df,
                    x="Sentiment",
                    y="Score",
                    text="Score",
                    color="Sentiment",
                    color_discrete_map=COLORS,
                    category_orders={
                        "Sentiment": SENTIMENT_ORDER
                    },
                )

                fig.update_traces(
                    texttemplate="%{text:.0%}",
                    textposition="outside",
                )

                fig.update_layout(
                    height=420,
                    xaxis_title="",
                    yaxis_title="Score moyen",
                    legend_title="",
                    yaxis=dict(
                        range=[0, 1],
                        tickformat=".0%",
                    ),
                    margin=dict(
                        l=10,
                        r=10,
                        t=45,
                        b=10,
                    ),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )

                st.plotly_chart(
                    fig,
                    width="stretch",
                    config={
                        "displayModeBar": False
                    },
                )

                # --------------------------------------------------
                # Information complémentaire
                # --------------------------------------------------

                st.caption(
                    f"{analyzed_count} score(s) disponible(s) "
                    f"sur {total_relevant} article(s) pertinent(s)."
                )
