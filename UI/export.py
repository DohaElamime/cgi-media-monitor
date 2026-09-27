# -*- coding: utf-8 -*-

"""
Interface d'export du CGI Media Monitor.
"""

import io

import pandas as pd
import streamlit as st


# ============================================================
# CSV
# ============================================================

def dataframe_to_csv(df):
    return df.to_csv(
        index=False,
        encoding="utf-8-sig",
    )


# ============================================================
# EXCEL
# ============================================================

def dataframe_to_excel(df):
    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="Articles",
        )

    output.seek(0)

    return output.getvalue()


# ============================================================
# EXPORT
# ============================================================

def render_export(filtered):
    """
    Affiche les boutons d'export pour les données filtrées.

    app.py appelle :
        render_export(filtered)
    """

    st.subheader("📤 Export")

    # --------------------------------------------------------
    # Vérification
    # --------------------------------------------------------

    if filtered is None:

        st.info(
            "Aucune donnée à exporter."
        )

        return

    if not isinstance(
        filtered,
        pd.DataFrame,
    ):

        st.error(
            "Les données d'export doivent être un DataFrame."
        )

        return

    if filtered.empty:

        st.info(
            "Aucun article à exporter avec les filtres actuels."
        )

        return

    # --------------------------------------------------------
    # Statistiques
    # --------------------------------------------------------

    st.write(
        f"**{len(filtered)} article(s) à exporter.**"
    )

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    try:

        csv_data = dataframe_to_csv(
            filtered
        )

        st.download_button(
            label="⬇️ Télécharger CSV",
            data=csv_data,
            file_name="cgi_media_monitor_articles.csv",
            mime="text/csv",
            use_container_width=True,
            key="export_csv",
        )

    except Exception as exc:

        st.error(
            f"Erreur export CSV : {exc}"
        )

    # --------------------------------------------------------
    # Excel
    # --------------------------------------------------------

    try:

        excel_data = dataframe_to_excel(
            filtered
        )

        st.download_button(
            label="⬇️ Télécharger Excel",
            data=excel_data,
            file_name="cgi_media_monitor_articles.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True,
            key="export_excel",
        )

    except Exception as exc:

        st.error(
            f"Erreur export Excel : {exc}"
        )