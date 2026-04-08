from __future__ import annotations

import html
import json
import math
import time
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from win_engine.core.config import get_settings
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.ingestion.research_service import ResearchService


st.set_page_config(
    page_title="CreatorMode // YT",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def copy_button(label: str, value: str, key: str) -> None:
    payload = json.dumps(value)
    safe_label = html.escape(label)
    components.html(
        f"""
        <div style="margin: 0.2rem 0 0.55rem 0;">
          <button
            onclick='navigator.clipboard.writeText({payload}); this.innerText="Copied";'
            style="
              width:100%;
              background: linear-gradient(90deg, #FF0000 0%, #CC0000 100%);
              border: none;
              color: white;
              padding: 0.72rem 1rem;
              border-radius: 12px;
              font-weight: 700;
              letter-spacing: 0.4px;
              cursor: pointer;
              box-shadow: 0 4px 15px rgba(255, 0, 0, 0.3);
            "
          >
            {safe_label}
          </button>
        </div>
        """,
        height=58,
    )


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        marker = cleaned.lower()
        if marker in seen:
            continue
        seen.add(marker)
        ordered.append(cleaned)
    return ordered


def build_tags(result: dict[str, Any]) -> list[str]:
    tags: list[str] = []

    for signal in result.get("keyword_signals", []):
        keyword = str(signal.get("keyword", "")).strip()
        if keyword:
            tags.append(keyword)

    for hashtag in result.get("hashtags", []):
        normalized = str(hashtag).strip().lstrip("#").replace("_", " ")
        if normalized:
            tags.append(normalized)

    return dedupe_preserve_order(tags)[:12]


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800;900&display=swap');

        html, body, [class*="css"]  {
            font-family: 'Inter', sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(255, 0, 0, 0.12), transparent 24%),
                radial-gradient(circle at top left, rgba(255, 120, 40, 0.08), transparent 28%),
                linear-gradient(180deg, #0f0f0f 0%, #1a1a1a 100%);
        }

        .block-container {
            padding-top: 1.3rem;
            padding-bottom: 3rem;
        }

        h1, h2, h3, h4, p, div, span, label {
            color: #f5f7fb;
        }

        [data-testid="stVerticalBlock"] > div:has(div.stButton) {
            background: rgba(255, 255, 255, 0.03);
            padding: 2rem;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }

        div.stButton > button:first-child {
            background: linear-gradient(90deg, #FF0000 0%, #CC0000 100%);
            border: none;
            color: white;
            padding: 0.82rem 1.2rem;
            border-radius: 12px;
            font-weight: 800;
            letter-spacing: 0.5px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(255, 0, 0, 0.3);
        }

        div.stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(255, 0, 0, 0.5);
            color: white;
        }

        .stTextArea textarea {
            background-color: #000000 !important;
            border: 1px solid #333 !important;
            border-radius: 12px !important;
            color: #ddd !important;
            min-height: 360px !important;
        }

        [data-testid="stSelectbox"] > div,
        [data-testid="stMultiSelect"] > div {
            background-color: #111318;
            border-radius: 12px;
        }

        .copy-card {
            background-color: #1d2129;
            padding: 20px;
            border-radius: 14px;
            border-left: 5px solid #FF0000;
            margin-bottom: 20px;
            box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18);
        }

        .best-card {
            background: linear-gradient(135deg, rgba(255, 0, 0, 0.15), rgba(29, 33, 41, 1));
        }

        .best-title {
            font-size: 2.15rem;
            line-height: 1.15;
            font-weight: 900;
            margin-top: 0.35rem;
            margin-bottom: 0.4rem;
        }

        .mini-label {
            color: #aab1c3;
            text-transform: uppercase;
            font-size: 0.78rem;
            letter-spacing: 0.08em;
            font-weight: 700;
        }

        .counter {
            color: #98a2b3;
            text-align: right;
            font-size: 0.8rem;
            margin-top: 0.35rem;
        }

        .helper {
            color: #98a2b3;
            font-size: 0.92rem;
        }

        pre {
            background: #111318 !important;
            border-radius: 14px !important;
            border: 1px solid rgba(255, 255, 255, 0.06);
        }

        [data-testid="stExpander"] details {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.04);
            border-radius: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def counter_text(current: int, limit: int) -> str:
    return f"{current}/{limit}"


def energy_to_tone(energy: str) -> str:
    mapping = {
        "Chill": "Formal",
        "Hype": "Viral",
        "Chaos": "Educational",
    }
    return mapping.get(energy, "Viral")


def estimated_minutes(text: str) -> int:
    words = max(len(text.split()), 1)
    return max(1, math.ceil(words / 150))


def main() -> None:
    apply_styles()

    if "history" not in st.session_state:
        st.session_state.history = []
    if "result" not in st.session_state:
        st.session_state.result = None

    col_h1, col_h2 = st.columns([2, 1])
    with col_h1:
        st.title("🎬 CreatorMode")
        st.markdown(
            "<p style='opacity: 0.68; margin-top: -15px;'>Vibe-check your SEO. Script to Studio in seconds.</p>",
            unsafe_allow_html=True,
        )

    st.divider()

    left_col, right_col = st.columns([1, 2.2], gap="large")

    with left_col:
        st.markdown("### 🛠️ Config")
        with st.container(border=True):
            lang = st.selectbox("Vibe (Language)", ["Auto-detect", "English", "Tamil", "Gen-Z Slang"])
            region = st.selectbox("Region", ["Global", "India", "Tamil Nadu", "Sri Lanka", "Gulf"])
            audience_type = st.selectbox("Audience", ["General", "Local", "Diaspora", "Global"])
            tone = st.select_slider("Energy Level", options=["Chill", "Hype", "Chaos"], value="Hype")

            st.write("")
            with st.expander("Advanced Settings"):
                hashtags_enabled = st.checkbox("Auto-Hashtags", value=True)
                raw_logs = st.checkbox("Dev Mode", value=False)

        if st.session_state.history:
            st.write("")
            st.markdown("### 🕒 Recent Drops")
            for item in reversed(st.session_state.history[-3:]):
                st.caption(f"📌 {item['title'][:42]}...")

    with right_col:
        script_content = st.text_area(
            "Drop your script here",
            height=360,
            placeholder="Paste the sauce here... the more context, the better the output.",
        )

        char_count = len(script_content)
        st.caption(f"Character count: {char_count} | Estimated reading time: {estimated_minutes(script_content) if script_content else 0} mins")

        if st.button("Generate Final Package ⚡"):
            if not script_content.strip():
                st.toast("Add a script first, bestie.", icon="🚫")
            else:
                with st.status("Cooking the SEO sauce...", expanded=True) as status:
                    st.write("Checking the hook...")
                    time.sleep(0.2)
                    settings = get_settings()
                    research = ResearchService(settings)
                    research_payload = research.gather(script_content.strip())
                    st.write("Optimizing for the algorithm...")
                    time.sleep(0.2)
                    generation_context = {
                        "language": lang if lang != "Auto-detect" else "",
                        "region": region,
                        "audience_type": audience_type,
                    }
                    result = generate_seo_suggestions(script_content.strip(), research_payload, context=generation_context)
                    result["selected_language"] = lang
                    result["selected_tone"] = energy_to_tone(tone)
                    result["selected_region"] = region
                    result["selected_audience_type"] = audience_type
                    result["raw_logs"] = raw_logs
                    if not hashtags_enabled:
                        result["hashtags"] = []
                    st.session_state.result = result
                    st.session_state.history.append({"title": result["title"]})
                    status.update(label="Manifested! ✨", state="complete", expanded=False)

    result = st.session_state.result
    if not result:
        st.write("")
        st.info("💡 **Pro-Tip:** Streamlit's `st.code` block has a copy button in the top right. Use it.")
        return

    best_title = str(result.get("title", "")).strip()
    description = str(result.get("description", "")).strip()
    tags = ", ".join(build_tags(result))
    hashtags = " ".join(str(tag).strip() for tag in result.get("hashtags", []) if str(tag).strip())
    alt_titles = [
        title for title in dedupe_preserve_order([str(item) for item in result.get("title_variants", [])])
        if title != best_title
    ][:3]

    st.write("")
    res_tab1, res_tab2, res_tab3 = st.tabs(["🔥 THE DROP", "🎲 ALT VIBES", "📊 SEO TAGS"])

    with res_tab1:
        st.markdown('<div class="copy-card best-card">', unsafe_allow_html=True)
        st.markdown('<div class="mini-label">Primary Title</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="best-title">{html.escape(best_title)}</div>', unsafe_allow_html=True)
        copy_button("Copy Best Title", best_title, "copy_best_title")
        st.markdown(f'<div class="counter">{counter_text(len(best_title), 100)}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="copy-card">', unsafe_allow_html=True)
        st.markdown("#### Meta Description")
        st.code(description, language=None)
        copy_button("Copy Description", description, "copy_description")
        st.markdown(f'<div class="counter">{counter_text(len(description), 5000)}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with res_tab2:
        st.markdown('<div class="copy-card">', unsafe_allow_html=True)
        st.markdown("#### Alt Titles")
        for title in alt_titles:
            st.code(title, language=None)
        copy_button("Copy All Alt Titles", "\n".join(alt_titles), "copy_alt_titles")
        st.markdown("</div>", unsafe_allow_html=True)

    with res_tab3:
        st.markdown('<div class="copy-card">', unsafe_allow_html=True)
        st.markdown("#### Keywords & Tags")
        st.code(tags, language=None)
        copy_button("Copy Tags", tags, "copy_tags")
        st.markdown(f'<div class="counter">{counter_text(len(tags), 500)}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="copy-card">', unsafe_allow_html=True)
        st.markdown("#### Hashtags")
        st.code(hashtags, language=None)
        copy_button("Copy Hashtags", hashtags, "copy_hashtags")
        st.markdown("</div>", unsafe_allow_html=True)

    if result.get("raw_logs"):
        st.write("")
        st.markdown("### 🧪 Dev Mode")
        st.json(
            {
                "intent": result.get("intent"),
                "content_angle": result.get("content_angle"),
                "title_optimization": result.get("title_optimization"),
                "keyword_signals": result.get("keyword_signals"),
                "entity_signals": result.get("entity_signals"),
            }
        )

    st.write("")
    st.info("💡 **Pro-Tip:** Streamlit's `st.code` block has a copy button in the top right. Use it.")


if __name__ == "__main__":
    main()
