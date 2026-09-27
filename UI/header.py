"""
UI/header.py
----------------------------------------------------
Header CGI Media Monitor
"""

from datetime import datetime
import streamlit as st


def render_header():

    now = datetime.now()

    current_date = now.strftime("%d/%m/%Y")
    current_time = now.strftime("%H:%M")

    st.markdown(
        f"""
<div style="
background:white;
border-radius:18px;
padding:28px 35px;
border:1px solid #E5E7EB;
box-shadow:0 6px 18px rgba(0,0,0,.06);
margin-bottom:20px;
">

<div style="
font-size:54px;
font-weight:700;
color:#1F2937;
margin-bottom:6px;
">
🏢 CGI Media Monitor
</div>

<div style="
font-size:18px;
color:#6B7280;
margin-bottom:22px;
">
Plateforme intelligente de veille médiatique et d'analyse des sentiments
</div>

<div style="
display:flex;
justify-content:space-between;
align-items:center;
padding-top:18px;
border-top:1px solid #E5E7EB;
font-size:17px;
font-weight:600;
color:#374151;
">

<span>📅 {current_date}</span>

<span>🕒 {current_time}</span>

<span>🔄 Dernière analyse : {current_time}</span>

</div>

</div>
""",
        unsafe_allow_html=True,
    )