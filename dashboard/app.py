"""Streamlit dashboard for the macro-pulse project."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import altair as alt
import httpx
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

from agent.macro_agent import generate_briefing, get_latest_briefing
from analytics.anomaly_detector import analyze_series
from analytics.regime_detector import get_global_macro_snapshot
from ingestion.loader import get_connection, get_series, load_all

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
DEFAULT_LANG = "pt"
INITIAL_INVESTMENT_USD = 10_000.0
SERIES_ORDER = ["FEDFUNDS", "CPIAUCSL", "UNRATE", "GDP", "T10Y2Y", "432", "13522", "1", "4380", "EWZ", "SPY", "USD/BRL"]
TOPIC_OPTIONS = {
    "pt": {"overview": "visão geral", "brazil": "Brasil", "us": "EUA", "risks": "riscos e alertas", "fx": "câmbio e commodities"},
    "en": {"overview": "overall view", "brazil": "Brazil", "us": "United States", "risks": "risks and alerts", "fx": "FX and commodities"},
}
COPY = {
    "pt": {
        "caption": "Painel macroeconômico com indicadores reais, anomalias quantitativas e briefings automatizados.",
        "sidebar": "Status das fontes, regimes atuais e controle de atualização.",
        "refresh": "Atualizar dados", "refreshing": "Atualizando FRED, BCB e Alpha Vantage...",
        "indicators": "Painel de indicadores", "charts": "Gráficos de séries temporais",
        "pick_series": "Escolha a série para visualizar os últimos 36 períodos",
        "briefing": "Briefing do agente", "topic": "Tópico do briefing", "generate": "Gerar novo briefing",
        "generating": "Gerando briefing com o agente macroeconômico...", "generated": "Briefing gerado com sucesso.",
        "briefing_error": "Não foi possível gerar o briefing", "raw": "Conteúdo bruto do briefing",
        "compare": "Comparativo BR x EUA", "compare_caption": "Comparação ilustrativa com USD 10.000 investidos em cada ativo de mercado do escopo.",
        "compare_intro": "O objetivo aqui é comparar o comportamento do mesmo capital em EWZ e SPY ao longo dos últimos 12 meses, identificar qual mercado remunerou melhor e contextualizar uma leitura prudente para os próximos 3 meses.",
        "evolution": "Evolução simulada do investimento em 12 meses", "readout": "Leitura comparativa",
        "forecast": "Cenário ilustrativo para os próximos 3 meses", "disclaimer": "Este bloco é apenas uma leitura quantitativa do cenário atual. Não constitui recomendação de investimento.",
        "winner": "Melhor rendimento em 12 meses", "normal": "Normal", "anomaly": "Anomalia detectada",
        "variation": "Variação vs. período anterior", "last_date": "Última data", "no_briefing": "Nenhum briefing foi gerado ainda.",
        "translate_error": "Não foi possível traduzir o briefing automaticamente. Exibindo o texto original.",
        "no_data": "Sem dados para a série selecionada.", "no_anomalies": "Nenhuma anomalia por Z-score foi detectada nos últimos 36 períodos.",
        "anomaly_caption": "Pontos vermelhos destacam anomalias detectadas por Z-score.", "source_status": "Status das fontes",
        "regimes": "Regimes atuais", "rows": "Linhas", "updated": "Última atualização", "brazil": "Brasil", "us": "EUA",
        "asset": "Ativo", "market": "Mercado", "start": "Preço inicial", "end": "Preço final", "ret": "Retorno 12m",
        "final": "Valor final (USD)", "date": "Data", "value": "Valor", "constructive": "cenário construtivo",
        "neutral": "cenário neutro", "cautious": "cenário cauteloso", "briefing_topic": "Tópico",
    },
    "en": {
        "caption": "Macroeconomic dashboard with real indicators, quantitative anomalies and automated briefings.",
        "sidebar": "Source status, current regimes and refresh controls.",
        "refresh": "Refresh data", "refreshing": "Refreshing FRED, BCB and Alpha Vantage...",
        "indicators": "Indicator panel", "charts": "Time-series charts",
        "pick_series": "Choose a series to inspect the latest 36 periods",
        "briefing": "Agent briefing", "topic": "Briefing topic", "generate": "Generate new briefing",
        "generating": "Generating the macro briefing...", "generated": "Briefing generated successfully.",
        "briefing_error": "Unable to generate the briefing", "raw": "Raw briefing content",
        "compare": "Brazil vs US comparison", "compare_caption": "Illustrative comparison assuming USD 10,000 invested in each in-scope market asset.",
        "compare_intro": "The goal here is to compare how the same capital would have behaved in EWZ and SPY over the last 12 months, identify the stronger market and frame a cautious 3-month forward-looking view.",
        "evolution": "Illustrative 12-month investment path", "readout": "Comparative readout",
        "forecast": "Illustrative 3-month outlook", "disclaimer": "This section is only a quantitative interpretation of the current setup. It is not investment advice.",
        "winner": "Best 12-month performer", "normal": "Normal", "anomaly": "Anomaly detected",
        "variation": "Change vs. previous period", "last_date": "Latest date", "no_briefing": "No briefing has been generated yet.",
        "translate_error": "Unable to translate the briefing automatically. Showing the original text instead.",
        "no_data": "No data available for the selected series.", "no_anomalies": "No Z-score anomalies were detected in the last 36 periods.",
        "anomaly_caption": "Red points highlight Z-score anomalies.", "source_status": "Source status",
        "regimes": "Current regimes", "rows": "Rows", "updated": "Last update", "brazil": "Brazil", "us": "United States",
        "asset": "Asset", "market": "Market", "start": "Start price", "end": "End price", "ret": "12M return",
        "final": "Final value (USD)", "date": "Date", "value": "Value", "constructive": "constructive setup",
        "neutral": "neutral setup", "cautious": "cautious setup", "briefing_topic": "Topic",
    },
}


def tr(key: str) -> str:
    return COPY[st.session_state.get("lang", DEFAULT_LANG)][key]


def _styles() -> None:
    st.markdown(
        """
        <style>
        .stApp{background:radial-gradient(circle at top left,rgba(246,218,174,.35),transparent 26%),radial-gradient(circle at top right,rgba(117,173,219,.2),transparent 28%),linear-gradient(180deg,#f8f4ec 0%,#f2eee6 100%)}
        [data-testid="stHeader"]{background:transparent;height:0;visibility:hidden}
        .block-container{padding-top:3.2rem;padding-left:2rem;padding-right:2rem;max-width:1220px}
        section[data-testid="stSidebar"]{background:linear-gradient(180deg,#1e2d40 0%,#162236 100%);color:#e2e8f0}
        section[data-testid="stSidebar"] .stButton button{border-radius:10px;font-weight:600}
        .macro-section,.card{background:rgba(255,255,255,.92);border:1px solid rgba(30,41,59,.08);box-shadow:0 10px 30px rgba(15,23,42,.06)}
        .macro-section{border-radius:24px;padding:1.25rem;margin-top:1rem}
        .card{border-radius:18px;padding:1rem;min-height:160px;height:100%;display:flex;flex-direction:column;justify-content:space-between}
        .label{color:#6b7280;font-size:.82rem;text-transform:uppercase;letter-spacing:.08em}.value{font-size:1.55rem;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.meta{color:#374151;font-size:.92rem}
        .badge{display:inline-block;border-radius:999px;padding:.24rem .6rem;font-size:.78rem;font-weight:700}.good{background:rgba(22,163,74,.12);color:#166534}.bad{background:rgba(220,38,38,.12);color:#991b1b}
        .pill{display:inline-block;border-radius:999px;padding:.3rem .7rem;font-size:.8rem;font-weight:700;margin-right:.4rem}
        .regime-normal,.regime-expansao,.regime-estabilidade{background:rgba(22,163,74,.12);color:#166534}.regime-flat{background:rgba(217,119,6,.14);color:#92400e}.regime-inverted,.regime-contracao,.regime-estagflacao{background:rgba(220,38,38,.12);color:#991b1b}
        .note{background:rgba(245,247,250,.96);border:1px solid rgba(30,41,59,.08);border-radius:18px;padding:1rem;margin-top:.8rem}
        .source-box{background:rgba(255,255,255,.05);border-radius:10px;padding:.6rem .8rem;margin-bottom:.5rem}
        ::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:rgba(15,76,129,.25);border-radius:3px}
        button:focus{outline:none!important;box-shadow:none!important}h2,h3{color:#1e293b!important;letter-spacing:-.01em}hr{border-color:rgba(30,41,59,.08)!important}
        @media (max-width:768px){.macro-section{padding:.75rem;border-radius:14px}.card{min-height:140px}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _groq_key() -> str | None:
    load_dotenv(dotenv_path=ENV_PATH)
    return os.getenv("GROQ_API_KEY")


def _groq_client() -> Groq:
    return Groq(
        api_key=_groq_key(),
        http_client=httpx.Client(trust_env=False, timeout=30.0),
    )


@st.cache_data(show_spinner=False, ttl=3600)
def translate_briefing(content: str, target_lang: str) -> str:
    if target_lang == "pt" or not content.strip():
        return content
    api_key = _groq_key()
    if not api_key:
        return content
    client = _groq_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        max_tokens=900,
        messages=[
            {"role": "system", "content": "Translate this Brazilian Portuguese macroeconomic briefing into English. Preserve numbers, dates and indicator names. Return only the translation."},
            {"role": "user", "content": content},
        ],
    )
    return response.choices[0].message.content or content


@st.cache_data(ttl=600)
def indicator_catalog() -> pd.DataFrame:
    with get_connection() as con:
        df = con.execute("SELECT DISTINCT series_id, series_name, source FROM economic_indicators").fetchdf()
    df["sort_key"] = df["series_id"].apply(lambda x: SERIES_ORDER.index(x) if x in SERIES_ORDER else 999)
    return df.sort_values(["sort_key", "series_name"]).drop(columns=["sort_key"])


@st.cache_data(ttl=600)
def source_status() -> pd.DataFrame:
    with get_connection() as con:
        return con.execute("SELECT source, MAX(loaded_at) AS last_loaded_at, COUNT(*) AS total_rows FROM economic_indicators GROUP BY source ORDER BY source").fetchdf()


def refresh_data() -> dict[str, int]:
    counts = load_all()
    indicator_catalog.clear()
    source_status.clear()
    investment_comparison.clear()
    return counts


@st.cache_data(ttl=600)
def cards() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in indicator_catalog().itertuples(index=False):
        hist = get_series(row.series_id, n_periods=60)
        if hist.empty:
            continue
        latest = hist.iloc[-1]
        previous = hist.iloc[-2] if len(hist) > 1 else latest
        analysis = analyze_series(row.series_id, n_periods=min(60, len(hist)))
        latest_anomaly = bool(analysis["zscore_result"].iloc[-1]["is_anomaly"]) if not analysis["zscore_result"].empty else False
        out.append({"series_id": row.series_id, "series_name": row.series_name, "source": row.source, "date": pd.to_datetime(latest["date"]).date().isoformat(), "value": float(latest["value"]), "delta": float(latest["value"]) - float(previous["value"]), "is_anomaly": latest_anomaly})
    return out


def _chart_data(series_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    series_df = get_series(series_id, n_periods=36)
    series_df["date"] = pd.to_datetime(series_df["date"])
    anomaly_df = analyze_series(series_id, n_periods=36)["zscore_result"].copy()
    anomaly_df["date"] = pd.to_datetime(anomaly_df["date"])
    return series_df, anomaly_df.loc[anomaly_df["is_anomaly"]]


@st.cache_data(ttl=600)
def investment_comparison() -> dict[str, Any]:
    snapshot = get_global_macro_snapshot()
    rows: list[dict[str, Any]] = []
    evolution: list[dict[str, Any]] = []
    for series_id, region in [("EWZ", "BR"), ("SPY", "US")]:
        hist = get_series(series_id, n_periods=13).copy()
        hist["date"] = pd.to_datetime(hist["date"])
        start_price = float(hist.iloc[0]["value"])
        end_price = float(hist.iloc[-1]["value"])
        units = INITIAL_INVESTMENT_USD / start_price
        final_value = units * end_price
        return_pct = final_value / INITIAL_INVESTMENT_USD - 1
        for row in hist.itertuples(index=False):
            evolution.append({"date": pd.to_datetime(row.date), "series_id": series_id, "region": region, "portfolio_value": units * float(row.value)})
        recent = get_series(series_id, n_periods=4)
        momentum = (float(recent.iloc[-1]["value"]) / float(recent.iloc[0]["value"]) - 1) if len(recent) >= 2 else 0.0
        latest_anomaly = bool(analyze_series(series_id, n_periods=min(36, len(get_series(series_id, 36))))["zscore_result"].iloc[-1]["is_anomaly"])
        regime = snapshot["united_states"]["current_regime"] if region == "US" else snapshot["brazil"]["current_regime"]
        bias = {"normal": 0.015, "flat": 0.0, "inverted": -0.02}.get(regime, 0.0) if region == "US" else {"expansao": 0.02, "estabilidade": 0.005, "contracao": -0.015, "estagflacao": -0.025}.get(regime, 0.0)
        expected = max(min((momentum * 0.6) + bias + (-0.01 if latest_anomaly else 0.0), 0.12), -0.12)
        rows.append({"series_id": series_id, "region": region, "start_price": start_price, "end_price": end_price, "return_pct": return_pct, "final_value": final_value, "momentum_3m": momentum, "expected_return_3m": expected, "projected_value_3m": INITIAL_INVESTMENT_USD * (1 + expected), "regime": regime, "latest_anomaly": latest_anomaly, "outlook": "constructive" if expected >= 0.04 else "cautious" if expected <= -0.02 else "neutral", "end_date": hist.iloc[-1]["date"].date().isoformat()})
    table = pd.DataFrame(rows).sort_values("return_pct", ascending=False).reset_index(drop=True)
    evo = pd.DataFrame(evolution).sort_values(["date", "series_id"]).reset_index(drop=True)
    return {"table": table, "winner": table.iloc[0].to_dict(), "snapshot": snapshot, "evolution": evo}


def _region(code: str) -> str:
    return tr("brazil") if code == "BR" else tr("us")


def _language_toggle() -> None:
    col1, col2 = st.sidebar.columns(2)
    current = st.session_state.get("lang", DEFAULT_LANG)
    if col1.button("🇧🇷 Português", use_container_width=True, type="primary" if current == "pt" else "secondary"):
        if current != "pt":
            st.session_state["lang"] = "pt"
            st.rerun()
    if col2.button("🇺🇸 English", use_container_width=True, type="primary" if current == "en" else "secondary"):
        if current != "en":
            st.session_state["lang"] = "en"
            st.rerun()


def _sidebar(snapshot: dict[str, Any]) -> None:
    st.sidebar.markdown("<div style='font-size:1.3rem;font-weight:800;letter-spacing:.04em;color:#f0c040;padding-bottom:.5rem;'>📈 Macro Pulse</div>", unsafe_allow_html=True)
    st.sidebar.caption(tr("sidebar"))
    if st.sidebar.button(tr("refresh"), use_container_width=True):
        with st.spinner(tr("refreshing")):
            refresh_data()
        st.rerun()
    _language_toggle()
    st.sidebar.divider()
    st.sidebar.markdown(f"### {tr('regimes')}")
    st.sidebar.markdown(f"<span class='pill regime-{snapshot['united_states']['current_regime']}'>{tr('us')}: {snapshot['united_states']['current_regime']}</span>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<span class='pill regime-{snapshot['brazil']['current_regime']}'>{tr('brazil')}: {snapshot['brazil']['current_regime']}</span>", unsafe_allow_html=True)
    st.sidebar.divider()
    st.sidebar.markdown(f"### {tr('source_status')}")
    for row in source_status().itertuples(index=False):
        last_loaded = pd.to_datetime(row.last_loaded_at)
        st.sidebar.markdown(f"<div class='source-box'><b>{row.source}</b><br><span style='font-size:.8rem;color:#94a3b8'>{tr('updated')}: {last_loaded:%Y-%m-%d %H:%M}</span><br><span style='font-size:.8rem;color:#94a3b8'>{tr('rows')}: {row.total_rows:,}</span></div>", unsafe_allow_html=True)


def _render_cards() -> None:
    st.markdown('<div class="macro-section">', unsafe_allow_html=True)
    st.subheader(tr("indicators"))
    cols = st.columns(3)
    for idx, card in enumerate(cards()):
        with cols[idx % 3]:
            with st.container():
                badge = "bad" if card["is_anomaly"] else "good"
                label = tr("anomaly") if card["is_anomaly"] else tr("normal")
                arrow = "↑" if card["delta"] > 0 else "↓" if card["delta"] < 0 else "→"
                st.markdown(f"<div class='card'><div><div class='label'>{card['source']} · {card['series_id']}</div><div class='value'>{card['value']:,.2f}</div><div class='meta'>{card['series_name']}</div><div class='meta'>{tr('variation')}: {arrow} {card['delta']:,.2f}</div><div class='meta'>{tr('last_date')}: {card['date']}</div></div><div><span class='badge {badge}'>{label}</span></div></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_chart() -> None:
    st.markdown('<div class="macro-section">', unsafe_allow_html=True)
    st.subheader(tr("charts"))
    options = {f"[{row.source}] {row.series_name} ({row.series_id})": row.series_id for row in indicator_catalog().itertuples(index=False)}
    selected = st.selectbox(tr("pick_series"), options=list(options.keys()))
    series_df, anomaly_df = _chart_data(options[selected])
    if series_df.empty:
        st.info(tr("no_data"))
    else:
        base = alt.Chart(series_df).properties(height=360, title=alt.TitleParams(text=selected, fontSize=14, anchor="start"))
        line = base.mark_line(color="#0f4c81", strokeWidth=3, clip=True).encode(x=alt.X("date:T", title=tr("date")), y=alt.Y("value:Q", title=tr("value")), tooltip=[alt.Tooltip("date:T", title=tr("date")), alt.Tooltip("value:Q", title=tr("value"), format=",.2f")])
        points = alt.Chart(anomaly_df).mark_circle(size=120, color="#d62828", clip=True).encode(x="date:T", y="value:Q", tooltip=[alt.Tooltip("date:T", title=tr("date")), alt.Tooltip("value:Q", title=tr("value"), format=",.2f"), alt.Tooltip("zscore:Q", title="Z-score", format=",.2f")])
        chart = (line + points).configure_axis(labelFontSize=12, titleFontSize=13).configure_view(strokeWidth=0)
        st.altair_chart(chart, use_container_width=True)
        st.caption(tr("no_anomalies") if anomaly_df.empty else tr("anomaly_caption"))
    st.markdown("</div>", unsafe_allow_html=True)


def _render_briefing() -> None:
    st.markdown('<div class="macro-section">', unsafe_allow_html=True)
    st.subheader(tr("briefing"))
    topics = TOPIC_OPTIONS[st.session_state["lang"]]
    topic_key = st.selectbox(tr("topic"), options=list(topics.keys()), format_func=lambda k: topics[k])
    if st.button(tr("generate"), type="primary"):
        with st.spinner(tr("generating")):
            try:
                generate_briefing(topics[topic_key])
                st.success(tr("generated"))
                st.rerun()
            except Exception as exc:
                st.error(f"{tr('briefing_error')}: {exc}")
    latest = get_latest_briefing()
    if latest is None:
        st.info(tr("no_briefing"))
    else:
        display = latest["content"]
        if st.session_state["lang"] == "en":
            try:
                display = translate_briefing(latest["content"], "en")
            except Exception:
                st.warning(tr("translate_error"))
        generated_at = pd.to_datetime(latest["generated_at"])
        st.caption(f"🕐 {tr('briefing_topic')}: {latest['topic']} · {generated_at:%Y-%m-%d %H:%M:%S}")
        st.markdown(f"<div class='note'>{display}</div>", unsafe_allow_html=True)
        with st.expander(tr("raw"), expanded=False):
            st.text_area(tr("raw"), value=display, height=220)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_comparison() -> None:
    data = investment_comparison()
    table = data["table"]
    winner = data["winner"]
    ewz = table.loc[table["series_id"] == "EWZ"].iloc[0]
    spy = table.loc[table["series_id"] == "SPY"].iloc[0]
    st.markdown('<div class="macro-section">', unsafe_allow_html=True)
    st.subheader(tr("compare"))
    st.caption(tr("compare_caption"))
    st.markdown(tr("compare_intro"))
    top = st.columns(3)
    top[0].metric("EWZ 🇧🇷", f"USD {ewz['final_value']:,.2f}", delta=f"{ewz['return_pct']:+.2%}", delta_color="normal")
    top[1].metric("SPY 🇺🇸", f"USD {spy['final_value']:,.2f}", delta=f"{spy['return_pct']:+.2%}", delta_color="normal")
    top[2].metric(tr("winner"), f"{winner['series_id']}", delta=f"{winner['return_pct']:+.2%}", delta_color="normal")
    st.markdown(f"#### {tr('evolution')}")
    evo = data["evolution"].copy()
    evo["label"] = evo["series_id"] + " · " + evo["region"].map(_region)
    chart = alt.Chart(evo).mark_line(strokeWidth=3).encode(x=alt.X("date:T", title=tr("date")), y=alt.Y("portfolio_value:Q", title=tr("final")), color=alt.Color("label:N", title=tr("asset")), tooltip=[alt.Tooltip("date:T", title=tr("date")), alt.Tooltip("label:N", title=tr("asset")), alt.Tooltip("portfolio_value:Q", title=tr("final"), format=",.2f")]).configure_axis(labelFontSize=12, titleFontSize=13).configure_view(strokeWidth=0)
    st.altair_chart(chart.properties(height=320), use_container_width=True)
    shown = table.copy()
    shown["region"] = shown["region"].map(_region)
    shown["start_price"] = shown["start_price"].map(lambda v: f"{v:,.2f}")
    shown["end_price"] = shown["end_price"].map(lambda v: f"{v:,.2f}")
    shown["return_pct"] = shown["return_pct"].map(lambda v: f"{v:+.2%}")
    shown["final_value"] = shown["final_value"].map(lambda v: f"{v:,.2f}")
    st.dataframe(shown[["series_id", "region", "start_price", "end_price", "return_pct", "final_value"]].rename(columns={"series_id": tr("asset"), "region": tr("market"), "start_price": tr("start"), "end_price": tr("end"), "return_pct": tr("ret"), "final_value": tr("final")}), use_container_width=True, hide_index=True)
    summary = (
        f"Nos últimos 12 meses, USD {INITIAL_INVESTMENT_USD:,.0f} aplicados em EWZ teriam virado USD {ewz['final_value']:,.2f}, enquanto o mesmo valor em SPY teria chegado a USD {spy['final_value']:,.2f}. O recorte favoreceu o mercado {'brasileiro' if ewz['final_value'] > spy['final_value'] else 'americano'}, mas a leitura macro muda o contexto: os EUA seguem em regime {data['snapshot']['united_states']['current_regime']}, enquanto o Brasil está em {data['snapshot']['brazil']['current_regime']}."
        if st.session_state["lang"] == "pt"
        else f"Over the last 12 months, USD {INITIAL_INVESTMENT_USD:,.0f} invested in EWZ would have become USD {ewz['final_value']:,.2f}, while the same amount in SPY would have reached USD {spy['final_value']:,.2f}. The trailing edge favored the {'Brazilian' if ewz['final_value'] > spy['final_value'] else 'US'} market, but the macro backdrop changes the context: the US remains in a {data['snapshot']['united_states']['current_regime']} regime while Brazil sits in {data['snapshot']['brazil']['current_regime']}."
    )
    st.markdown(f"<div class='note'><strong>{tr('readout')}</strong><br><br>{summary}</div>", unsafe_allow_html=True)
    st.markdown(f"#### {tr('forecast')}")
    cols = st.columns(2)
    for col, row in zip(cols, [ewz, spy]):
        outlook = tr(row["outlook"])
        text = (
            f"**{row['series_id']} - {_region(row['region'])}**  \nLeitura atual: {outlook}.  \nMovimento recente de 3 meses: {row['momentum_3m']:.2%}.  \nProjeção ilustrativa de 3 meses: {row['expected_return_3m']:.2%}.  \nValor ilustrativo ao fim do período: USD {row['projected_value_3m']:,.2f}.  \nBase da leitura: regime {row['regime']}, último fechamento em {row['end_date']}."
            if st.session_state["lang"] == "pt"
            else f"**{row['series_id']} - {_region(row['region'])}**  \nCurrent read: {outlook}.  \nRecent 3-month move: {row['momentum_3m']:.2%}.  \nIllustrative 3-month projection: {row['expected_return_3m']:.2%}.  \nIllustrative end value: USD {row['projected_value_3m']:,.2f}.  \nReadout uses the {row['regime']} regime and latest close on {row['end_date']}."
        )
        col.markdown(f"<div class='note'>{text}</div>", unsafe_allow_html=True)
    st.caption(tr("disclaimer"))
    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="Macro Pulse", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
    if "lang" not in st.session_state:
        st.session_state["lang"] = DEFAULT_LANG
    _styles()
    snapshot = get_global_macro_snapshot()
    _sidebar(snapshot)
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.25rem;">
          <span style="font-size:2.2rem;">📈</span>
          <div>
            <div style="font-size:2rem;font-weight:800;line-height:1.1;background:linear-gradient(90deg,#0f4c81,#1a7fc1);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Macro Pulse</div>
            <div style="font-size:.85rem;color:#6b7280;letter-spacing:.05em;">Real-time macroeconomic intelligence</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_cards()
    _render_chart()
    _render_briefing()
    _render_comparison()


if __name__ == "__main__":
    main()
