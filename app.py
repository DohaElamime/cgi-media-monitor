import pandas as pd
import streamlit as st

from modules.database import get_articles

from UI.style import load_css
from UI.header import render_header
from UI.sidebar import render_sidebar
from UI.metrics import render_metrics
from UI.charts import render_charts
from UI.table import render_table
from UI.details import render_details
from UI.export import render_export
from UI.footer import render_footer


# ============================================================
# CHARGER LES ARTICLES
# ============================================================

articles = get_articles()

df = pd.DataFrame(articles)


# ============================================================
# CSS
# ============================================================

load_css()


# ============================================================
# HEADER
# ============================================================

render_header()


# ============================================================
# VÉRIFICATION DES DONNÉES
# ============================================================

if df.empty:

    st.warning(
        "Aucun article disponible dans la base de données."
    )

    render_footer()

else:

    # ========================================================
    # FILTRE PRINCIPAL
    # ========================================================
    #
    # Le dashboard affiche UNIQUEMENT les articles pertinents.
    #
    # Les articles non pertinents restent dans SQLite,
    # mais ne sont pas affichés dans le dashboard.
    #
    # ========================================================

    relevant_values = (
        df["relevant"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    dashboard_df = df[
        relevant_values.isin(["1", "true", "yes"])
    ].copy()


    # ========================================================
    # SI AUCUN ARTICLE PERTINENT
    # ========================================================

    if dashboard_df.empty:

        st.info(
            "Aucun article pertinent disponible."
        )

        render_footer()

    else:

        # ====================================================
        # SIDEBAR
        # ====================================================

        filtered = render_sidebar(
            dashboard_df
        )


        # ====================================================
        # SÉCURITÉ
        # ====================================================

        if filtered is None:

            filtered = dashboard_df.copy()


        # ====================================================
        # KPIs
        # ====================================================

        render_metrics(
            filtered
        )


        # ====================================================
        # GRAPHIQUES
        # ====================================================

        render_charts(
            filtered
        )


        # ====================================================
        # TABLEAU
        # ====================================================

        render_table(
            filtered
        )


        # ====================================================
        # DÉTAILS
        # ====================================================

        render_details(
            filtered
        )


        # ====================================================
        # EXPORT
        # ====================================================

        render_export(
            filtered
        )


        # ====================================================
        # FOOTER
        # ====================================================

        render_footer()