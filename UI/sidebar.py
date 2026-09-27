"""
UI/sidebar.py
----------------------------------------------------
Sidebar du dashboard CGI Media Monitor.
"""

from datetime import datetime, date

import pandas as pd
import streamlit as st


# ==========================================================
# DÉTECTION DU THÈME
# ==========================================================

THEME_KEYWORDS = {
    "Immobilier": [
        "immobilier",
        "logement",
        "habitat",
        "résidence",
        "residence",
        "appartement",
        "villa",
        "terrain",
        "lotissement",
        "acquéreur",
        "acquéreurs",
        "promotion immobilière",
        "promoteur",
    ],

    "Finance & Résultats": [
        "bénéfice",
        "benefice",
        "résultat",
        "resultat",
        "chiffre d'affaires",
        "revenu",
        "revenus",
        "profit",
        "financier",
        "financière",
        "finance",
        "résultats annuels",
        "bilan",
        "trésorerie",
        "dividende",
    ],

    "Projets & Programmes": [
        "projet",
        "programme",
        "chantier",
        "complexe",
        "résidences",
        "residences",
        "domaine",
        "construction",
        "développement immobilier",
    ],

    "Gouvernance & Nominations": [
        "nomination",
        "nommé",
        "nommee",
        "nommée",
        "directeur général",
        "directrice générale",
        "dga",
        "dg",
        "président",
        "présidente",
        "gouvernance",
        "conseil d'administration",
        "administrateur",
    ],

    "Stratégie & Développement": [
        "stratégie",
        "strategie",
        "développement",
        "developpement",
        "croissance",
        "expansion",
        "plan de relance",
        "vision",
        "performance",
    ],

    "Innovation & Digital": [
        "digital",
        "numérique",
        "numerique",
        "plateforme",
        "en ligne",
        "innovation",
        "innovante",
        "technologie",
        "technologique",
        "e-commerce",
        "réservation en ligne",
        "application",
        "showroom immersif",
        "simulateur",
    ],

    "Communication & Marketing": [
        "communication",
        "campagne",
        "marketing",
        "publicité",
        "promotion",
        "commercialisation",
        "lancement",
        "client",
        "clients",
        "marque",
    ],

    "RSE & Environnement": [
        "rse",
        "responsabilité sociétale",
        "environnement",
        "environnemental",
        "environnementale",
        "écologique",
        "ecologique",
        "durable",
        "durabilité",
        "climat",
        "énergie",
        "energie",
    ],

    "Partenariats": [
        "partenariat",
        "partenariats",
        "partenaire",
        "partenaires",
        "accord",
        "accords",
        "collaboration",
        "coopération",
        "cooperation",
    ],

    "Juridique & Contentieux": [
        "affaire",
        "justice",
        "tribunal",
        "procès",
        "proces",
        "sentence",
        "contentieux",
        "enquête",
        "enquetes",
        "arbitrage",
        "litige",
        "juridique",
        "condamnation",
    ],
}


THEME_ORDER = [
    "Immobilier",
    "Projets & Programmes",
    "Finance & Résultats",
    "Gouvernance & Nominations",
    "Stratégie & Développement",
    "Innovation & Digital",
    "Communication & Marketing",
    "RSE & Environnement",
    "Partenariats",
    "Juridique & Contentieux",
    "Autres",
]


# ==========================================================
# DÉTECTION DU THÈME
# ==========================================================

def detect_theme(row) -> str:
    """
    Détermine un thème à partir du titre et du contenu.
    """

    title = str(
        row.get("title", "") or ""
    )

    content = str(
        row.get("content", "") or ""
    )

    text = (
        f"{title} {content}"
        .lower()
    )

    scores = {}

    for theme, keywords in THEME_KEYWORDS.items():

        score = 0

        for keyword in keywords:

            keyword_lower = keyword.lower()

            if keyword_lower in text:

                # Le titre est plus important que le contenu.
                if keyword_lower in title.lower():
                    score += 3
                else:
                    score += 1

        scores[theme] = score

    best_theme = max(
        scores,
        key=scores.get,
    )

    if scores[best_theme] == 0:
        return "Autres"

    return best_theme


# ==========================================================
# AJOUT TEMPORAIRE DU THÈME
# ==========================================================

def ensure_theme_column(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Garantit que le DataFrame possède une colonne theme.

    Si la DB ne possède pas encore cette colonne,
    elle est calculée automatiquement.
    """

    result = df.copy()

    if "theme" not in result.columns:

        result["theme"] = result.apply(
            detect_theme,
            axis=1,
        )

    else:

        result["theme"] = (
            result["theme"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        missing = (
            result["theme"] == ""
        )

        if missing.any():

            result.loc[
                missing,
                "theme",
            ] = result.loc[
                missing
            ].apply(
                detect_theme,
                axis=1,
            )

    return result


# ==========================================================
# NORMALISATION PERTINENCE
# ==========================================================

def normalize_relevance_column(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normalise la colonne relevant afin de garantir
    un comportement stable avec SQLite / Pandas.
    """

    result = df.copy()

    if "relevant" not in result.columns:
        return result

    result["relevant"] = pd.to_numeric(
        result["relevant"],
        errors="coerce",
    )

    return result


# ==========================================================
# SIDEBAR
# ==========================================================

def render_sidebar(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Affiche la sidebar et retourne les données filtrées.

    Le DataFrame peut contenir tous les articles.

    La pertinence CGI est un filtre utilisateur,
    et non une restriction imposée par app.py.
    """

    filtered = df.copy()

    # ======================================================
    # NORMALISATION
    # ======================================================

    filtered = normalize_relevance_column(
        filtered
    )

    filtered = ensure_theme_column(
        filtered
    )

    # ======================================================
    # LOGO
    # ======================================================

    st.sidebar.image(
        "assets/logo_cgi.png",
        width=110,
    )

    st.sidebar.markdown(
        """
        <h2 style="margin-bottom:0;">
        🏢 CGI Media Monitor
        </h2>

        <p style="color:gray;font-size:14px;">
        Veille médiatique intelligente
        </p>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.success(
        "🟢 Surveillance active"
    )

    st.sidebar.caption(
        f"Dernière mise à jour : "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    st.sidebar.divider()

    # ======================================================
    # PERTINENCE CGI
    # ======================================================

    if "relevant" in filtered.columns:

        with st.sidebar.expander(
            "🎯 Pertinence CGI",
            expanded=True,
        ):

            relevance_options = [
                "Tous",
                "Pertinents",
                "Non pertinents",
            ]

            relevance_filter = st.selectbox(
                "Pertinence",
                relevance_options,
                label_visibility="collapsed",
                key="sidebar_relevance",
            )

        if relevance_filter == "Pertinents":

            filtered = filtered[
                filtered["relevant"] == 1
            ].copy()

        elif relevance_filter == "Non pertinents":

            filtered = filtered[
                filtered["relevant"] == 0
            ].copy()

    else:

        st.sidebar.caption(
            "⚠️ Colonne 'relevant' absente de la base."
        )

    # ======================================================
    # RECHERCHE
    # ======================================================

    with st.sidebar.expander(
        "🔍 Recherche",
        expanded=True,
    ):

        keyword = st.text_input(
            "Recherche",
            placeholder="Titre ou contenu...",
            label_visibility="collapsed",
            key="sidebar_keyword",
        )

    if keyword.strip():

        keyword = (
            keyword
            .strip()
            .lower()
        )

        title = (
            filtered["title"]
            .fillna("")
            .astype(str)
            .str.lower()
            if "title" in filtered.columns
            else pd.Series(
                "",
                index=filtered.index,
                dtype="object",
            )
        )

        content = (
            filtered["content"]
            .fillna("")
            .astype(str)
            .str.lower()
            if "content" in filtered.columns
            else pd.Series(
                "",
                index=filtered.index,
                dtype="object",
            )
        )

        filtered = filtered[
            title.str.contains(
                keyword,
                na=False,
                regex=False,
            )
            |
            content.str.contains(
                keyword,
                na=False,
                regex=False,
            )
        ].copy()

    # ======================================================
    # SOURCE
    # ======================================================

    if "source" in filtered.columns:

        with st.sidebar.expander(
            "📰 Source",
            expanded=True,
        ):

            sources = sorted(
                filtered["source"]
                .dropna()
                .astype(str)
                .str.strip()
                .loc[
                    lambda s: s != ""
                ]
                .unique()
            )

            source = st.selectbox(
                "Source",
                ["Toutes"] + list(sources),
                label_visibility="collapsed",
                key="sidebar_source",
            )

        if source != "Toutes":

            filtered = filtered[
                filtered["source"]
                .fillna("")
                .astype(str)
                .str.strip()
                == source
            ].copy()

    # ======================================================
    # SENTIMENT
    # ======================================================

    if "sentiment" in filtered.columns:

        with st.sidebar.expander(
            "😊 Sentiment",
            expanded=True,
        ):

            sentiments = sorted(
                filtered["sentiment"]
                .dropna()
                .astype(str)
                .str.strip()
                .loc[
                    lambda s: s != ""
                ]
                .unique()
            )

            sentiment = st.selectbox(
                "Sentiment",
                ["Tous"] + list(sentiments),
                label_visibility="collapsed",
                key="sidebar_sentiment",
            )

        if sentiment != "Tous":

            filtered = filtered[
                filtered["sentiment"]
                .fillna("")
                .astype(str)
                .str.strip()
                == sentiment
            ].copy()

    # ======================================================
    # THÈME
    # ======================================================

    if "theme" in filtered.columns:

        with st.sidebar.expander(
            "🏷️ Thème",
            expanded=True,
        ):

            available_themes = []

            for theme in THEME_ORDER:

                if theme in filtered["theme"].values:

                    available_themes.append(
                        theme
                    )

            theme = st.selectbox(
                "Thème",
                ["Tous"] + available_themes,
                label_visibility="collapsed",
                key="sidebar_theme",
            )

        if theme != "Tous":

            filtered = filtered[
                filtered["theme"] == theme
            ].copy()

    # ======================================================
    # PÉRIODE
    # ======================================================

    if "date" in filtered.columns:

        with st.sidebar.expander(
            "📅 Période",
            expanded=True,
        ):

            dates = pd.to_datetime(
                filtered["date"],
                errors="coerce",
                utc=True,
            ).dt.tz_localize(None)

            valid_dates = dates.dropna()

            if valid_dates.empty:

                st.caption(
                    "ℹ️ Aucune date exploitable."
                )

            else:

                min_date = valid_dates.min().date()
                max_date = valid_dates.max().date()

                use_date_filter = st.checkbox(
                    "Activer le filtre de période",
                    value=False,
                    key="sidebar_use_date_filter",
                )

                if use_date_filter:

                    # --------------------------------------------------
                    # Gestion du Session State
                    # --------------------------------------------------

                    state_key = (
                        "sidebar_date_range"
                    )

                    existing_range = (
                        st.session_state.get(
                            state_key
                        )
                    )

                    def _to_date(value):

                        if isinstance(
                            value,
                            datetime,
                        ):
                            return value.date()

                        if isinstance(
                            value,
                            date,
                        ):
                            return value

                        return None

                    valid_existing = False

                    normalized_range = (
                        min_date,
                        max_date,
                    )

                    if (
                        isinstance(
                            existing_range,
                            (tuple, list),
                        )
                        and len(existing_range) == 2
                    ):

                        old_start = _to_date(
                            existing_range[0]
                        )

                        old_end = _to_date(
                            existing_range[1]
                        )

                        if (
                            old_start is not None
                            and old_end is not None
                        ):

                            start_date = max(
                                min_date,
                                min(
                                    old_start,
                                    max_date,
                                ),
                            )

                            end_date = max(
                                min_date,
                                min(
                                    old_end,
                                    max_date,
                                ),
                            )

                            if start_date <= end_date:

                                normalized_range = (
                                    start_date,
                                    end_date,
                                )

                                valid_existing = (
                                    start_date
                                    == old_start
                                    and
                                    end_date
                                    == old_end
                                )

                    # --------------------------------------------------
                    # Supprimer une valeur invalide
                    # --------------------------------------------------

                    if (
                        existing_range is not None
                        and not valid_existing
                    ):

                        st.session_state.pop(
                            state_key,
                            None,
                        )

                                        # --------------------------------------------------
                    # Création du widget
                    # --------------------------------------------------

                    if valid_existing:

                        date_range = st.date_input(
                            "Sélectionner une période",
                            min_value=min_date,
                            max_value=max_date,
                            format="DD/MM/YYYY",
                            label_visibility="collapsed",
                            key=state_key,
                        )

                    else:

                        date_range = st.date_input(
                            "Sélectionner une période",
                            value=normalized_range,
                            min_value=min_date,
                            max_value=max_date,
                            format="DD/MM/YYYY",
                            label_visibility="collapsed",
                            key=state_key,
                        )

                    # --------------------------------------------------
                    # APPLICATION DU FILTRE
                    # --------------------------------------------------

                    if (
                        isinstance(
                            date_range,
                            tuple,
                        )
                        and len(date_range) == 2
                    ):

                        start_date, end_date = (
                            date_range
                        )

                        mask = (
                            dates.notna()
                            & (
                                dates.dt.date
                                >= start_date
                            )
                            & (
                                dates.dt.date
                                <= end_date
                            )
                        )

                        filtered = filtered[
                            mask
                        ].copy()

                    elif isinstance(
                        date_range,
                        (date, datetime),
                    ):

                        selected_date = _to_date(
                            date_range
                        )

                        if selected_date is not None:

                            mask = (
                                dates.notna()
                                & (
                                    dates.dt.date
                                    == selected_date
                                )
                            )

                            filtered = filtered[
                                mask
                            ].copy()

    # ======================================================
    # RÉSULTAT
    # ======================================================

    st.sidebar.divider()

    total_articles = len(df)

    if "relevant" in df.columns:

        total_relevant = int(
            (
                df["relevant"] == 1
            ).sum()
        )

        total_non_relevant = int(
            (
                df["relevant"] == 0
            ).sum()
        )

        total_unknown = int(
            df["relevant"].isna().sum()
        )

    else:

        total_relevant = 0
        total_non_relevant = 0
        total_unknown = 0

    st.sidebar.metric(
        "Articles affichés",
        len(filtered),
    )

    st.sidebar.caption(
        f"Base : {total_articles} articles"
    )

    if "relevant" in df.columns:

        st.sidebar.caption(
            f"Pertinents : {total_relevant} • "
            f"Non pertinents : {total_non_relevant}"
        )

        if total_unknown > 0:

            st.sidebar.caption(
                f"Sans classification : {total_unknown}"
            )

    # ======================================================
    # ACTIONS
    # ======================================================

    st.sidebar.subheader(
        "⚙️ Actions"
    )

    if st.sidebar.button(
        "♻️ Réinitialiser les filtres",
        width="stretch",
        key="reset_sidebar_filters",
    ):

        for key in (
            "sidebar_keyword",
            "sidebar_relevance",
            "sidebar_source",
            "sidebar_sentiment",
            "sidebar_theme",
            "sidebar_use_date_filter",
            "sidebar_date_range",
        ):

            st.session_state.pop(
                key,
                None,
            )

        st.rerun()

    # ======================================================
    # VERSION
    # ======================================================

    st.sidebar.caption(
        "Version 3.1.0"
    )

    # ======================================================
    # RETOURNER LE DATAFRAME
    # ======================================================

    return filtered