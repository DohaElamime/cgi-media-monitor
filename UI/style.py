"""
UI/style.py
----------------------------------------------------
Thème graphique CGI Media Monitor
"""

import streamlit as st


def load_css():

    st.markdown(
        """
<style>

/* ==========================================================
   IMPORT
========================================================== */

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');


/* ==========================================================
   GLOBAL
========================================================== */

html,
body,
.stApp{

    font-family:'Inter',sans-serif;
    background:#F5F7FA;

}


/* ==========================================================
   PAGE
========================================================== */

.block-container{

    max-width:1500px;

    padding-top:0.8rem;

    padding-bottom:1rem;

    padding-left:2rem;

    padding-right:2rem;

}


/* ==========================================================
   ESPACEMENT
========================================================== */

div[data-testid="stVerticalBlock"]{

    gap:0.8rem;

}


/* ==========================================================
   TITRES
========================================================== */

h1{

    color:#1F2937;

    font-size:3rem;

    font-weight:700;

    margin:0;

}

h2{

    color:#1F2937;

    font-weight:700;

}

h3{

    color:#374151;

}


/* ==========================================================
   SIDEBAR
========================================================== */

section[data-testid="stSidebar"]{

    background:white;

    border-right:1px solid #E5E7EB;

    box-shadow:3px 0 12px rgba(0,0,0,.04);

}

section[data-testid="stSidebar"] img{

    border-radius:10px;

}


/* ==========================================================
   INPUTS
========================================================== */

.stTextInput input,
.stSelectbox div[data-baseweb="select"],
.stDateInput input{

    border-radius:10px;

}


/* ==========================================================
   KPI
========================================================== */

[data-testid="metric-container"]{

    background:white;

    border-radius:16px;

    padding:16px;

    border:1px solid #ECECEC;

    box-shadow:0 5px 15px rgba(0,0,0,.06);

    transition:.25s;

}

[data-testid="metric-container"]:hover{

    transform:translateY(-4px);

    box-shadow:0 10px 22px rgba(0,0,0,.10);

}

[data-testid="stMetricValue"]{

    font-size:2rem !important;

    font-weight:700;

}


/* ==========================================================
   BOUTONS
========================================================== */

.stButton>button,
.stDownloadButton>button{

    width:100%;

    height:46px;

    border:none;

    border-radius:12px;

    background:#E31937;

    color:white;

    font-weight:600;

    transition:.25s;

}

.stButton>button:hover,
.stDownloadButton>button:hover{

    background:#C8102E;

}


/* ==========================================================
   DATAFRAME
========================================================== */

[data-testid="stDataFrame"]{

    border-radius:14px;

    overflow:hidden;

    border:1px solid #E5E7EB;

    box-shadow:0 4px 12px rgba(0,0,0,.05);

}


/* ==========================================================
   ALERTES
========================================================== */

.stAlert{

    border-radius:14px;

}


/* ==========================================================
   PLOTLY
========================================================== */

.js-plotly-plot{

    background:white;

    border-radius:14px;

    border:1px solid #ECECEC;

    padding:8px;

}


/* ==========================================================
   LIENS
========================================================== */

a{

    color:#E31937;

    text-decoration:none;

}

a:hover{

    color:#C8102E;

}


/* ==========================================================
   FOOTER
========================================================== */

.footer{

    text-align:center;

    color:#6B7280;

    font-size:13px;

    margin-top:25px;

    padding-top:15px;

    border-top:1px solid #E5E7EB;

}


/* ==========================================================
   SCROLLBAR
========================================================== */

::-webkit-scrollbar{

    width:8px;

}

::-webkit-scrollbar-thumb{

    background:#C7CBD1;

    border-radius:20px;

}

::-webkit-scrollbar-track{

    background:#F3F4F6;

}


/* ==========================================================
   RESPONSIVE
========================================================== */

@media (max-width:900px){

.block-container{

    padding-left:1rem;

    padding-right:1rem;

}

h1{

    font-size:2.2rem;

}

}

</style>
""",
        unsafe_allow_html=True,
    )