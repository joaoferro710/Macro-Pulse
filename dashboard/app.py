"""Streamlit dashboard for the macro-pulse project."""

from __future__ import annotations

import logging
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from agent.macro_agent import generate_briefing, get_latest_briefing
from analytics.anomaly_detector import analyze_series
from analytics.regime_detector import get_global_macro_snapshot
from ingestion.loader import get_connection, get_series, load_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)

TOPIC_OPTIONS = [
    "visão geral",
    "Brasil",
    "EUA",
    "riscos e alertas",
    "câmbio e commodities",
]

SERIES_ORDER = [
    "FEDFUNDS",
    "CPIAUCSL",
    "UNRATE",
    "GDP",
    "T10Y2Y",
    "432",
    "13522",
    "1",
    "4380",
    "EWZ",
    "SPY",
    "USD/BRL",
]


def _inject_styles() -> None:
    """Apply lightweight dashboard styling."""

    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(246, 218, 174, 0.35), transparent 26%),
                radial-gradient(circle at top right, rgba(117, 173, 219, 0.20), transparent 28%),
                linear-gradient(180deg, #f8f4ec 0%, #f2eee6 100%);
        }
        .block-container {
            padding-top: 2.2rem;
            padding-bottom: 3rem;
            max-width: 1220px;
        }
        .macro-card {
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid rgba(30, 41, 59, 0.08);
            border-radius: 18px;
            padding: 1rem 1rem 0.85rem 1rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
            min-height: 180px;
        }
        .macro-label {
            color: #6b7280;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.35rem;
        }
        .macro-value {
            color: #111827;
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }
        .macro-meta {
            color: #374151;
            font-size: 0.92rem;
            margin-bottom: 0.35rem;
        }
        .macro-badge {
            display: inline-block;
            border-radius: 999px;
            padding: 0.24rem 0.6rem;
            font-size: 0.78rem;
            font-weight: 700;
        }
        .macro-badge.good {
            background: rgba(22, 163, 74, 0.12);
            color: #166534;
        }
        .macro-badge.alert {
            background: rgba(220, 38, 38, 0.12);
            color: #991b1b;
        }
        .macro-section {
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid rgba(30, 41, 59, 0.08);
            border-radius: 24px;
            padding: 1.3rem 1.3rem 1.1rem 1.3rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
            margin-top: 1rem;
        }
        .regime-pill {
            display: inline-block;
            border-radius: 999px;
            padding: 0.3rem 0.7rem;
            font-size: 0.8rem;
            font-weight: 700;
            margin-right: 0.4rem;
        }
        .regime-normal, .regime-expansao, .regime-estabilidade {
            background: rgba(22, 163, 74, 0.12);
            color: #166534;
        }
        .regime-flat {
            background: rgba(217, 119, 6, 0.14);
            color: #92400e;
        }
        .regime-inverted, .regime-contracao, .regime-estagflacao {
            background: rgba(220, 38, 38, 0.12);
            color: #991b1b;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=600)
def load_indicator_catalog() -> pd.DataFrame:
    """Load the current indicator catalog from DuckDB."""

    with get_connection() as connection:
        dataframe = connection.execute(
            """
            SELECT DISTINCT series_id, series_name, source
            FROM economic_indicators
            """
        ).fetchdf()

    dataframe["sort_key"] = dataframe["series_id"].apply(
        lambda series_id: SERIES_ORDER.index(series_id) if series_id in SERIES_ORDER else 999
    )
    return dataframe.sort_values(["sort_key", "series_name"]).drop(columns=["sort_key"])


@st.cache_data(ttl=600)
def load_latest_indicator_cards() -> list[dict[str, Any]]:
    """Build card-ready latest indicator summaries."""

    catalog = load_indicator_catalog()
    cards: list[dict[str, Any]] = []
    for row in catalog.itertuples(index=False):
        series_df = get_series(row.series_id, n_periods=2)
        if series_df.empty:
            continue
        latest = series_df.iloc[-1]
        previous = series_df.iloc[-2] if len(series_df) > 1 else latest
        delta = float(latest["value"]) - float(previous["value"])
        analysis = analyze_series(row.series_id, n_periods=min(60, max(24, len(get_series(row.series_id, 60)))))
        latest_anomaly = False
        if not analysis["zscore_result"].empty:
            latest_anomaly = bool(analysis["zscore_result"].iloc[-1]["is_anomaly"])

        cards.append(
            {
                "series_id": row.series_id,
                "series_name": row.series_name,
                "source": row.source,
                "date": pd.to_datetime(latest["date"]).date().isoformat(),
                "value": float(latest["value"]),
                "delta": delta,
                "is_anomaly": latest_anomaly,
            }
        )
    return cards


@st.cache_data(ttl=600)
def load_source_status() -> pd.DataFrame:
    """Return latest load timestamps by source."""

    with get_connection() as connection:
        dataframe = connection.execute(
            """
            SELECT source, MAX(loaded_at) AS last_loaded_at, COUNT(*) AS total_rows
            FROM economic_indicators
            GROUP BY source
            ORDER BY source
            """
        ).fetchdf()
    return dataframe


def refresh_all_data() -> dict[str, int]:
    """Reload all sources and invalidate Streamlit caches."""

    counts = load_all()
    load_indicator_catalog.clear()
    load_latest_indicator_cards.clear()
    load_source_status.clear()
    return counts


def _format_delta(delta: float) -> str:
    """Format the delta between the latest two observations."""

    arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
    return f"{arrow} {delta:,.2f}"


def _build_card_html(card: dict[str, Any]) -> str:
    """Render one indicator card as HTML."""

    badge_class = "alert" if card["is_anomaly"] else "good"
    badge_label = "Anomalia detectada" if card["is_anomaly"] else "Normal"
    return f"""
    <div class="macro-card">
        <div class="macro-label">{card['source']} · {card['series_id']}</div>
        <div class="macro-value">{card['value']:,.2f}</div>
        <div class="macro-meta">{card['series_name']}</div>
        <div class="macro-meta">Variação vs. período anterior: {_format_delta(card['delta'])}</div>
        <div class="macro-meta">Última data: {card['date']}</div>
        <span class="macro-badge {badge_class}">{badge_label}</span>
    </div>
    """


def _build_chart_dataframe(series_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Prepare chart and anomaly data for one series."""

    series_df = get_series(series_id=series_id, n_periods=36)
    series_df["date"] = pd.to_datetime(series_df["date"])
    analysis = analyze_series(series_id=series_id, n_periods=36)
    anomaly_df = analysis["zscore_result"].copy()
    anomaly_df["date"] = pd.to_datetime(anomaly_df["date"])
    anomaly_df = anomaly_df.loc[anomaly_df["is_anomaly"]]
    return series_df, anomaly_df


def _render_regime_header(snapshot: dict[str, Any]) -> None:
    """Render a compact regime banner above the chart."""

    us_regime = snapshot["united_states"]["current_regime"]
    br_regime = snapshot["brazil"]["current_regime"]
    st.markdown(
        (
            f"<span class='regime-pill regime-{us_regime}'>EUA: {us_regime}</span>"
            f"<span class='regime-pill regime-{br_regime}'>Brasil: {br_regime}</span>"
        ),
        unsafe_allow_html=True,
    )


def _render_time_series_chart(series_id: str, snapshot: dict[str, Any]) -> None:
    """Render the selected time series with anomalies highlighted."""

    series_df, anomaly_df = _build_chart_dataframe(series_id)
    if series_df.empty:
        st.info("Sem dados para a série selecionada.")
        return

    regime_label = snapshot["brazil"]["current_regime"] if series_id in {"432", "13522", "1", "4380", "EWZ", "USD/BRL"} else snapshot["united_states"]["current_regime"]
    regime_color = {
        "normal": "#d1fae5",
        "expansao": "#d1fae5",
        "estabilidade": "#ecfccb",
        "flat": "#fef3c7",
        "inverted": "#fee2e2",
        "contracao": "#fee2e2",
        "estagflacao": "#fecaca",
    }.get(regime_label, "#e5e7eb")

    background_df = pd.DataFrame(
        {
            "start": [series_df["date"].min()],
            "end": [series_df["date"].max()],
            "regime": [regime_label],
        }
    )

    base = alt.Chart(series_df).encode(x=alt.X("date:T", title="Data"))
    background = alt.Chart(background_df).mark_rect(opacity=0.2, color=regime_color).encode(
        x="start:T",
        x2="end:T",
    )
    line = base.mark_line(color="#0f4c81", strokeWidth=3).encode(
        y=alt.Y("value:Q", title="Valor"),
        tooltip=[
            alt.Tooltip("date:T", title="Data"),
            alt.Tooltip("value:Q", title="Valor", format=",.2f"),
        ],
    )
    points = (
        alt.Chart(anomaly_df)
        .mark_circle(size=120, color="#d62828")
        .encode(
            x="date:T",
            y="value:Q",
            tooltip=[
                alt.Tooltip("date:T", title="Data"),
                alt.Tooltip("value:Q", title="Valor", format=",.2f"),
                alt.Tooltip("zscore:Q", title="Z-score", format=",.2f"),
            ],
        )
    )

    chart = (background + line + points).properties(height=360)
    st.altair_chart(chart, use_container_width=True)

    if anomaly_df.empty:
        st.caption("Nenhuma anomalia por Z-score foi detectada nos últimos 36 períodos.")
    else:
        st.caption("Pontos vermelhos destacam anomalias detectadas por Z-score.")


def _render_sidebar(snapshot: dict[str, Any]) -> None:
    """Render the dashboard sidebar with source status and controls."""

    st.sidebar.markdown("## Macro Pulse")
    st.sidebar.caption("Status operacional das fontes e visão rápida de regime.")

    if st.sidebar.button("Atualizar Dados", use_container_width=True):
        with st.spinner("Atualizando FRED, BCB e Alpha Vantage..."):
            counts = refresh_all_data()
        st.sidebar.success(
            "Dados atualizados: "
            + ", ".join(f"{source}={total}" for source, total in counts.items())
        )

    st.sidebar.markdown("### Regimes atuais")
    st.sidebar.markdown(
        f"<span class='regime-pill regime-{snapshot['united_states']['current_regime']}'>"
        f"EUA: {snapshot['united_states']['current_regime']}</span>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f"<span class='regime-pill regime-{snapshot['brazil']['current_regime']}'>"
        f"Brasil: {snapshot['brazil']['current_regime']}</span>",
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("### Status das fontes")
    for row in load_source_status().itertuples(index=False):
        last_loaded = pd.to_datetime(row.last_loaded_at)
        st.sidebar.markdown(
            f"**{row.source}**  \nÚltima atualização: {last_loaded:%Y-%m-%d %H:%M}  \nLinhas: {row.total_rows:,}"
        )


def main() -> None:
    """Run the Streamlit dashboard app."""

    st.set_page_config(
        page_title="Macro Pulse",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()

    snapshot = get_global_macro_snapshot()
    _render_sidebar(snapshot)

    st.title("Macro Pulse")
    st.caption(
        "Painel macroeconômico com indicadores reais, detecção de anomalias e briefings automatizados."
    )

    st.markdown('<div class="macro-section">', unsafe_allow_html=True)
    st.subheader("Painel de Indicadores")
    cards = load_latest_indicator_cards()
    first, second, third = st.columns(3)
    columns = [first, second, third]
    for index, card in enumerate(cards):
        with columns[index % 3]:
            st.markdown(_build_card_html(card), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="macro-section">', unsafe_allow_html=True)
    st.subheader("Gráficos de Séries Temporais")
    catalog = load_indicator_catalog()
    series_options = {
        f"{row.series_name} ({row.series_id})": row.series_id for row in catalog.itertuples(index=False)
    }
    selected_label = st.selectbox(
        "Escolha a série para visualizar os últimos 36 períodos",
        options=list(series_options.keys()),
        index=list(series_options.values()).index("T10Y2Y")
        if "T10Y2Y" in series_options.values()
        else 0,
    )
    selected_series_id = series_options[selected_label]
    _render_regime_header(snapshot)
    _render_time_series_chart(selected_series_id, snapshot)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="macro-section">', unsafe_allow_html=True)
    st.subheader("Briefing do Agente")
    briefing_topic = st.selectbox("Tópico do briefing", TOPIC_OPTIONS)
    if st.button("Gerar Novo Briefing", type="primary"):
        with st.spinner("Gerando briefing com o agente macroeconômico..."):
            try:
                generate_briefing(briefing_topic)
                st.success("Briefing gerado com sucesso.")
            except Exception as exc:
                LOGGER.exception("Failed to generate briefing.")
                st.error(f"Não foi possível gerar o briefing: {exc}")

    latest_briefing = get_latest_briefing()
    if latest_briefing is None:
        st.info("Nenhum briefing foi gerado ainda.")
    else:
        generated_at = pd.to_datetime(latest_briefing["generated_at"])
        st.caption(
            f"Tópico: {latest_briefing['topic']} · Gerado em {generated_at:%Y-%m-%d %H:%M:%S}"
        )
        st.markdown(latest_briefing["content"])
        st.text_area(
            "Conteúdo bruto do briefing",
            value=latest_briefing["content"],
            height=260,
        )
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
