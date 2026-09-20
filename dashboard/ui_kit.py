"""Styling and small display helpers shared by the dashboard pages."""

import html
import json
from typing import Any

import streamlit as st

TONES = ("ok", "bad", "warn", "info", "neutral")

CSS = """
<style>
.block-container {max-width: 1250px; padding-top: 2.2rem;}

/* Type scale: the default page title is oversized for a working tool. */
h1 {font-size: 2rem !important; font-weight: 700 !important;
    letter-spacing: -0.015em; padding-bottom: 0.25rem;}
h2, h3 {letter-spacing: -0.01em;}
[data-testid="stSidebar"] h1 {font-size: 1.35rem !important;}

/* Metric cards */
[data-testid="stMetric"] {
    border: 1px solid #d5e3dc; border-radius: 10px;
    padding: 0.85rem 1rem; background: #f7faf8;
}
[data-testid="stMetricLabel"] {color: #4a675d;}
[data-testid="stMetricValue"] {font-variant-numeric: tabular-nums;}

/* Status pills: colour is paired with a dot and a word, never colour alone. */
.pill-row {display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.25rem 0 1rem;}
.pill {
    display: inline-flex; align-items: center; gap: 0.45rem;
    padding: 0.12rem 0.7rem; border-radius: 999px; border: 1px solid;
    font-size: 0.86rem; font-weight: 600; line-height: 1.7;
}
.pill::before {
    content: ""; width: 0.5rem; height: 0.5rem; border-radius: 50%;
    background: currentColor;
}
.pill-ok {background: #e4f4ec; color: #14603c; border-color: #bfe3d0;}
.pill-bad {background: #fbeceb; color: #9c2f28; border-color: #f0c5c1;}
.pill-warn {background: #fdf3df; color: #7d5006; border-color: #f0dcae;}
.pill-info {background: #e6f0f7; color: #1d5f8f; border-color: #c2d9ea;}
.pill-neutral {background: #eef2f0; color: #3e5a51; border-color: #d5dfda;}

/* Result banner: the one loud element on a report. */
.verdict {
    border: 1px solid; border-left-width: 6px; border-radius: 10px;
    padding: 0.85rem 1.1rem; margin: 0.5rem 0 1rem;
}
.verdict-title {font-size: 1.2rem; font-weight: 700; letter-spacing: -0.01em;}
.verdict-line {margin-top: 0.2rem; font-size: 0.95rem;}
.verdict-ok {background: #eef8f2; border-color: #1c7a4f; color: #14603c;}
.verdict-warn {background: #fff8e8; border-color: #b7791f; color: #6b4304;}
.verdict-bad {background: #fdf1f0; border-color: #b23a32; color: #8a2a24;}
.verdict-info {background: #eef5fa; border-color: #2a6f9e; color: #1d5f8f;}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def pill(text: str, tone: str = "neutral") -> str:
    tone = tone if tone in TONES else "neutral"
    return f'<span class="pill pill-{tone}">{html.escape(str(text))}</span>'


def pill_row(*pills: str) -> None:
    st.markdown(
        f'<div class="pill-row">{"".join(pills)}</div>', unsafe_allow_html=True
    )


def verdict(title: str, lines: list[str] | None = None, tone: str = "info") -> None:
    tone = tone if tone in TONES else "info"
    body = "".join(
        f'<div class="verdict-line">{html.escape(line)}</div>'
        for line in (lines or [])
    )
    st.markdown(
        f'<div class="verdict verdict-{tone}">'
        f'<div class="verdict-title">{html.escape(title)}</div>{body}</div>',
        unsafe_allow_html=True,
    )


def table(data: Any, **kwargs: Any) -> None:
    """Full-width dataframe without an index, across Streamlit versions."""
    try:
        st.dataframe(data, hide_index=True, width="stretch", **kwargs)
    except (TypeError, ValueError):
        st.dataframe(data, hide_index=True, use_container_width=True, **kwargs)


def short(value: Any, limit: int = 160) -> str:
    """One-line preview of any value, for tables."""
    text = (
        value
        if isinstance(value, str)
        else json.dumps(value, ensure_ascii=False, default=str)
    )
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def fmt_ms(value: float | None) -> str:
    if value is None:
        return "—"
    if value < 1000:
        return f"{value:,.0f} ms"
    if value < 60_000:
        return f"{value / 1000:.1f} s"
    return f"{value / 60_000:.1f} min"
