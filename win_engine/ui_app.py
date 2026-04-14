from __future__ import annotations

import copy
import html
import json
import math
from datetime import datetime
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from win_engine.analysis.psychology_triggers_engine import analyze_content_psychology
from win_engine.core.config import get_settings
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.post_upload_engine import get_post_upload_recommendations
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.generation.upload_timing_engine import get_optimal_upload_time
from win_engine.ingestion.research_service import ResearchService

try:
    from win_engine.analysis.tamil_language_engine import TamilLanguageDetector
except ImportError:  # pragma: no cover - optional feature
    TamilLanguageDetector = None


PAGE_OPTIONS = [
    "Optimizer",
    "Brain Insights",
    "Upload Timing",
    "Post-Upload",
    "Psychology",
    "Settings & Help",
]


def main() -> None:
    st.set_page_config(
        page_title="Win-Engine OS v4",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    apply_styles()
    init_session_state()
    settings = get_settings()
    page, ui = render_sidebar(settings)

    render_hero(ui)

    if page == "Optimizer":
        render_optimizer(ui)
    elif page == "Brain Insights":
        render_brain_insights()
    elif page == "Upload Timing":
        render_upload_timing(ui)
    elif page == "Post-Upload":
        render_post_upload(ui)
    elif page == "Psychology":
        render_psychology(ui)
    else:
        render_settings_help(settings)


def init_session_state() -> None:
    defaults: dict[str, Any] = {
        "result": None,
        "analysis_history": [],
        "script_draft": "",
        "post_upload_result": None,
        "psychology_result": None,
        "latest_settings": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

        :root {
            --bg: #09111f;
            --bg-soft: #111d32;
            --panel: rgba(11, 19, 33, 0.92);
            --panel-strong: rgba(17, 29, 50, 0.96);
            --panel-border: rgba(148, 163, 184, 0.18);
            --text-main: #f8fafc;
            --text-soft: #cbd5e1;
            --text-dim: #94a3b8;
            --accent: #ff6b35;
            --accent-2: #13c2c2;
            --good: #22c55e;
            --warn: #f59e0b;
            --bad: #ef4444;
        }


        html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], .block-container {
            background: #09111f !important;
            color: var(--text-main) !important;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(19, 194, 194, 0.12), transparent 28%),
                radial-gradient(circle at top right, rgba(255, 107, 53, 0.14), transparent 26%),
                linear-gradient(180deg, #08101b 0%, #0d1728 100%);
            color: var(--text-main);
            font-family: "IBM Plex Sans", sans-serif;
        }

        .block-container {
            padding-top: 3.5rem !important;
            padding-bottom: 2.5rem;
        }

        h1, h2, h3, h4, h5, h6, p, li, label, span, div {
            color: var(--text-main);
            font-family: "IBM Plex Sans", sans-serif;
        }


        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #111d32 0%, #09111f 100%) !important;
            border-right: 1px solid var(--panel-border) !important;
        }

        [data-testid="stSidebar"] * {
            color: var(--text-main) !important;
        }

        [data-testid="stSidebar"] .stRadio label,
        [data-testid="stSidebar"] .stSelectbox label,
        [data-testid="stSidebar"] .stMultiSelect label,
        [data-testid="stSidebar"] .stCheckbox label,
        [data-testid="stSidebar"] .stTextInput label,
        [data-testid="stSidebar"] .stNumberInput label {
            color: var(--text-soft) !important;
            font-weight: 600;
        }

        [data-testid="stSidebar"] .stTextInput input,
        [data-testid="stSidebar"] .stTextArea textarea,
        [data-testid="stSidebar"] .stNumberInput input {
            background: rgba(8, 15, 27, 0.95) !important;
            color: var(--text-main) !important;
            border: 1px solid rgba(148, 163, 184, 0.25) !important;
            border-radius: 14px !important;
        }

        .stTextArea textarea,
        .stTextInput input,
        .stNumberInput input {
            background: rgba(8, 15, 27, 0.85) !important;
            color: var(--text-main) !important;
            border: 1px solid rgba(148, 163, 184, 0.25) !important;
            border-radius: 14px !important;
        }

        .stTextArea textarea::placeholder,
        .stTextInput input::placeholder {
            color: var(--text-dim) !important;
        }

        [data-testid="stSelectbox"] > div,
        [data-testid="stMultiSelect"] > div {
            background: rgba(8, 15, 27, 0.9) !important;
            border: 1px solid rgba(148, 163, 184, 0.25) !important;
            border-radius: 14px !important;
        }

        .stMarkdown a {
            color: #7dd3fc !important;
        }

        div.stButton > button:first-child,
        .stDownloadButton button {
            background: linear-gradient(135deg, #ff6b35 0%, #f43f5e 100%);
            color: white !important;
            border: none;
            border-radius: 14px;
            font-weight: 700;
            letter-spacing: 0.02em;
            box-shadow: 0 12px 30px rgba(244, 63, 94, 0.22);
        }

        div.stButton > button:hover,
        .stDownloadButton button:hover {
            color: white !important;
            transform: translateY(-1px);
        }

        button[kind="secondary"] {
            background: rgba(17, 29, 50, 0.96) !important;
            border: 1px solid rgba(148, 163, 184, 0.22) !important;
        }

        [data-testid="stMetric"] {
            background: linear-gradient(180deg, rgba(11, 19, 33, 0.88), rgba(17, 29, 50, 0.92));
            border: 1px solid rgba(148, 163, 184, 0.16);
            padding: 0.9rem 1rem;
            border-radius: 16px;
        }

        [data-testid="stMetricLabel"] {
            color: var(--text-soft) !important;
        }

        [data-testid="stMetricValue"] {
            color: var(--text-main) !important;
        }

        [data-testid="stMetricDelta"] {
            color: #86efac !important;
        }

        [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }

        button[data-baseweb="tab"] {
            background: rgba(17, 29, 50, 0.8);
            border: 1px solid rgba(148, 163, 184, 0.14);
            border-radius: 12px 12px 0 0;
            color: var(--text-soft) !important;
            padding: 0.7rem 1rem !important;
            font-weight: 600;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            background: rgba(255, 107, 53, 0.12);
            color: var(--text-main) !important;
            border-bottom: 2px solid var(--accent);
        }

        .hero-shell, .surface-card, .info-card {
            background: linear-gradient(180deg, rgba(11, 19, 33, 0.9), rgba(17, 29, 50, 0.92));
            border: 1px solid rgba(148, 163, 184, 0.15);
            border-radius: 20px;
            padding: 1.1rem 1.2rem;
            box-shadow: 0 16px 40px rgba(8, 15, 27, 0.34);
        }

        .hero-title {
            font-family: "Space Grotesk", sans-serif;
            font-size: 2.4rem;
            font-weight: 700;
            line-height: 1.05;
            color: var(--text-main);
            margin: 0;
        }

        .hero-subtitle {
            color: var(--text-soft);
            margin-top: 0.35rem;
            margin-bottom: 0;
            font-size: 1rem;
        }

        .badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 0.85rem;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.4rem 0.7rem;
            border-radius: 999px;
            background: rgba(19, 194, 194, 0.12);
            border: 1px solid rgba(19, 194, 194, 0.25);
            color: var(--text-main);
            font-size: 0.84rem;
            font-weight: 600;
        }

        .accent-badge {
            background: rgba(255, 107, 53, 0.12);
            border-color: rgba(255, 107, 53, 0.25);
        }

        .section-title {
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.15rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }

        .section-copy {
            color: var(--text-soft);
            line-height: 1.55;
            margin-top: 0.2rem;
        }

        .callout {
            border-left: 4px solid var(--accent-2);
            padding: 0.8rem 0.95rem;
            background: rgba(19, 194, 194, 0.08);
            border-radius: 0 14px 14px 0;
            color: var(--text-soft);
        }

        .title-block {
            background: linear-gradient(135deg, rgba(255, 107, 53, 0.14), rgba(19, 194, 194, 0.09));
            border: 1px solid rgba(148, 163, 184, 0.15);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            margin-bottom: 1rem;
        }

        .title-label {
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.75rem;
            font-weight: 700;
        }

        .title-main {
            color: var(--text-main);
            font-size: 1.85rem;
            line-height: 1.15;
            font-weight: 700;
            margin: 0.35rem 0 0.5rem;
        }

        .sidebar-card {
            background: rgba(17, 29, 50, 0.78);
            border: 1px solid rgba(148, 163, 184, 0.14);
            border-radius: 18px;
            padding: 0.85rem 0.95rem;
            margin-bottom: 0.8rem;
        }

        .sidebar-kicker {
            color: var(--text-dim);
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 700;
        }

        .sidebar-brand {
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.65rem;
            font-weight: 700;
            margin: 0.2rem 0 0;
            color: var(--text-main);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(settings: Any) -> tuple[str, dict[str, Any]]:

    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-card">
                <div class="sidebar-kicker">Win-Engine OS</div>
                <div class="sidebar-brand">UI v4</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        page = st.radio(
            "Workspace",
            PAGE_OPTIONS,
            index=PAGE_OPTIONS.index("Optimizer"),
            help="Switch between optimization, analytics, timing, monitoring, and psychology tools.",
        )

        st.markdown("### Creator Controls")
        language_mode = st.selectbox("Language", ["Auto-detect", "English", "Tamil", "Gen-Z Slang"], index=0)
        region = st.selectbox("Region", ["Global", "India", "Tamil Nadu", "Sri Lanka", "Gulf"], index=0)
        audience_type = st.selectbox("Audience", ["General", "Local", "Diaspora", "Global"], index=0)
        script_format = st.selectbox(
            "Format",
            ["Tutorial", "Case Study", "Vlog", "Documentary", "Short-Form", "Podcast"],
            index=0,
        )
        niche = st.selectbox(
            "Niche",
            ["General Growth", "Tech", "Education", "Finance", "Entertainment", "Gaming", "Health"],
            index=0,
        )
        energy = st.select_slider("Energy", options=["Chill", "Hype", "Chaos"], value="Hype")

        st.markdown("### Output Controls")
        include_hashtags = st.checkbox("Show hashtags", value=True)
        show_raw_data = st.checkbox("Show raw JSON panels", value=False)
        compare_competitors = st.checkbox("Use competitor timing inference", value=True)
        creator_timezone = st.text_input("Creator timezone", value="UTC")
        target_audience = st.selectbox(
            "Timing audience",
            ["global", "india", "us", "asia", "europe"],
            index=0,
            help="Used by the Phase 13 upload timing panel.",
        )

        st.markdown("### Recent Analyses")
        history = st.session_state.analysis_history
        if history:
            for index, item in enumerate(reversed(history[-5:])):
                title = str(item["result"].get("title", "Untitled")).strip() or "Untitled"
                if st.button(_truncate(title, 34), use_container_width=True, key=f"history_{index}"):
                    st.session_state.result = copy.deepcopy(item["result"])
                    st.session_state.script_draft = item["script"]
        else:
            st.caption("Your last few generated packages will appear here.")

        st.markdown("### System Status")
        history_status = HistoryStore(settings.database_path).system_status()
        st.markdown(
            f"""
            <div class="sidebar-card">
              <div class="section-copy">
                API key loaded: <strong>{'Yes' if settings.youtube_api_key_pool else 'No'}</strong><br>
                Database ready: <strong>{'Yes' if history_status.get('database_ok') else 'No'}</strong><br>
                Stored analyses: <strong>{history_status.get('analysis_count', 0)}</strong>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    ui = {
        "language_mode": language_mode,
        "region": region,
        "audience_type": audience_type,
        "script_format": script_format,
        "niche": niche,
        "energy": energy,
        "include_hashtags": include_hashtags,
        "show_raw_data": show_raw_data,
        "compare_competitors": compare_competitors,
        "creator_timezone": creator_timezone.strip() or "UTC",
        "target_audience": target_audience,
    }
    st.session_state.latest_settings = ui
    return page, ui


def render_hero(ui: dict[str, Any]) -> None:
        st.markdown(
                f"""
                <div class="hero-shell">
                    <p class="hero-title">Win-Engine OS v4</p>
                    <div class="badge-row">
                        <span class="badge accent-badge">Format: {html.escape(ui['script_format'])}</span>
                        <span class="badge">Region: {html.escape(ui['region'])}</span>
                        <span class="badge">Audience: {html.escape(ui['audience_type'])}</span>
                        <span class="badge">Energy: {html.escape(ui['energy'])}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
        )
        st.write("")


def render_optimizer(ui: dict[str, Any]) -> None:
    left_col, right_col = st.columns([2.2, 1], gap="large")

    with left_col:
        st.markdown('<div class="section-title">Script Input</div>', unsafe_allow_html=True)
        # Handle clear draft flag
        if st.session_state.get("clear_draft_flag"):
            script_value = ""
            st.session_state.script_draft = ""
            st.session_state.clear_draft_flag = False
        else:
            script_value = st.session_state.script_draft
        script = st.text_area(
            "Script",
            value=script_value,
            key="script_draft",
            height=360,
            placeholder="Paste the script, hook draft, concept outline, or title direction here.",
        )
        detected = detect_language(script)
        char_count = len(script)
        read_time = max(1, math.ceil(max(len(script.split()), 1) / 150)) if char_count else 0
        helper_cols = st.columns([1, 1, 1])
        helper_cols[0].caption(f"Characters: {char_count}")
        helper_cols[1].caption(f"Read time: {read_time} min")
        helper_cols[2].caption(f"Detected: {detected or 'English'}")

    with right_col:
        if st.button("Generate Full Package", use_container_width=True, type="primary"):
            if not script.strip():
                st.warning("Add a script or idea first.")
            else:
                run_analysis(script.strip(), ui, detected)
        if st.button("Clear Current Draft", use_container_width=True):
            st.session_state.clear_draft_flag = True
            st.session_state.result = None
            st.experimental_rerun()

    result = st.session_state.result
    if not result:
        return

        if st.session_state.result:
            st.markdown('<div class="section-title">Feedback</div>', unsafe_allow_html=True)
            feedback = st.radio(
                "How useful was this package?",
                ["👍 Very useful", "👌 Decent", "👎 Needs work"],
                key="feedback_rating"
            )
            comments = st.text_area("Comments or suggestions? (optional)", key="feedback_comments", height=80)
            if st.button("Submit Feedback", key="submit_feedback_btn"):
                if "feedback_log" not in st.session_state:
                    st.session_state.feedback_log = []
                st.session_state.feedback_log.append({
                    "result": st.session_state.result,
                    "rating": feedback,
                    "comments": comments,
                })
                st.success("Thank you for your feedback! Your input will help improve future recommendations.")
    render_optimizer_results(result, ui)


def render_optimizer_results(result: dict[str, Any], ui: dict[str, Any]) -> None:
    tabs = st.tabs(["Overview", "Titles", "Metadata", "Research", "Brain"])

    with tabs[0]:
        render_overview_tab(result)

    with tabs[1]:
        render_titles_tab(result)

    with tabs[2]:
        render_metadata_tab(result, ui)

    with tabs[3]:
        render_research_tab(result)

    with tabs[4]:
        render_brain_tab(result, ui["show_raw_data"])


def render_overview_tab(result: dict[str, Any]) -> None:
    verdict = result.get("opportunity_gap_analysis", {}).get("viability_verdict", {})
    competition = result.get("opportunity_gap_analysis", {}).get("competition", {})
    ctr_prediction = result.get("ctr_prediction", {})
    timing = result.get("upload_timing", {})

    metrics = st.columns(4)
    metrics[0].metric(
        "Viability",
        str(verdict.get("status", "unknown")).upper(),
        "Proceed" if verdict.get("proceed") else "Rework",
    )
    metrics[1].metric("CTR Prediction", f"{ctr_prediction.get('predicted_ctr_percent', 0)}%", ctr_prediction.get("label", ""))
    metrics[2].metric("Competition", competition.get("label", "UNKNOWN"), str(competition.get("score", "n/a")))
    metrics[3].metric("Content Angle", result.get("content_angle", "unknown"), result.get("intent", ""))

    st.markdown(
        f"""
        <div class="title-block">
          <div class="title-label">Primary Title</div>
          <div class="title-main">{html.escape(str(result.get('title', 'Untitled')))}</div>
          <div class="section-copy">{html.escape(str(verdict.get('summary', 'No summary available yet.')))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    copy_button("Copy Primary Title", str(result.get("title", "")), "copy_primary_title")

    summary_cols = st.columns([1.3, 1])
    with summary_cols[0]:
        st.markdown('<div class="section-title">Packaging Readout</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="callout">
              Timing: {html.escape(str(timing.get('recommendation', 'No timing signal yet.')))}<br>
              Thumbnail: {html.escape(str(result.get('thumbnail_strategy', {}).get('recommendation', 'No thumbnail note.')))}<br>
              Pacing: {html.escape(str(result.get('pacing_analysis', {}).get('recommendation', 'No pacing note.')))}
            </div>
            """,
            unsafe_allow_html=True,
        )
    with summary_cols[1]:
        st.markdown('<div class="section-title">Retention Notes</div>', unsafe_allow_html=True)
        for note in result.get("content_audit", {}).get("retention_risk", {}).get("notes", []):
            st.write(f"- {note}")


def render_titles_tab(result: dict[str, Any]) -> None:
    st.markdown('<div class="section-title">Best Title and Variants</div>', unsafe_allow_html=True)
    best_title = str(result.get("title", ""))
    st.code(best_title, language=None)
    copy_button("Copy Best Title", best_title, "copy_best_title")

    scored_variants = result.get("title_optimization", {}).get("scored_variants", [])
    if scored_variants:
        st.dataframe(scored_variants, use_container_width=True, hide_index=True)

    psychology = result.get("psychology_analysis", {}).get("title_analysis", {})
    if psychology:
        st.markdown('<div class="section-title">Psychology Snapshot</div>', unsafe_allow_html=True)
        psych_cols = st.columns(4)
        psych_cols[0].metric("Composite", f"{psychology.get('composite_score', 0)}", psychology.get("strength_level", ""))
        components = psychology.get("components", {})
        psych_cols[1].metric("Curiosity", f"{components.get('curiosity_gap', {}).get('score', 0)}")
        psych_cols[2].metric("Urgency", f"{components.get('urgency_signals', {}).get('score', 0)}")
        psych_cols[3].metric("Emotion", f"{components.get('emotional_resonance', {}).get('score', 0)}")

        for recommendation in psychology.get("recommendations", []):
            st.markdown(
                f"""
                <div class="info-card">
                  <strong>{html.escape(str(recommendation.get('area', 'Optimization')))}</strong><br>
                  <span class="section-copy">{html.escape(str(recommendation.get('suggestion', '')))}</span><br>
                  <span class="section-copy">{html.escape(str(recommendation.get('example', '')))}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    competitor_shadow = result.get("competitor_shadow", {})
    st.markdown('<div class="section-title">Competitor Shadow</div>', unsafe_allow_html=True)
    st.write(f"- Similar videos: {competitor_shadow.get('similar_video_count', 0)}")
    st.write(f"- Dominant title pattern: {competitor_shadow.get('dominant_title_pattern', 'unknown')}")
    st.write(f"- Differentiation: {competitor_shadow.get('recommended_differentiation', 'No note yet.')}")


def render_metadata_tab(result: dict[str, Any], ui: dict[str, Any]) -> None:
    metadata_cols = st.columns([1.4, 1])

    with metadata_cols[0]:
        st.markdown('<div class="section-title">Description</div>', unsafe_allow_html=True)
        st.code(str(result.get("description", "")), language=None)
        copy_button("Copy Description", str(result.get("description", "")), "copy_description")

        st.markdown('<div class="section-title">Chapters</div>', unsafe_allow_html=True)
        chapters = result.get("chapters", [])
        if chapters:
            st.dataframe(chapters, use_container_width=True, hide_index=True)
        else:
            st.caption("No chapters generated yet.")

    with metadata_cols[1]:
        st.markdown('<div class="section-title">Tags</div>', unsafe_allow_html=True)
        tags = ", ".join(build_tags(result))
        st.code(tags, language=None)
        copy_button("Copy Tags", tags, "copy_tags")

        if ui["include_hashtags"]:
            st.markdown('<div class="section-title">Hashtags</div>', unsafe_allow_html=True)
            hashtags = " ".join([tag for tag in result.get("hashtags", []) if tag])
            st.code(hashtags, language=None)
            copy_button("Copy Hashtags", hashtags, "copy_hashtags")

        st.markdown('<div class="section-title">Language & Thumbnail Strategy</div>', unsafe_allow_html=True)
        st.write(f"- Packaging style: {result.get('language_strategy', {}).get('packaging_style', 'unknown')}")
        st.write(f"- Language note: {result.get('language_strategy', {}).get('recommendation', 'No note yet.')}")
        st.write(f"- Thumbnail note: {result.get('thumbnail_strategy', {}).get('recommendation', 'No note yet.')}")


def render_research_tab(result: dict[str, Any]) -> None:
    research_cols = st.columns(2)

    with research_cols[0]:
        st.markdown('<div class="section-title">Keyword Signals</div>', unsafe_allow_html=True)
        keyword_signals = result.get("keyword_signals", [])
        if keyword_signals:
            st.dataframe(keyword_signals, use_container_width=True, hide_index=True)
        else:
            st.caption("No keyword signals returned.")

        st.markdown('<div class="section-title">Opportunity Gaps</div>', unsafe_allow_html=True)
        keyword_gaps = result.get("opportunity_gap_analysis", {}).get("keyword_gaps", [])
        if keyword_gaps:
            st.dataframe(keyword_gaps, use_container_width=True, hide_index=True)
        else:
            st.caption("No keyword gaps detected for this run.")

    with research_cols[1]:
        st.markdown('<div class="section-title">Competitor Results</div>', unsafe_allow_html=True)
        competitors = [
            {
                "title": item.get("title"),
                "channel": item.get("channel_title"),
                "views": item.get("view_count"),
                "outlier_score": item.get("outlier_score"),
                "published_at": item.get("published_at"),
            }
            for item in result.get("youtube_results", [])
        ]
        if competitors:
            st.dataframe(competitors, use_container_width=True, hide_index=True)
        else:
            st.caption("No YouTube research results available.")

        st.markdown('<div class="section-title">Timing Intel</div>', unsafe_allow_html=True)
        upload_timing = result.get("upload_timing", {})
        st.write(f"- Top hours: {', '.join(map(str, upload_timing.get('top_hours', []))) or 'n/a'}")
        st.write(f"- Top weekdays: {', '.join(upload_timing.get('top_weekdays', [])) or 'n/a'}")
        st.write(f"- Recommendation: {upload_timing.get('recommendation', 'No timing note yet.')}")

        derived_timing = result.get("timing_analysis")
        if derived_timing:
            st.write("")
            st.markdown("**Phase 13 timing engine**")
            optimal = derived_timing.get("optimal_recommendation", {})
            st.write(f"- Best day: {optimal.get('day', 'n/a')}")
            st.write(f"- Best hour: {optimal.get('hour', 'n/a')}:00")
            st.write(f"- Confidence: {optimal.get('confidence', 'n/a')}")
            st.write(f"- Expected lift: {optimal.get('expected_improvement', 'n/a')}")


def render_brain_tab(result: dict[str, Any], show_raw_data: bool) -> None:
    st.markdown('<div class="section-title">Brain v2.0 Readout</div>', unsafe_allow_html=True)
    scorecard = result.get("internal_scorecard", {})
    score_cols = st.columns(4)
    score_cols[0].metric("Total runs", scorecard.get("total_runs", 0))
    score_cols[1].metric("Avg title score", scorecard.get("avg_title_score", 0))
    score_cols[2].metric("Avg opportunity", scorecard.get("avg_opportunity_score", 0))
    score_cols[3].metric("Dominant risk", scorecard.get("dominant_retention_risk", "unknown"))

    learning_cols = st.columns(2)
    with learning_cols[0]:
        st.markdown("#### Learning Engine")
        for item in result.get("learning_engine", {}).get("angle_effectiveness", []):
            st.write(f"- {item.get('content_angle')}: {item.get('avg_title_score')} avg title score")
        st.write(result.get("winning_patterns", {}).get("observation", ""))

    with learning_cols[1]:
        st.markdown("#### Workflow")
        workflow = result.get("automation_workflow", {})
        for item in workflow.get("pre_publish_checklist", []):
            st.write(f"- {item}")

    st.markdown("#### Historical Comparison")
    st.write(result.get("historical_comparison", {}).get("summary", "No historical comparison available yet."))

    if show_raw_data:
        st.markdown("#### Raw JSON")
        st.json(result)


def render_brain_insights() -> None:
    result = st.session_state.result
    st.markdown('<div class="section-title">Brain Insights</div>', unsafe_allow_html=True)
    if not result:
        st.info("Run an analysis first to populate the Brain v2.0 panels.")
        return

    render_brain_tab(result, show_raw_data=True)


def render_upload_timing(ui: dict[str, Any]) -> None:
    result = st.session_state.result
    st.markdown('<div class="section-title">Upload Timing Optimizer</div>', unsafe_allow_html=True)
    if not result:
        st.info("Run an analysis first so the timing engine can use competitor publish data.")
        return

    derived = result.get("timing_analysis")
    if not derived:
        st.warning("Not enough published competitor timestamps were available to build the timing panel.")
        return

    optimal = derived.get("optimal_recommendation", {})
    backups = derived.get("backup_options", {})

    metrics = st.columns(4)
    metrics[0].metric("Best day", str(optimal.get("day", "n/a")).title())
    metrics[1].metric("Best hour", f"{optimal.get('hour', 'n/a')}:00")
    metrics[2].metric("Confidence", optimal.get("confidence", "n/a"))
    metrics[3].metric("Expected lift", optimal.get("expected_improvement", "n/a"))

    st.markdown(
        f"""
        <div class="callout">
          {html.escape(str(optimal.get('reasoning', 'No timing reasoning available.')))}
        </div>
        """,
        unsafe_allow_html=True,
    )

    backup_cols = st.columns(2)
    with backup_cols[0]:
        st.markdown("#### Backup Days")
        if backups.get("day_alternatives"):
            st.dataframe(backups["day_alternatives"], use_container_width=True, hide_index=True)
        else:
            st.caption("No backup day options yet.")
    with backup_cols[1]:
        st.markdown("#### Backup Hours")
        if backups.get("hour_alternatives"):
            st.dataframe(backups["hour_alternatives"], use_container_width=True, hide_index=True)
        else:
            st.caption("No backup hour options yet.")

    st.markdown("#### Input Notes")
    st.write("- This panel uses current competitor publish timestamps as an inference source.")
    st.write(f"- Creator timezone: {ui['creator_timezone']}")
    st.write(f"- Target audience: {ui['target_audience']}")


def render_post_upload(ui: dict[str, Any]) -> None:
    st.markdown('<div class="section-title">Post-Upload Monitor</div>', unsafe_allow_html=True)
    result = st.session_state.result
    default_title = str(result.get("title", "")) if result else ""
    default_ctr = float(result.get("ctr_prediction", {}).get("predicted_ctr_percent", 5.0)) if result else 5.0
    default_angle = str(result.get("content_angle", "general")) if result else "general"

    with st.form("post_upload_form"):
        title = st.text_input("Video title", value=default_title)
        form_cols = st.columns(3)
        views_24h = form_cols[0].number_input("Views in first 24h", min_value=0, value=200)
        clicks_24h = form_cols[1].number_input("Clicks in first 24h", min_value=0, value=15)
        likes = form_cols[2].number_input("Likes", min_value=0, value=12)

        form_cols_2 = st.columns(3)
        comments = form_cols_2[0].number_input("Comments", min_value=0, value=4)
        avg_watch_duration = form_cols_2[1].number_input("Avg watch duration (sec)", min_value=0.0, value=95.0)
        expected_ctr = form_cols_2[2].number_input("Expected CTR %", min_value=0.0, value=default_ctr)

        submitted = st.form_submit_button("Run Post-Upload Check", use_container_width=True)

    if submitted:
        st.session_state.post_upload_result = get_post_upload_recommendations(
            video_id="manual_check",
            title=title,
            views_24h=int(views_24h),
            clicks_24h=int(clicks_24h),
            likes=int(likes),
            comments=int(comments),
            avg_watch_duration=float(avg_watch_duration),
            expected_ctr_percent=float(expected_ctr),
            content_angle=default_angle,
        )

    post_result = st.session_state.post_upload_result
    if not post_result:
        st.caption("Fill in your first-24-hour metrics to generate emergency recommendations.")
        return

    monitor = post_result.get("monitoring_status", {})
    engagement = post_result.get("engagement_health", {})
    retention = post_result.get("retention_health", {})
    cols = st.columns(4)
    cols[0].metric("Alert level", monitor.get("alert_level", "UNKNOWN"))
    cols[1].metric("Actual CTR", f"{monitor.get('actual_ctr_percent', 0)}%")
    cols[2].metric("CTR delta", f"{monitor.get('ctr_delta_percent', 0)}%")
    cols[3].metric("Next check", f"{post_result.get('next_check_hours', 0)}h")

    st.write(f"Engagement health: {engagement.get('status', 'unknown')}")
    st.write(f"Retention health: {retention.get('status', 'unknown')} - {retention.get('interpretation', '')}")

    st.markdown("#### Emergency Recommendations")
    recommendations = post_result.get("emergency_recommendations", [])
    if not recommendations:
        st.success("No emergency action is needed right now. The video is within a healthy range.")
    for item in recommendations:
        st.markdown(
            f"""
            <div class="info-card">
              <strong>P{item.get('priority', '?')} - {html.escape(str(item.get('action', 'Action')))}</strong><br>
              <span class="section-copy">{html.escape(str(item.get('description', '')))}</span><br>
              <span class="section-copy">Expected impact: {html.escape(str(item.get('expected_impact', 'n/a')))}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for tactic in item.get("tactics", []):
            st.write(f"- {tactic}")


def render_psychology(ui: dict[str, Any]) -> None:
    st.markdown('<div class="section-title">Psychology Analysis</div>', unsafe_allow_html=True)
    result = st.session_state.result
    default_title = str(result.get("title", "")) if result else ""
    default_description = str(result.get("description", "")) if result else ""

    with st.form("psychology_form"):
        title = st.text_input("Title to analyze", value=default_title)
        description = st.text_area("Description to analyze", value=default_description, height=180)
        submitted = st.form_submit_button("Analyze Psychology", use_container_width=True)

    if submitted:
        st.session_state.psychology_result = analyze_content_psychology(title=title, description=description)

    psychology = st.session_state.psychology_result
    if not psychology and result:
        psychology = result.get("psychology_analysis")
    if not psychology:
        st.caption("Analyze a title and description to inspect curiosity, urgency, emotion, and social proof.")
        return

    title_analysis = psychology.get("title_analysis", {})
    components = title_analysis.get("components", {})
    cols = st.columns(5)
    cols[0].metric("Composite", title_analysis.get("composite_score", 0), title_analysis.get("strength_level", ""))
    cols[1].metric("Curiosity", components.get("curiosity_gap", {}).get("score", 0))
    cols[2].metric("Urgency", components.get("urgency_signals", {}).get("score", 0))
    cols[3].metric("Emotion", components.get("emotional_resonance", {}).get("score", 0))
    cols[4].metric("Social proof", components.get("social_proof", {}).get("score", 0))

    st.markdown("#### Recommendations")
    for recommendation in title_analysis.get("recommendations", []):
        st.write(f"- {recommendation.get('area')}: {recommendation.get('suggestion')}")

    description_analysis = psychology.get("description_analysis", {})
    if description_analysis:
        st.markdown("#### Description Hook")
        st.write(
            f"Hook quality: {description_analysis.get('hook_quality', {}).get('score', 0)} "
            f"({description_analysis.get('hook_quality', {}).get('feedback', '')})"
        )
        st.write(
            f"CTA effectiveness: {description_analysis.get('call_to_action', {}).get('effectiveness', 'unknown')}"
        )
        st.write(
            f"Engagement potential: {description_analysis.get('engagement_potential', 'unknown')}"
        )


def render_settings_help(settings: Any) -> None:
    st.markdown('<div class="section-title">Settings & Help</div>', unsafe_allow_html=True)
    history_status = HistoryStore(settings.database_path).system_status()
    st.markdown(
        """
        <div class="info-card">
          <div class="section-copy">
            This screen exists so the richer v4 interface and the default app stay in sync.
            The current `streamlit_app.py` and `streamlit_app_v4_polish.py` now share one implementation.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write(f"- YouTube API keys loaded: {len(settings.youtube_api_key_pool)}")
    st.write(f"- Database path: {settings.database_path}")
    st.write(f"- Stored analysis runs: {history_status.get('analysis_count', 0)}")
    st.write(f"- Recent snapshots: {history_status.get('snapshot_count', 0)}")
    st.write("- Use the left sidebar to switch modules and tune output behavior.")
    st.write("- Use the Optimizer page first to populate the advanced Phase 13 pages.")


def run_analysis(script: str, ui: dict[str, Any], detected_language: str | None) -> None:
    with st.status("Running Win-Engine pipeline...", expanded=True) as status:
        settings = get_settings()
        research = ResearchService(settings)
        research_language = normalize_language(ui["language_mode"], detected_language)
        status.write("Gathering competitor research...")
        research_payload = research.gather(script, region=ui["region"], primary_language=research_language)
        status.write("Generating packaging and strategic recommendations...")
        result = generate_seo_suggestions(
            script,
            research_payload,
            context={
                "language": "" if ui["language_mode"] == "Auto-detect" else research_language,
                "region": ui["region"],
                "audience_type": ui["audience_type"],
            },
        )

        if not ui["include_hashtags"]:
            result["hashtags"] = []

        result["selected_language"] = ui["language_mode"]
        result["selected_region"] = ui["region"]
        result["selected_audience_type"] = ui["audience_type"]
        result["selected_format"] = ui["script_format"]
        result["selected_niche"] = ui["niche"]
        result["selected_energy"] = ui["energy"]
        result["analysis_timestamp"] = datetime.utcnow().isoformat() + "Z"
        result["psychology_analysis"] = analyze_content_psychology(
            title=str(result.get("title", "")),
            description=str(result.get("description", "")),
            primary_topic=derive_primary_topic(result),
        )
        if ui["compare_competitors"]:
            result["timing_analysis"] = build_timing_analysis(result, ui)
        status.update(label="Package ready.", state="complete", expanded=False)

    st.session_state.result = result
    st.session_state.analysis_history.append({"script": script, "result": copy.deepcopy(result)})
    st.session_state.analysis_history = st.session_state.analysis_history[-12:]


def build_timing_analysis(result: dict[str, Any], ui: dict[str, Any]) -> dict[str, Any] | None:
    history = []
    for item in result.get("youtube_results", []):
        published_at = str(item.get("published_at", "")).strip()
        if not published_at:
            continue
        try:
            published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError:
            continue

        views = to_int(item.get("view_count"))
        likes = to_int(item.get("like_count"))
        comments = to_int(item.get("comment_count"))
        engagement_score = ((likes * 0.3) + (comments * 0.7)) / max(views, 1) if views else 0.0
        history.append(
            {
                "upload_day": published_dt.strftime("%A").lower(),
                "upload_hour": published_dt.hour,
                "views_24h": views,
                "likes": likes,
                "comments": comments,
                "engagement_score": round(engagement_score, 4),
            }
        )

    if len(history) < 2:
        return None

    return get_optimal_upload_time(
        video_history=history,
        creator_timezone=ui["creator_timezone"],
        content_angle=str(result.get("content_angle", "general")),
        target_audience=ui["target_audience"],
    )


def build_tags(result: dict[str, Any]) -> list[str]:
    explicit_tags = result.get("tags", [])
    if explicit_tags:
        return dedupe_preserve_order([str(item) for item in explicit_tags])[:12]

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
              background: linear-gradient(135deg, #ff6b35 0%, #f43f5e 100%);
              border: none;
              color: white;
              padding: 0.78rem 1rem;
              border-radius: 12px;
              font-weight: 700;
              cursor: pointer;
            "
          >
            {safe_label}
          </button>
        </div>
        """,
        height=58,
    )


def detect_language(text: str) -> str | None:
    if not text or TamilLanguageDetector is None:
        return None
    try:
        detection = TamilLanguageDetector.detect_language(text)
    except Exception:  # noqa: BLE001 - UI fallback
        return None
    language = str(detection.get("language", "")).strip()
    return language or None


def normalize_language(selection: str, detected_language: str | None) -> str:
    if selection == "Auto-detect" and detected_language:
        mapping = {"Tamil": "tamil", "English": "english"}
        return mapping.get(detected_language, "english")

    mapping = {
        "Auto-detect": "english",
        "English": "english",
        "Tamil": "tamil",
        "Gen-Z Slang": "english",
    }
    return mapping.get(selection, "english")


def derive_primary_topic(result: dict[str, Any]) -> str:
    keyword_signals = result.get("keyword_signals", [])
    if keyword_signals:
        return str(keyword_signals[0].get("keyword", "")).strip()
    return str(result.get("title", "")).strip()


def to_int(value: Any) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"
