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
# COOKIE / PRIVACY DETECTION
# ==========================================================

# Pages de type fiche technique / données de marché.
# Elles ne doivent pas afficher un petit extrait SEO comme résumé éditorial.
MARKET_TECHNICAL_PAGE_PATTERNS = [
    "bourse de casablanca - liste des fiche-technique",
    "bourse de casablanca liste des fiche-technique",
    "liste des fiche-technique",
    "liste des fiches techniques",
    "fiche-technique",
    "fiche technique",
]


def is_market_technical_page(title):
    normalized = clean_text(title).lower()

    if not normalized:
        return False

    return any(
        pattern in normalized
        for pattern in MARKET_TECHNICAL_PAGE_PATTERNS
    )


COOKIE_PRIVACY_PATTERNS = [
    "nous utilisons des cookies",
    "nous utilisons les cookies",
    "vos préférences des cookies",
    "préférences des cookies",
    "politique de confidentialité",
    "politique de vie privée",
    "politique de vie privee",
    "mémoire locale",
    "memoire locale",
    "accepter ou refuser",
    "accepter les cookies",
    "refuser les cookies",
    "contenu personnalisé",
    "contenu personnalise",
    "cookies permettant d'afficher",
    "cookies nécessaires",
    "cookies necessaires",
    "privacy policy",
    "cookie policy",
    "cookie preferences",
]


def is_cookie_privacy_content(text):
    """Détecte une bannière cookies / confidentialité."""
    normalized = clean_text(text).lower()

    if not normalized:
        return False

    matches = sum(
        1 for pattern in COOKIE_PRIVACY_PATTERNS
        if pattern in normalized
    )

    if matches >= 2:
        return True

    if (
        "cookies" in normalized
        and (
            "préférences" in normalized
            or "preferences" in normalized
        )
        and (
            "mémoire locale" in normalized
            or "memoire locale" in normalized
            or "navigateur" in normalized
        )
    ):
        return True

    return False


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

    if is_cookie_privacy_content(text):
        return ""

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

    title = str(
        selected.get(
            "title",
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

    if is_cookie_privacy_content(clean_content):
        clean_content = ""

    # ======================================================
    # CAS SPÉCIAL : PAGE FICHE TECHNIQUE / MARCHÉ
    # ======================================================
    #
    # Le petit texte SEO stocké dans "summary" n'est jamais utilisé
    # directement pour ces pages. Si le contenu réel est suffisamment
    # riche, on construit l'extrait à partir de celui-ci.
    if is_market_technical_page(title):
        if len(clean_content) >= MIN_SUMMARY_LENGTH:
            technical_summary = build_summary_from_content(
                clean_content,
                MAX_SUMMARY_LENGTH,
            )

            if len(technical_summary) >= MIN_SUMMARY_LENGTH:
                return technical_summary

        return ""

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

            content_summary = build_summary_from_content(
                clean_content,
                MAX_SUMMARY_LENGTH,
            )

            if len(content_summary) >= MIN_SUMMARY_LENGTH:
                return content_summary

        return ""


    # ======================================================
    # CAS 3
    # Résumé trop court
    # ======================================================

    if (
        len(summary) < MIN_SUMMARY_LENGTH
        and len(clean_content) >= MIN_SUMMARY_LENGTH
        and len(clean_content) > len(summary)
    ):

        # Construire un bloc plus riche à partir du contenu.
        # Il doit obligatoirement atteindre la longueur minimale.
        content_excerpt = build_summary_from_content(
            clean_content,
            MAX_SUMMARY_LENGTH,
        )

        if len(content_excerpt) >= MIN_SUMMARY_LENGTH:
            return content_excerpt

        # Le contenu ne permet pas de produire un résumé suffisamment
        # riche : on n'affiche pas le résumé court.
        return ""

    # ======================================================
    # CAS 4
    # Résumé déjà suffisamment long
    # ======================================================

    final_summary = shorten_text(
        summary,
        MAX_SUMMARY_LENGTH,
    )

    if is_cookie_privacy_content(final_summary):
        return ""

    return final_summary


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

    col1, col2 = st.columns(
        2
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
