
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px


# ============================================================
# CONFIGURACIÓN
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "football"
HIST = ROOT / "data" / "historical"

ALERTS_PATH = HIST / "alertas_enviadas.csv"
MASTER_PATH = ROOT / "data" / "processed" / "odds" / "master_odds.csv"


LEAGUE_NAMES = {
    "premier_league": "Premier League",
    "serie_a": "Serie A",
    "ligue_1": "Ligue 1",
    "la_liga": "La Liga",
    "bundesliga": "Bundesliga",
    "brasileirao": "Brasileirão",
    "primera_a_clausura": "Primera A Colombia",
}


MASTER_COLUMNS = [
    "timestamp_consulta",
    "run_id",
    "sport",
    "competition",
    "season",
    "fecha_partido",
    "local",
    "visitante",
    "mercado",
    "probabilidad_modelo",
    "cuota_teorica",
    "casa_apuestas",
    "cuota_real",
    "edge",
    "es_alerta",
    "resultado_real",
]


st.set_page_config(
    page_title="Bet App | Centro de análisis",
    page_icon="⚽",
    layout="wide",
)

st.title("Bet App | Centro de análisis")

st.caption(
    "Calendario, comparación de cuotas y seguimiento del desempeño. "
    "Las métricas financieras son simuladas cuando no hay apuestas "
    "ejecutadas registradas."
)


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def date_series(values, *, dayfirst=False):
    """Convierte valores a datetime sin zona horaria."""
    if not isinstance(values, pd.Series):
        values = pd.Series(values)

    parsed = pd.to_datetime(
        values,
        errors="coerce",
        dayfirst=dayfirst,
        utc=True,
    )

    return parsed.dt.tz_convert(None)


def numeric_series(df, column):
    """Convierte una columna a numérica."""
    if column in df.columns:
        return pd.to_numeric(
            df[column],
            errors="coerce",
        )

    return pd.Series(
        float("nan"),
        index=df.index,
        dtype="float64",
    )


def normalize_text(series):
    """Normaliza texto para facilitar los cruces."""
    return (
        series.astype("string")
        .str.strip()
        .str.casefold()
    )


# ============================================================
# CARGA DE PARTIDOS
# ============================================================

@st.cache_data(show_spinner=False)
def load_events():

    frames = []

    if not DATA.exists():
        return pd.DataFrame()

    for path in DATA.rglob("events.csv"):

        try:
            frame = pd.read_csv(path)

            if frame.empty:
                continue

            relative_parts = (
                path.parent.relative_to(DATA).parts
            )

            competition_key = (
                relative_parts[0]
                if relative_parts
                else path.parent.name
            )

            frame["competition_key"] = competition_key

            frame["competition_name"] = LEAGUE_NAMES.get(
                competition_key,
                competition_key,
            )

            frames.append(frame)

        except Exception as exc:
            st.warning(
                f"No se pudo leer {path}: {exc}"
            )

    if not frames:
        return pd.DataFrame()

    out = pd.concat(
        frames,
        ignore_index=True,
    )

    if "date" not in out.columns:
        out["date"] = pd.NaT

    out["date"] = date_series(
        out["date"]
    ).dt.normalize()

    for col in ("home_score", "away_score"):
        out[col] = numeric_series(out, col)

    for col in (
        "sport",
        "season",
        "home",
        "away",
        "status",
    ):
        if col not in out.columns:
            out[col] = pd.NA

    keys = [
        "sport",
        "competition_key",
        "season",
        "date",
        "home",
        "away",
    ]

    return (
        out.drop_duplicates(
            subset=keys,
            keep="last",
        )
        .reset_index(drop=True)
    )


# ============================================================
# CARGA DE ALERTAS
# ============================================================

@st.cache_data(show_spinner=False)
def load_alerts():

    if not ALERTS_PATH.exists():
        return pd.DataFrame()

    try:
        data = pd.read_csv(ALERTS_PATH)

    except Exception as exc:
        st.warning(
            f"No se pudo leer la bitácora de alertas: {exc}"
        )
        return pd.DataFrame()

    if data.empty:
        return data

    # Fecha de consulta.
    if "sent_at" in data.columns:
        data["timestamp_consulta"] = date_series(
            data["sent_at"]
        )

    elif "timestamp_consulta" not in data.columns:
        data["timestamp_consulta"] = pd.Series(
            pd.NaT,
            index=data.index,
            dtype="datetime64[ns]",
        )

    # Fecha del partido.
    if "fecha_partido" in data.columns:
        date_col = data["fecha_partido"]

    elif "fecha" in data.columns:
        date_col = data["fecha"]

    else:
        date_col = pd.Series(
            pd.NaT,
            index=data.index,
        )

    data["fecha_partido"] = date_series(
        date_col,
        dayfirst=True,
    ).dt.normalize()

    # Compatibilidad entre distintas versiones de archivos.
    aliases = {
        "competition": (
            "competition",
            "competicion",
            "liga",
        ),
        "local": (
            "local",
            "home",
            "equipo_local",
        ),
        "visitante": (
            "visitante",
            "away",
            "equipo_visitante",
        ),
        "mercado": (
            "mercado",
            "market",
        ),
        "cuota_real": (
            "cuota_real",
            "odd_real",
            "cuota_casa",
        ),
        "cuota_teorica": (
            "cuota_teorica",
            "odd_teorica",
        ),
        "edge": (
            "edge",
            "valor_esperado",
        ),
    }

    for target, candidates in aliases.items():

        if target not in data.columns:

            source = next(
                (
                    name
                    for name in candidates
                    if name in data.columns
                ),
                None,
            )

            data[target] = (
                data[source]
                if source
                else pd.NA
            )

    for col in (
        "cuota_real",
        "cuota_teorica",
        "edge",
        "probabilidad_modelo",
    ):
        data[col] = numeric_series(
            data,
            col,
        )

    if "es_alerta" not in data.columns:
        data["es_alerta"] = True

    if "casa_apuestas" not in data.columns:
        data["casa_apuestas"] = "WPlay"

    return data


# ============================================================
# CARGA DE TABLA MAESTRA
# ============================================================

@st.cache_data(show_spinner=False)
def load_master():

    if not MASTER_PATH.exists():
        return pd.DataFrame(
            columns=MASTER_COLUMNS
        )

    try:
        data = pd.read_csv(MASTER_PATH)

    except Exception as exc:
        st.warning(
            f"No se pudo leer la tabla maestra: {exc}"
        )

        return pd.DataFrame(
            columns=MASTER_COLUMNS
        )

    if data.empty:
        return pd.DataFrame(
            columns=MASTER_COLUMNS
        )

    for col in MASTER_COLUMNS:
        if col not in data.columns:
            data[col] = pd.NA

    data["timestamp_consulta"] = date_series(
        data["timestamp_consulta"]
    )

    data["fecha_partido"] = date_series(
        data["fecha_partido"]
    ).dt.normalize()

    for col in (
        "cuota_real",
        "cuota_teorica",
        "edge",
        "probabilidad_modelo",
    ):
        data[col] = numeric_series(
            data,
            col,
        )

    return data[MASTER_COLUMNS]


# ============================================================
# CARGA GENERAL
# ============================================================

events = load_events()
alerts = load_alerts()
master = load_master()


if events.empty:

    st.error(
        f"No se cargaron eventos desde {DATA}. "
        "Verifica que existan archivos events.csv."
    )

    st.stop()


# ============================================================
# RECUPERAR FECHAS DE ALERTAS ANTIGUAS
# ============================================================

# Algunas alertas históricas pueden no tener fecha de partido.
# Se recupera usando competición, local y visitante.

if (
    not alerts.empty
    and alerts["fecha_partido"].isna().all()
):

    lookup = events[
        [
            "competition_key",
            "date",
            "home",
            "away",
        ]
    ].drop_duplicates()

    # Se renombran las columnas del lookup para evitar
    # conflictos de nombres en el merge.
    lookup = lookup.rename(
        columns={
            "competition_key": "_lookup_competition",
            "date": "_lookup_date",
            "home": "_lookup_home",
            "away": "_lookup_away",
        }
    )

    alerts = alerts.merge(
        lookup,
        left_on=[
            "competition",
            "local",
            "visitante",
        ],
        right_on=[
            "_lookup_competition",
            "_lookup_home",
            "_lookup_away",
        ],
        how="left",
    )

    alerts["fecha_partido"] = alerts[
        "_lookup_date"
    ]


# ============================================================
# FILTROS GLOBALES
# ============================================================

now = pd.Timestamp.now().normalize()

valid_dates = events["date"].dropna()

if valid_dates.empty:

    st.error(
        "Los archivos events.csv no contienen fechas válidas."
    )

    st.stop()


min_date = valid_dates.min().date()
max_date = valid_dates.max().date()


with st.sidebar:

    st.header("Filtros globales")

    leagues = sorted(
        events["competition_name"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_leagues = st.multiselect(
        "Competición / liga",
        leagues,
        default=leagues,
    )

    mode = st.radio(
        "Periodo",
        [
            "Próximos",
            "Históricos",
            "Esta semana",
            "Próxima semana",
            "Todo",
            "Personalizado",
        ],
        index=0,
    )

    monday = now - pd.Timedelta(
        days=now.weekday()
    )

    if mode == "Próximos":

        start = now
        end = valid_dates.max()

    elif mode == "Históricos":

        start = valid_dates.min()
        end = now - pd.Timedelta(days=1)

    elif mode == "Esta semana":

        start = monday
        end = monday + pd.Timedelta(days=6)

    elif mode == "Próxima semana":

        start = monday + pd.Timedelta(days=7)
        end = monday + pd.Timedelta(days=13)

    elif mode == "Todo":

        start = valid_dates.min()
        end = valid_dates.max()

    else:

        date_range = st.date_input(
            "Slicer temporal · desde / hasta",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

        if (
            isinstance(date_range, (tuple, list))
            and len(date_range) == 2
        ):

            start = pd.Timestamp(date_range[0])
            end = pd.Timestamp(date_range[1])

        else:

            start = pd.Timestamp(date_range)
            end = pd.Timestamp(date_range)

    min_edge = st.slider(
        "Edge mínimo (%)",
        0,
        200,
        0,
        1,
    )


start = pd.Timestamp(start).normalize()
end = pd.Timestamp(end).normalize()

if start > end:
    start, end = end, start


# ============================================================
# FILTRADO DE PARTIDOS
# ============================================================

selected_keys = (
    events.loc[
        events["competition_name"].isin(
            selected_leagues
        ),
        "competition_key",
    ]
    .dropna()
    .astype(str)
    .unique()
)


filtered = events[
    events["competition_name"].isin(
        selected_leagues
    )
    & events["date"].between(
        start,
        end,
    )
].copy()


# ============================================================
# FILTRADO DE ALERTAS
# ============================================================

if not alerts.empty:

    period_alerts = alerts[
        alerts["competition"]
        .astype(str)
        .isin(selected_keys)
        & alerts["fecha_partido"].between(
            start,
            end,
        )
    ].copy()

    period_alerts = period_alerts[
        period_alerts["edge"].fillna(0) * 100
        >= min_edge
    ]

else:

    period_alerts = pd.DataFrame()


# ============================================================
# INDICADORES PRINCIPALES
# ============================================================

finished = filtered[
    filtered["home_score"].notna()
    & filtered["away_score"].notna()
]

upcoming = filtered[
    filtered["home_score"].isna()
    | filtered["away_score"].isna()
]


col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Partidos en el periodo",
    len(filtered),
)

col2.metric(
    "Por jugar",
    len(upcoming),
)

col3.metric(
    "Resultados disponibles",
    len(finished),
)

col4.metric(
    "Alertas registradas",
    len(period_alerts),
)


tabs = st.tabs(
    [
        "Resumen y calendario",
        "Alertas",
        "Performance",
        "Cuotas maestras",
        "Evolución de cuotas",
    ]
)


# ============================================================
# PESTAÑA 1: RESUMEN Y CALENDARIO
# ============================================================

with tabs[0]:

    st.subheader("Partidos del periodo")

    if filtered.empty:

        st.info(
            "No hay partidos para los filtros seleccionados."
        )

    else:

        view = filtered.copy()

        view["Fecha"] = (
            view["date"].dt.strftime("%d/%m/%Y")
        )

        view["Marcador"] = view.apply(
            lambda row: (
                f"{int(row.home_score)} - "
                f"{int(row.away_score)}"
            )
            if (
                pd.notna(row.home_score)
                and pd.notna(row.away_score)
            )
            else "—",
            axis=1,
        )

        st.dataframe(
            view[
                [
                    "Fecha",
                    "competition_name",
                    "home",
                    "Marcador",
                    "away",
                    "status",
                ]
            ].rename(
                columns={
                    "competition_name": "Competición",
                    "home": "Local",
                    "away": "Visitante",
                    "status": "Estado",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        by_day = (
            filtered.groupby(
                filtered["date"].dt.strftime(
                    "%Y-%m-%d"
                )
            )
            .size()
            .reset_index(name="Partidos")
        )

        st.plotly_chart(
            px.bar(
                by_day,
                x="date",
                y="Partidos",
                title="Partidos por día",
            ),
            use_container_width=True,
        )


# ============================================================
# PESTAÑA 2: ALERTAS
# ============================================================

with tabs[1]:

    st.subheader("Alertas enviadas")

    if period_alerts.empty:

        st.info(
            "No hay alertas para el periodo y filtros. "
            "La bitácora contiene alertas enviadas, "
            "no todas las predicciones."
        )

    else:

        view = period_alerts.copy()

        view["Edge (%)"] = (
            view["edge"] * 100
        )

        st.dataframe(
            view,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Descargar alertas filtradas",
            view.to_csv(
                index=False
            ).encode("utf-8-sig"),
            "alertas_filtradas.csv",
            "text/csv",
        )


# ============================================================
# PESTAÑA 3: PERFORMANCE
# ============================================================

with tabs[2]:

    st.subheader(
        "Performance histórica simulada"
    )

    st.caption(
        "Se simula una unidad por alerta enlazable con "
        "un resultado final; no representa apuestas ejecutadas."
    )

    settled = pd.DataFrame()

    if not alerts.empty:

        # Construimos una tabla auxiliar con nombres únicos.
        # Esto evita conflictos de columnas al cruzar datos.
        event_lookup = events[
            [
                "competition_key",
                "date",
                "home",
                "away",
                "home_score",
                "away_score",
            ]
        ].copy()

        event_lookup = event_lookup.rename(
            columns={
                "competition_key": "_event_competition",
                "date": "_event_date",
                "home": "_event_home",
                "away": "_event_away",
                "home_score": "_event_home_score",
                "away_score": "_event_away_score",
            }
        )

        # Cruce entre alertas y resultados.
        join = alerts.merge(
            event_lookup,
            left_on=[
                "competition",
                "fecha_partido",
                "local",
                "visitante",
            ],
            right_on=[
                "_event_competition",
                "_event_date",
                "_event_home",
                "_event_away",
            ],
            how="left",
        )

        # Se recuperan los marcadores con nombres explícitos.
        settled = join[
            join["_event_home_score"].notna()
            & join["_event_away_score"].notna()
        ].copy()

        # CORRECCIÓN PRINCIPAL:
        # El filtro utiliza la columna original "competition"
        # de la bitácora, no una columna auxiliar del merge.
        settled = settled[
            settled["competition"]
            .astype(str)
            .isin(
                [str(key) for key in selected_keys]
            )
            & settled["fecha_partido"].between(
                start,
                end,
            )
            & (
                settled["edge"].fillna(0) * 100
                >= min_edge
            )
        ].copy()

        # Estandarizamos los marcadores para la liquidación.
        settled["home_score"] = settled[
            "_event_home_score"
        ]

        settled["away_score"] = settled[
            "_event_away_score"
        ]

        def is_winner(row):

            market = str(
                row.get("mercado", "")
            ).strip().upper()

            if market in (
                "LOCAL",
                "HOME",
                "1",
            ):
                return (
                    row["home_score"]
                    > row["away_score"]
                )

            if market in (
                "VISITANTE",
                "AWAY",
                "2",
            ):
                return (
                    row["away_score"]
                    > row["home_score"]
                )

            if market in (
                "EMPATE",
                "DRAW",
                "X",
            ):
                return (
                    row["home_score"]
                    == row["away_score"]
                )

            return None

        if not settled.empty:

            settled["won"] = settled.apply(
                is_winner,
                axis=1,
            )

            settled = settled[
                settled["won"].notna()
            ].copy()

            settled["profit_units"] = settled.apply(
                lambda row: (
                    row["cuota_real"] - 1
                    if (
                        row["won"]
                        and pd.notna(
                            row["cuota_real"]
                        )
                    )
                    else (
                        -1
                        if not row["won"]
                        else 0
                    )
                ),
                axis=1,
            )

    if settled.empty:

        st.info(
            "No hay alertas con resultados finales "
            "enlazables para calcular el rendimiento."
        )

    else:

        count = len(settled)

        profit = settled[
            "profit_units"
        ].sum()

        wins = int(
            settled["won"].sum()
        )

        m1, m2, m3, m4 = st.columns(4)

        m1.metric(
            "Apuestas liquidadas",
            count,
        )

        m2.metric(
            "Acierto",
            f"{wins / count:.1%}",
        )

        m3.metric(
            "Beneficio (u)",
            f"{profit:.2f}",
        )

        m4.metric(
            "ROI simulado",
            f"{profit / count:.1%}",
        )

        settled = settled.sort_values(
            "fecha_partido"
        ).copy()

        settled["P&L acumulado"] = (
            settled["profit_units"].cumsum()
        )

        st.plotly_chart(
            px.line(
                settled,
                x="fecha_partido",
                y="P&L acumulado",
            ),
            use_container_width=True,
        )

        st.dataframe(
            settled,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# PESTAÑA 4: CUOTAS MAESTRAS
# ============================================================

with tabs[3]:

    st.subheader(
        "Tabla maestra de cuotas"
    )

    st.write(
        f"Archivo consultable: "
        f"`{MASTER_PATH.relative_to(ROOT)}`"
    )

    st.warning(
        "La tabla maestra contiene capturas completas "
        "solo si el proceso de comparación las ha persistido. "
        "La bitácora de alertas no representa todas las cuotas evaluadas."
    )

    source = master.copy()

    if source.empty and not alerts.empty:

        source = alerts.copy()

        source["es_alerta"] = True

        st.info(
            "Mostrando alertas como respaldo; "
            "no deben interpretarse como el universo completo de cuotas."
        )

    if source.empty:

        st.info(
            "Aún no hay capturas de cuotas registradas."
        )

    else:

        if "competition" in source.columns:

            source = source[
                source["competition"]
                .astype(str)
                .isin(
                    [str(key) for key in selected_keys]
                )
            ]

        if "fecha_partido" in source.columns:

            source = source[
                source["fecha_partido"].between(
                    start,
                    end,
                )
            ]

        if "edge" in source.columns:

            source = source[
                source["edge"].fillna(0) * 100
                >= min_edge
            ]

        st.metric(
            "Registros visibles",
            len(source),
        )

        st.dataframe(
            source,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Descargar tabla visible",
            source.to_csv(
                index=False
            ).encode("utf-8-sig"),
            "master_odds_filtrada.csv",
            "text/csv",
        )


# ============================================================
# PESTAÑA 5: EVOLUCIÓN DE CUOTAS
# ============================================================

with tabs[4]:

    st.subheader(
        "Evolución de cuotas por partido y mercado"
    )

    if master.empty:

        st.info(
            "Aún no hay snapshots completos en "
            "master_odds.csv. Se necesitan al menos "
            "dos capturas para analizar variaciones."
        )

    else:

        history = master[
            master["competition"]
            .astype(str)
            .isin(
                [str(key) for key in selected_keys]
            )
            & master["fecha_partido"].between(
                start,
                end,
            )
        ].copy()

        if history.empty:

            st.info(
                "No hay snapshots con los filtros seleccionados."
            )

        else:

            history["evento"] = (
                history["local"].astype(str)
                + " vs "
                + history["visitante"].astype(str)
                + " | "
                + history["mercado"].astype(str)
            )

            choices = sorted(
                history["evento"]
                .dropna()
                .unique()
            )

            chosen = st.selectbox(
                "Partido y mercado",
                choices,
            )

            selected_history = (
                history[
                    history["evento"] == chosen
                ]
                .sort_values(
                    "timestamp_consulta"
                )
            )

            if len(selected_history) >= 2:

                first = selected_history.iloc[0]
                last = selected_history.iloc[-1]

                variation = (
                    (
                        last["cuota_real"]
                        / first["cuota_real"]
                        - 1
                    )
                    * 100
                    if (
                        pd.notna(first["cuota_real"])
                        and first["cuota_real"]
                    )
                    else None
                )

                k1, k2, k3 = st.columns(3)

                k1.metric(
                    "Cuota inicial",
                    (
                        f"{first['cuota_real']:.3f}"
                        if pd.notna(
                            first["cuota_real"]
                        )
                        else "N/D"
                    ),
                )

                k2.metric(
                    "Última cuota",
                    (
                        f"{last['cuota_real']:.3f}"
                        if pd.notna(
                            last["cuota_real"]
                        )
                        else "N/D"
                    ),
                )

                k3.metric(
                    "Variación",
                    (
                        f"{variation:+.2f}%"
                        if variation is not None
                        else "N/D"
                    ),
                )

                st.plotly_chart(
                    px.line(
                        selected_history,
                        x="timestamp_consulta",
                        y="cuota_real",
                        markers=True,
                        title="Histórico de cuota real",
                    ),
                    use_container_width=True,
                )

            else:

                st.info(
                    "Se requieren al menos dos capturas "
                    "del mismo partido y mercado para "
                    "medir la variación."
                )

            st.dataframe(
                selected_history,
                use_container_width=True,
                hide_index=True,
            )


# ============================================================
# PIE DE PÁGINA
# ============================================================

st.sidebar.caption(
    f"Eventos: {DATA.relative_to(ROOT)} | "
    f"Alertas: {ALERTS_PATH.relative_to(ROOT)} | "
    f"Master: {MASTER_PATH.relative_to(ROOT)}"
)