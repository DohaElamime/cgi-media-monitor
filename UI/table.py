"""
UI/table.py
----------------------------------------------------
Tableau interactif des articles CGI Media Monitor.
"""

import re

import pandas as pd
import streamlit as st


# ============================================================
# NETTOYAGE DU TITRE
# ============================================================

def clean_article_title(title):
    """
    Nettoie le titre provenant de Google News / RSS.

    Supprime les suffixes ajoutés par les médias.
    """

    if title is None:
        return ""

    title = str(title).strip()

    if not title:
        return ""

    patterns = [

        # Hespress
        r"\s*-\s*Hespress Français\s*-\s*Actualités du Maroc.*$",
        r"\s*-\s*Hespress Français.*$",
        r"\s*-\s*Hespress.*$",

        # Le360
        r"\s*-\s*Le360\.ma\s*$",
        r"\s*-\s*Le360\s*$",

        # LesEco
        r"\s*-\s*LesEco\.ma\s*$",
        r"\s*-\s*LesEco\s*$",

        # Médias24
        r"\s*-\s*Médias24\s*-\s*Numéro un de l'information économique marocaine.*$",
        r"\s*-\s*Medias24\s*-\s*Numéro un de l'information économique marocaine.*$",
        r"\s*-\s*Médias24.*$",
        r"\s*-\s*Medias24.*$",

        # Challenge
        r"\s*-\s*Challenge\.ma\s*$",
        r"\s*-\s*Challenge\s*$",

        # La Vie éco
        r"\s*-\s*La Vie éco\s*$",
        r"\s*-\s*La Vie eco\s*$",

        # Le Matin
        r"\s*-\s*Le Matin\.ma\s*$",
        r"\s*-\s*Le Matin\s*$",

        # L'Economiste
        r"\s*-\s*L'Économiste\s*$",
        r"\s*-\s*L’Économiste\s*$",
        r"\s*-\s*L'Economiste\s*$",

        # MAP
        r"\s*-\s*MAP\s*$",
        r"\s*-\s*Maghreb Arabe Presse\s*$",

        # Boursenews
        r"\s*-\s*Boursenews\s*$",
        r"\s*-\s*Bourse News\s*$",
    ]

    cleaned = title

    for pattern in patterns:
        cleaned = re.sub(
            pattern,
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()

    # Nettoyage espaces
    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    ).strip()

    return cleaned


# ============================================================
# RECHERCHE
# ============================================================

def normalize_for_search(text):
    """
    Prépare un texte pour la recherche.
    """

    if text is None:
        return ""

    return (
        str(text)
        .strip()
        .lower()
    )


# ============================================================
# NORMALISATION PERTINENCE
# ============================================================

def normalize_relevance(value):
    """
    Convertit les différentes représentations
    possibles de la pertinence en True / False / None.
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
# NORMALISATION CONFIANCE
# ============================================================

def normalize_confidence(value):
    """
    Normalise la confiance IA.

    La valeur retournée est comprise entre 0 et 1.

    Les valeurs absentes ou invalides restent NaN.
    Elles ne sont PAS remplacées par 0.
    """

    if value is None:
        return float("nan")

    try:

        if pd.isna(value):
            return float("nan")

    except (TypeError, ValueError):
        return float("nan")

    # Déjà numérique
    if isinstance(value, (int, float)):

        try:
            value = float(value)
        except (TypeError, ValueError):
            return float("nan")

    else:

        text = (
            str(value)
            .strip()
            .replace(",", ".")
        )

        if not text:
            return float("nan")

        # Exemple : "94%"
        if text.endswith("%"):

            try:
                value = float(
                    text[:-1].strip()
                ) / 100.0

            except (TypeError, ValueError):
                return float("nan")

        else:

            try:
                value = float(text)

            except (TypeError, ValueError):
                return float("nan")

    # Si la valeur est exprimée comme 94 au lieu de 0.94
    if value > 1.0 and value <= 100.0:
        value = value / 100.0

    # Valeur impossible
    if value < 0.0 or value > 1.0:
        return float("nan")

    return value


# ============================================================
# TABLEAU
# ============================================================

def render_table(df: pd.DataFrame):
    """
    Affiche le tableau des articles actuellement filtrés.

    Le tableau reçoit normalement uniquement les articles
    pertinents depuis app.py.

    Si des articles non pertinents arrivent malgré tout,
    ils sont correctement identifiés et leur sentiment
    n'est pas présenté comme une analyse IA.
    """

    st.subheader(
        "📰 Liste des articles"
    )

    if df.empty:

        st.info(
            "Aucun article disponible."
        )

        return

    display = df.copy()


    # ========================================================
    # TITRE PROPRE
    # ========================================================

    if "title" in display.columns:

        display["title"] = (
            display["title"]
            .fillna("")
            .astype(str)
            .map(clean_article_title)
        )


    # ========================================================
    # RECHERCHE RAPIDE
    # ========================================================

    search = st.text_input(
        "🔎 Rechercher dans les articles",
        placeholder="Titre ou source...",
        key="table_search",
    )

    if search.strip():

        search_value = normalize_for_search(
            search
        )

        title_series = (
            display["title"]
            .fillna("")
            .astype(str)
            .str.lower()
            if "title" in display.columns
            else pd.Series(
                "",
                index=display.index,
                dtype="object",
            )
        )

        source_series = (
            display["source"]
            .fillna("")
            .astype(str)
            .str.lower()
            if "source" in display.columns
            else pd.Series(
                "",
                index=display.index,
                dtype="object",
            )
        )

        mask = (
            title_series.str.contains(
                search_value,
                case=False,
                regex=False,
                na=False,
            )
            |
            source_series.str.contains(
                search_value,
                case=False,
                regex=False,
                na=False,
            )
        )

        display = display[
            mask
        ].copy()


    # ========================================================
    # PERTINENCE
    # ========================================================

    relevance_values = None

    if "relevant" in display.columns:

        relevance_values = (
            display["relevant"]
            .map(normalize_relevance)
        )

        display["relevance_display"] = (
            relevance_values.map(
                {
                    True: "🟢 Pertinent",
                    False: "⚪ Non pertinent",
                }
            )
            .fillna("🟡 Non classé")
        )


    # ========================================================
    # SENTIMENT
    # ========================================================

    if "sentiment" in display.columns:

        sentiment_values = (
            display["sentiment"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        # ----------------------------------------------------
        # NON PERTINENT
        # ----------------------------------------------------
        #
        # Un article non pertinent ne doit pas être présenté
        # comme "Neutre" simplement parce que SQLite contient
        # une valeur Neutral par défaut.
        #

        if relevance_values is not None:

            non_relevant_mask = (
                relevance_values
                .eq(False)
            )

            sentiment_values.loc[
                non_relevant_mask
            ] = ""

        display["sentiment"] = (
            sentiment_values
            .replace(
                {
                    "Positive": "🟢 Positif",
                    "Negative": "🔴 Négatif",
                    "Neutral": "🟡 Neutre",

                    "positive": "🟢 Positif",
                    "negative": "🔴 Négatif",
                    "neutral": "🟡 Neutre",

                    "Positif": "🟢 Positif",
                    "Négatif": "🔴 Négatif",
                    "Neutre": "🟡 Neutre",
                }
            )
        )

        display["sentiment"] = (
            display["sentiment"]
            .replace(
                "",
                "⚪ Non analysé",
            )
        )

    else:

        display["sentiment"] = "⚪ Non analysé"


    # ========================================================
    # THÈME
    # ========================================================

    if "theme" in display.columns:

        display["theme"] = (
            display["theme"]
            .fillna("Autres")
            .astype(str)
            .str.strip()
            .replace(
                "",
                "Autres",
            )
        )


    # ========================================================
    # DATE
    # ========================================================

    if "date" in display.columns:

        parsed_dates = pd.to_datetime(
            display["date"],
            errors="coerce",
        )

        display["date"] = (
            parsed_dates
            .dt.strftime("%d/%m/%Y")
            .fillna("-")
        )


    # ========================================================
    # COLONNES AFFICHÉES
    # ========================================================

    columns = [
        "title",
        "source",
        "relevance_display",
        "theme",
        "date",
        "sentiment",
    ]

    columns = [
        column
        for column in columns
        if column in display.columns
    ]

    display = display[
        columns
    ]


    # ========================================================
    # RENOMMAGE
    # ========================================================

    display = display.rename(
        columns={
            "title": "Titre",
            "source": "Source",
            "relevance_display": "Pertinence",
            "theme": "Thème",
            "date": "Date",
            "sentiment": "Sentiment",
        }
    )


    # ========================================================
    # CONFIGURATION DES COLONNES
    # ========================================================

    column_config = {}


    # --------------------------------------------------------
    # TITRE
    # --------------------------------------------------------

    if "Titre" in display.columns:

        column_config["Titre"] = (
            st.column_config.TextColumn(
                "Titre",
                width="large",
                help="Titre original nettoyé de l'article",
            )
        )


    # --------------------------------------------------------
    # SOURCE
    # --------------------------------------------------------

    if "Source" in display.columns:

        column_config["Source"] = (
            st.column_config.TextColumn(
                "Source",
                width="medium",
            )
        )


    # --------------------------------------------------------
    # PERTINENCE
    # --------------------------------------------------------

    if "Pertinence" in display.columns:

        column_config["Pertinence"] = (
            st.column_config.TextColumn(
                "Pertinence",
                width="small",
                help="Classification de pertinence de l'article par rapport à la CGI",
            )
        )


    # --------------------------------------------------------
    # THÈME
    # --------------------------------------------------------

    if "Thème" in display.columns:

        column_config["Thème"] = (
            st.column_config.TextColumn(
                "Thème",
                width="medium",
            )
        )


    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    if "Date" in display.columns:

        column_config["Date"] = (
            st.column_config.TextColumn(
                "Date",
                width="small",
            )
        )


    # --------------------------------------------------------
    # SENTIMENT
    # --------------------------------------------------------

    if "Sentiment" in display.columns:

        column_config["Sentiment"] = (
            st.column_config.TextColumn(
                "Sentiment",
                width="small",
                help="Sentiment calculé par l'IA à partir du contenu de l'article",
            )
        )


    # ========================================================
    # AFFICHER LE TABLEAU
    # ========================================================

    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        height=500,
        column_config=column_config,
    )


    # ========================================================
    # COMPTEUR
    # ========================================================

    st.caption(
        f"📄 {len(display)} article(s) affiché(s)"
    )