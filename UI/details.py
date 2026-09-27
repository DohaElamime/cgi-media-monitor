"""
UI/details.py
----------------------------------------------------
Affichage des détails d'un article.
"""

import re
import html

import pandas as pd
import streamlit as st

from bs4 import BeautifulSoup


# ==========================================================
# CONSTANTES
# ==========================================================

# Taille minimale d'un résumé considéré comme suffisamment long
MIN_SUMMARY_LENGTH = 450

# Taille maximale affichée dans le résumé
MAX_SUMMARY_LENGTH = 1500


# ==========================================================
# NETTOYAGE TEXTE
# ==========================================================

def clean_text(text):
    """
    Nettoie un texte HTML et normalise les espaces.
    """

    if text is None:
        return ""

    text = str(text).strip()

    if not text:
        return ""

    # Décodage HTML
    text = html.unescape(text)

    try:

        soup = BeautifulSoup(
            text,
            "html.parser",
        )

        text = soup.get_text(
            " ",
            strip=True,
        )

    except Exception:
        pass

    # Nettoyer les espaces
    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text


# ==========================================================
# NETTOYAGE DU RÉSUMÉ
# ==========================================================

def clean_summary(
    summary,
    source=None,
):
    """
    Nettoie le résumé provenant de la base.

    Supprime notamment le HTML Google News :

        <a href="...">Titre</a>
        <font>Le360</font>

    """

    text = clean_text(
        summary
    )

    if not text:
        return ""

    # ------------------------------------------------------
    # Supprimer la source finale
    # ------------------------------------------------------

    if source:

        source = str(
            source
        ).strip()

        if (
            source
            and text.lower().endswith(
                source.lower()
            )
        ):

            text = text[
                : -len(source)
            ].rstrip(
                " -|"
            ).strip()

    # ------------------------------------------------------
    # Supprimer quelques marqueurs RSS
    # ------------------------------------------------------

    text = re.sub(
        r"^\s*(Résumé|Summary)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text.strip()


# ==========================================================
# DÉTECTER HTML GOOGLE NEWS
# ==========================================================

def is_google_news_summary(
    summary,
):
    """
    Détecte si la valeur ressemble au HTML brut
    fourni par Google News RSS.
    """

    if summary is None:
        return False

    raw = str(
        summary
    ).lower()

    indicators = (
        "<a ",
        "</a>",
        "<font",
        "</font>",
        "news.google.com",
        "target=\"_blank\"",
        "target='_blank'",
    )

    return any(
        indicator in raw
        for indicator in indicators
    )


# ==========================================================
# COUPURE PROPRE
# ==========================================================

def shorten_text(
    text,
    max_length=MAX_SUMMARY_LENGTH,
):
    """
    Limite un texte sans couper brutalement une phrase
    lorsque c'est possible.
    """

    text = clean_text(
        text
    )

    if not text:
        return ""

    if len(text) <= max_length:
        return text

    shortened = text[
        :max_length
    ]

    # ------------------------------------------------------
    # Chercher une fin de phrase
    # ------------------------------------------------------

    sentence_positions = [
        shortened.rfind(". "),
        shortened.rfind("! "),
        shortened.rfind("? "),
        shortened.rfind("。"),
    ]

    best_position = max(
        sentence_positions
    )

    # On accepte la coupure seulement
    # si elle laisse un texte suffisamment long.
    if best_position >= 250:

        return shortened[
            :best_position + 1
        ].strip()

    # ------------------------------------------------------
    # Sinon couper au dernier espace
    # ------------------------------------------------------

    shortened = shortened.rsplit(
        " ",
        1,
    )[0].strip()

    return shortened + "..."


# ==========================================================
# RÉSUMÉ DE SECOURS
# ==========================================================

def build_summary_from_content(
    content,
    max_length=MAX_SUMMARY_LENGTH,
):
    """
    Construit un résumé d'affichage à partir du contenu réel.

    IMPORTANT :
    ce n'est pas une nouvelle analyse IA.
    C'est un extrait propre du contenu existant.
    """

    text = clean_text(
        content
    )

    if not text:
        return ""

    # ------------------------------------------------------
    # Éviter les textes extrêmement courts
    # ------------------------------------------------------

    if len(text) <= max_length:
        return text

    # ------------------------------------------------------
    # Garder des phrases complètes autant que possible
    # ------------------------------------------------------

    candidate = text[
        :max_length
    ]

    # Chercher le dernier point
    matches = list(
        re.finditer(
            r"[.!?](?:\s|$)",
            candidate,
        )
    )

    if matches:

        last = matches[-1]

        if last.end() >= 350:

            return candidate[
                :last.end()
            ].strip()

    # ------------------------------------------------------
    # Sinon dernier espace
    # ------------------------------------------------------

    candidate = candidate.rsplit(
        " ",
        1,
    )[0].strip()

    return candidate + "..."


# ==========================================================
# CONSTRUIRE LE RÉSUMÉ AFFICHÉ
# ==========================================================

def get_display_summary(
    selected,
):
    """
    Retourne le meilleur résumé possible.

    Priorité :

        1. Résumé IA propre et suffisamment long
        2. Contenu réel si résumé trop court
        3. Résumé IA court comme dernier recours
    """

    source = str(
        selected.get(
            "source",
            "",
        )
        or ""
    ).strip()

    raw_summary = (
        selected.get(
            "summary",
            "",
        )
        or ""
    )

    content = (
        selected.get(
            "content",
            "",
        )
        or ""
    )

    # ======================================================
    # RÉSUMÉ EXISTANT
    # ======================================================

    summary = clean_summary(
        raw_summary,
        source=source,
    )

    google_html = is_google_news_summary(
        raw_summary
    )

    # ======================================================
    # CONTENU NETTOYÉ
    # ======================================================

    clean_content = clean_text(
        content
    )

    # ======================================================
    # CAS 1
    # Résumé Google News brut
    # ======================================================

    if google_html:

        summary = ""

    # ======================================================
    # CAS 2
    # Résumé vide
    # ======================================================

    if not summary:

        if clean_content:

            return build_summary_from_content(
                clean_content,
                MAX_SUMMARY_LENGTH,
            )

        return ""

    # ======================================================
    # CAS 3
    # Résumé trop court
    # ======================================================

    if (
        len(summary) < MIN_SUMMARY_LENGTH
        and len(clean_content) > len(summary)
    ):

        # Construire un bloc plus riche à partir du contenu
        content_excerpt = build_summary_from_content(
            clean_content,
            MAX_SUMMARY_LENGTH,
        )

        if content_excerpt:

            return content_excerpt

    # ======================================================
    # CAS 4
    # Résumé déjà suffisamment long
    # ======================================================

    return shorten_text(
        summary,
        MAX_SUMMARY_LENGTH,
    )


# ==========================================================
# SENTIMENT
# ==========================================================

def get_sentiment_badge(
    sentiment,
):
    """
    Retourne le badge correspondant au sentiment.
    """

    normalized = (
        str(
            sentiment
            or ""
        )
        .strip()
        .lower()
    )

    if normalized in (
        "positive",
        "positif",
    ):

        return (
            "🟢 Positif",
            "positive",
        )

    if normalized in (
        "negative",
        "négatif",
        "negatif",
    ):

        return (
            "🔴 Négatif",
            "negative",
        )

    if normalized in (
        "neutral",
        "neutre",
    ):

        return (
            "🟡 Neutre",
            "neutral",
        )

    return (
        "⚪ Non analysé",
        "unknown",
    )


# ==========================================================
# AFFICHAGE
# ==========================================================

def render_details(
    df: pd.DataFrame,
):
    """
    Affiche les détails d'un article.
    """

    # ======================================================
    # AUCUNE DONNÉE
    # ======================================================

    if df.empty:

        st.info(
            "Aucun article disponible."
        )

        return

    # ======================================================
    # SÉLECTION
    # ======================================================

    article = st.selectbox(
        "Sélectionner un article",
        options=df.index,
        format_func=lambda i: (
            str(
                df.loc[i, "title"]
            )
            if "title" in df.columns
            else f"Article {i}"
        ),
        key="details_article_selector",
    )

    selected = df.loc[
        article
    ]

    # ======================================================
    # DONNÉES
    # ======================================================

    title = str(
        selected.get(
            "title",
            "Sans titre",
        )
        or "Sans titre"
    ).strip()

    source = str(
        selected.get(
            "source",
            "-",
        )
        or "-"
    ).strip()

    sentiment = str(
        selected.get(
            "sentiment",
            "",
        )
        or ""
    ).strip()

    url = str(
        selected.get(
            "url",
            "",
        )
        or ""
    ).strip()

    summary = get_display_summary(
        selected
    )

    # ======================================================
    # CONFIANCE
    # ======================================================

    try:

        confidence = float(
            selected.get(
                "confidence",
                0,
            )
            or 0
        )

    except (
        TypeError,
        ValueError,
    ):

        confidence = 0.0

    confidence = max(
        0.0,
        min(
            1.0,
            confidence,
        ),
    )

    # ======================================================
    # SENTIMENT
    # ======================================================

    badge, sentiment_type = (
        get_sentiment_badge(
            sentiment
        )
    )

    # ======================================================
    # TITRE
    # ======================================================

    st.title(
        title
    )

    st.write("")

    # ======================================================
    # INFORMATIONS
    # ======================================================

    col1, col2, col3 = st.columns(
        3
    )

    # ------------------------------------------------------
    # SOURCE
    # ------------------------------------------------------

    with col1:

        st.info(
            f"🌐 **Source**\n\n{source}"
        )

    # ------------------------------------------------------
    # SENTIMENT
    # ------------------------------------------------------

    with col2:

        if sentiment_type == "positive":

            st.success(
                f"**{badge}**"
            )

        elif sentiment_type == "negative":

            st.error(
                f"**{badge}**"
            )

        elif sentiment_type == "neutral":

            st.warning(
                f"**{badge}**"
            )

        else:

            st.info(
                f"**{badge}**"
            )

    # ------------------------------------------------------
    # CONFIANCE
    # ------------------------------------------------------

    with col3:

        st.metric(
            "🤖 Confiance IA",
            f"{confidence:.0%}",
        )

    # ======================================================
    # RÉSUMÉ
    # ======================================================

    st.markdown(
        "### 📝 Résumé"
    )

    if summary:

        st.markdown(
            f"""
            <div style="
                background:#FFFFFF;
                border:1px solid #E5E7EB;
                border-radius:14px;
                padding:22px 24px;
                margin-top:8px;
                margin-bottom:18px;
                font-size:16px;
                line-height:1.85;
                color:#1F2937;
                text-align:justify;
            ">
                {html.escape(summary)}
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:

        st.info(
            "Aucun résumé disponible."
        )

    # ======================================================
    # ARTICLE ORIGINAL
    # ======================================================

    if url:

        st.link_button(
            "🌐 Lire l'article complet",
            url,
            width="stretch",
        )