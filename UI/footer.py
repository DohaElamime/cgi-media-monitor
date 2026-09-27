"""
UI/footer.py
----------------------------------------------------
Footer du dashboard CGI Media Monitor.
"""

from datetime import datetime
import streamlit as st


def render_footer():
    """
    Affiche le pied de page.
    """

    current_year = datetime.now().year

    st.divider()

    st.markdown(
        """
        <div style="
            text-align:center;
            color:#6b7280;
            font-size:15px;
            line-height:1.8;
        ">

        <b>🏢 CGI Media Monitor</b><br>

        Plateforme intelligente de veille médiatique assistée par Intelligence Artificielle.

        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        f"""
        <div style="
            text-align:center;
            color:#9ca3af;
            font-size:13px;
            border-top:1px solid #e5e7eb;
            padding-top:12px;
        ">

        © {current_year} CGI Media Monitor

        </div>
        """,
        unsafe_allow_html=True,
    )