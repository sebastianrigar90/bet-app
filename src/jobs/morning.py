from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from src.alerts.pipeline import AlertPipeline
from src.alerts.telegram import TelegramNotifier
from src.updater import SportsUpdater


# ============================================================
# CONFIGURACIÓN
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ALERT_HISTORY_PATH = (
    PROJECT_ROOT
    / "data"
    / "historical"
    / "alertas_enviadas.csv"
)


# ============================================================
# URLs REALES DE WPLAY
# ============================================================

WPLAY_URLS = {

    "premier_league":
        "https://apuestas.wplay.co/es/PremierLeague",

    "serie_a":
        "https://apuestas.wplay.co/es/ItaliaSerieA",

    "ligue_1":
        "https://apuestas.wplay.co/es/Ligue1",

    "la_liga":
        "https://apuestas.wplay.co/es/LaLiga",

    "bundesliga":
        "https://apuestas.wplay.co/es/Bundesliga",

    "brasileirao":
        "https://apuestas.wplay.co/es/t/2400790/Brasil-Serie-A",

    "primera_a_clausura":
        "https://apuestas.wplay.co/es/PrimeraAColombia",
}


COMPETITION_NAMES = {

    "premier_league":
        "Premier League",

    "serie_a":
        "Serie A",

    "ligue_1":
        "Ligue 1",

    "la_liga":
        "La Liga",

    "bundesliga":
        "Bundesliga",

    "brasileirao":
        "Brasileirão",

    "primera_a_clausura":
        "Primera A Colombia",
}


# ============================================================
# COLUMNAS DE LA BITÁCORA DE ALERTAS
# ============================================================

ALERT_HISTORY_COLUMNS = [

    "sent_at",
    "run_id",
    "sport",
    "competition",
    "season",
    "local",
    "visitante",
    "fecha",
    "mercado",
    "cuota_teorica",
    "cuota_real",
    "edge",
]


# ============================================================
# JOB DE LA MAÑANA
# ============================================================

class MorningJob:

    def __init__(self):

        # ----------------------------------------------------
        # RUTA DEL PROYECTO
        # ----------------------------------------------------

        self.project_root = PROJECT_ROOT

        if str(self.project_root) not in sys.path:

            sys.path.insert(
                0,
                str(self.project_root),
            )

        # ----------------------------------------------------
        # GARANTIZAR DIRECTORIO DE TRABAJO
        # ----------------------------------------------------

        os.chdir(
            self.project_root
        )

        # ----------------------------------------------------
        # DIRECTORIO HISTÓRICO
        # ----------------------------------------------------

        ALERT_HISTORY_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ----------------------------------------------------
        # COMPONENTES
        # ----------------------------------------------------

        self.updater = SportsUpdater()

        self.telegram = TelegramNotifier()

        # ----------------------------------------------------
        # CARGAR HISTÓRICO DE ALERTAS
        # ----------------------------------------------------

        self.alert_history = (
            self._load_alert_history()
        )

    # ========================================================
    # HISTÓRICO DE ALERTAS
    # ========================================================

    def _load_alert_history(self) -> pd.DataFrame:

        if not ALERT_HISTORY_PATH.exists():

            return pd.DataFrame(
                columns=ALERT_HISTORY_COLUMNS
            )

        try:

            history = pd.read_csv(
                ALERT_HISTORY_PATH
            )

        except Exception as exc:

            print(
                f"AVISO: no se pudo leer "
                f"el histórico de alertas: {exc}"
            )

            return pd.DataFrame(
                columns=ALERT_HISTORY_COLUMNS
            )

        # ----------------------------------------------------
        # GARANTIZAR COLUMNAS
        # ----------------------------------------------------

        for column in ALERT_HISTORY_COLUMNS:

            if column not in history.columns:

                history[column] = None

        return history[
            ALERT_HISTORY_COLUMNS
        ].copy()

    # ========================================================
    # GUARDAR HISTÓRICO DE ALERTAS
    # ========================================================

    def _save_alert_history(self):

        self.alert_history.to_csv(
            ALERT_HISTORY_PATH,
            index=False,
            encoding="utf-8-sig",
        )

    # ========================================================
    # CLAVE DE UNA ALERTA
    # ========================================================

    @staticmethod
    def _alert_key(
        sport: str,
        competition: str,
        season: str,
        local: str,
        visitante: str,
        mercado: str,
    ) -> tuple:

        return (
            str(sport).strip(),
            str(competition).strip(),
            str(season).strip(),
            str(local).strip(),
            str(visitante).strip(),
            str(mercado).strip(),
        )

    # ========================================================
    # COMPARAR CUOTAS
    # ========================================================

    @staticmethod
    def _odds_changed(
        previous_theoretical: float,
        previous_real: float,
        current_theoretical: float,
        current_real: float,
    ) -> bool:

        # ----------------------------------------------------
        # Tolerancia numérica
        # ----------------------------------------------------

        tolerance = 1e-12

        theoretical_changed = (
            abs(
                float(previous_theoretical)
                - float(current_theoretical)
            )
            > tolerance
        )

        real_changed = (
            abs(
                float(previous_real)
                - float(current_real)
            )
            > tolerance
        )

        return (
            theoretical_changed
            or real_changed
        )

    # ========================================================
    # PARSEAR FECHAS DE FORMA ROBUSTA
    # ========================================================

    @staticmethod
    def _parse_date_value(value):

        if value is None or pd.isna(value):
            return pd.NaT

        text = str(value).strip()

        if not text or text.casefold() in {
            "nan",
            "nat",
            "none",
        }:
            return pd.NaT

        # Formatos ISO generados por Event / pandas.
        iso_formats = [
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]

        for fmt in iso_formats:
            try:
                return pd.Timestamp(
                    datetime.strptime(text, fmt)
                )
            except (ValueError, TypeError):
                pass

        # Formatos colombianos DD/MM/YYYY.
        for fmt in [
            "%d/%m/%Y",
            "%d/%m/%Y %H:%M:%S",
        ]:
            try:
                return pd.Timestamp(
                    datetime.strptime(text, fmt)
                )
            except (ValueError, TypeError):
                pass

        # Último intento para valores compatibles con pandas.
        try:
            return pd.to_datetime(
                text,
                errors="coerce",
            )
        except Exception:
            return pd.NaT

    # ========================================================
    # ¿DEBE ENVIARSE LA ALERTA?
    # ========================================================

    def _should_send_alert(
        self,
        sport: str,
        competition: str,
        season: str,
        row,
    ) -> bool:

        key = self._alert_key(
            sport=sport,
            competition=competition,
            season=season,
            local=row["local"],
            visitante=row["visitante"],
            mercado=row["mercado"],
        )

        # ----------------------------------------------------
        # Buscar alertas anteriores del mismo evento/mercado
        # ----------------------------------------------------

        if self.alert_history.empty:

            return True

        mask = (

            self.alert_history["sport"].astype(str)
            == key[0]

        ) & (

            self.alert_history["competition"].astype(str)
            == key[1]

        ) & (

            self.alert_history["season"].astype(str)
            == key[2]

        ) & (

            self.alert_history["local"].astype(str)
            == key[3]

        ) & (

            self.alert_history["visitante"].astype(str)
            == key[4]

        ) & (

            self.alert_history["mercado"].astype(str)
            == key[5]

        )

        previous = self.alert_history[
            mask
        ]

        # ----------------------------------------------------
        # Nunca se ha enviado
        # ----------------------------------------------------

        if previous.empty:

            return True

        # ----------------------------------------------------
        # Tomar la última versión enviada
        # ----------------------------------------------------

        last = previous.iloc[-1]

        try:

            previous_theoretical = float(
                last["cuota_teorica"]
            )

            previous_real = float(
                last["cuota_real"]
            )

            current_theoretical = float(
                row["cuota_teorica"]
            )

            current_real = float(
                row["cuota_real"]
            )

        except (
            TypeError,
            ValueError,
        ):

            # Si el histórico está corrupto
            # permitimos una nueva alerta.

            return True

        # ----------------------------------------------------
        # Si cambió cualquiera de las dos cuotas:
        # NUEVA ALERTA
        # ----------------------------------------------------

        return self._odds_changed(
            previous_theoretical=previous_theoretical,
            previous_real=previous_real,
            current_theoretical=current_theoretical,
            current_real=current_real,
        )

    # ========================================================
    # REGISTRAR ALERTA ENVIADA
    # ========================================================

    def _register_alert(
        self,
        run_id: str,
        sport: str,
        competition: str,
        season: str,
        row,
    ):

        new_row = {

            "sent_at":
                datetime.now().isoformat(),

            "run_id":
                run_id,

            "sport":
                sport,

            "competition":
                competition,

            "season":
                season,

            "local":
                str(row["local"]),

            "visitante":
                str(row["visitante"]),

            "fecha":
                str(row.get("fecha", "")),

            "mercado":
                str(row["mercado"]),

            "cuota_teorica":
                float(row["cuota_teorica"]),

            "cuota_real":
                float(row["cuota_real"]),

            "edge":
                float(row["edge"]),
        }

        self.alert_history = pd.concat(
            [
                self.alert_history,
                pd.DataFrame(
                    [new_row]
                ),
            ],
            ignore_index=True,
        )

        self._save_alert_history()

    # ========================================================
    # ACTUALIZACIÓN DE DATOS
    # ========================================================

    def update_data(self):

        print()
        print("=" * 70)
        print("1. ACTUALIZACIÓN DE DATOS")
        print("=" * 70)

        self.updater.run()

    # ========================================================
    # ENVÍO DE ALERTAS
    # ========================================================

    def send_alerts(
        self,
        alerts,
        competition: str,
        season: str,
        run_id: str,
        sport: str = "football",
    ) -> int:

        if alerts.empty:

            return 0

        sent_count = 0

        skipped_count = 0

        print()
        print(
            f"VALUE DETECTADO: "
            f"{len(alerts)}"
        )

        print(
            "VERIFICANDO ALERTAS PREVIAMENTE ENVIADAS..."
        )

        today = pd.Timestamp.now().normalize()

        for _, row in alerts.iterrows():

            # Telegram solo notifica partidos de hoy (fecha local del equipo).
            parsed_match_date = self._parse_date_value(row.get("fecha"))
            if pd.isna(parsed_match_date) or parsed_match_date.normalize() != today:
                skipped_count += 1
                continue

            # ------------------------------------------------
            # ¿YA FUE ENVIADA SIN CAMBIOS?
            # ------------------------------------------------

            should_send = (
                self._should_send_alert(
                    sport=sport,
                    competition=competition,
                    season=season,
                    row=row,
                )
            )

            if not should_send:

                skipped_count += 1

                print(
                    "  OMITIDA | "
                    f"{row['local']} vs "
                    f"{row['visitante']} | "
                    f"{row['mercado']} | "
                    f"sin cambio de cuotas"
                )

                continue

            # ------------------------------------------------
            # CONSTRUIR MENSAJE COMPLETO
            # ------------------------------------------------

            competition_name = COMPETITION_NAMES.get(
                competition,
                competition,
            )

            try:

                match_date = self._parse_date_value(
                    row["fecha"]
                )

                if pd.notna(match_date):
                    match_date_text = match_date.strftime(
                        "%d/%m/%Y"
                    )
                else:
                    match_date_text = "No disponible"

            except Exception:

                match_date_text = "No disponible"

            message = (
                "ALERTA DE VALOR\n\n"
                f"Liga: {competition_name}\n"
                f"Fecha: {match_date_text}\n"
                f"Partido: {row['local']} vs {row['visitante']}\n"
                f"Mercado: {row['mercado']}\n"
                f"Cuota teórica: {float(row['cuota_teorica']):.3f}\n"
                f"Cuota real: {float(row['cuota_real']):.2f}\n"
                f"Edge: {float(row['edge']):.2%}"
            )

            # ------------------------------------------------
            # ENVIAR TELEGRAM
            # ------------------------------------------------

            success = self.telegram.send_message(
                message
            )

            # ------------------------------------------------
            # TELEGRAM OK
            # ------------------------------------------------

            if success:

                sent_count += 1

                # --------------------------------------------
                # IMPORTANTE:
                # solo guardar después de enviar correctamente
                # --------------------------------------------

                self._register_alert(
                    run_id=run_id,
                    sport=sport,
                    competition=competition,
                    season=season,
                    row=row,
                )

                print(
                    "  TELEGRAM OK | "
                    f"{row['local']} vs "
                    f"{row['visitante']} | "
                    f"{row['mercado']} | "
                    f"edge={row['edge']:.2%}"
                )

            # ------------------------------------------------
            # TELEGRAM ERROR
            # ------------------------------------------------

            else:

                print(
                    "  TELEGRAM ERROR | "
                    f"{row['local']} vs "
                    f"{row['visitante']} | "
                    f"{self.telegram.last_error}"
                )

        print()
        print(
            f"  NUEVAS ALERTAS ENVIADAS: "
            f"{sent_count}"
        )

        print(
            f"  ALERTAS REPETIDAS OMITIDAS: "
            f"{skipped_count}"
        )

        return sent_count

    # ========================================================
    # ANÁLISIS DE UNA COMPETICIÓN
    # ========================================================

    def analyze_competition(
        self,
        sport: str,
        competition: str,
        season: str,
        wplay_url: str,
    ) -> dict:

        print()
        print("-" * 70)

        print(
            f"ANALIZANDO: "
            f"{sport} / "
            f"{competition} / "
            f"{season}"
        )

        print(
            f"WPLAY: "
            f"{wplay_url}"
        )

        print("-" * 70)

        pipeline = AlertPipeline(
            min_edge=0.05
        )

        result = pipeline.run(
            sport=sport,
            competition=competition,
            season=season,
            wplay_url=wplay_url,
        )

        print(
            f"  Modelo nuevo: "
            f"{result.get('model_is_new')}"
        )

        print(
            f"  Partidos futuros: "
            f"{len(result['future'])}"
        )

        print(
            f"  Cuotas Wplay: "
            f"{len(result['market'])}"
        )

        print(
            f"  Comparaciones: "
            f"{len(result['comparison'])}"
        )

        print(
            f"  Value detectado: "
            f"{len(result['alerts'])}"
        )

        # ----------------------------------------------------
        # TELEGRAM + DEDUPLICACIÓN
        # ----------------------------------------------------

        telegram_sent = self.send_alerts(
            alerts=result["alerts"],
            competition=competition,
            season=season,
            run_id=result["run_id"],
            sport=sport,
        )

        result["telegram_sent"] = telegram_sent

        print(
            f"  Alertas nuevas enviadas: "
            f"{telegram_sent}"
        )

        return result

    # ========================================================
    # RESUMEN GERENCIAL SEMANAL
    # ========================================================

    def _build_weekly_summary(
        self,
        results: dict,
    ) -> str:

        """
        Resumen gerencial independiente de las alertas.

        IMPORTANTE:
        - NO utiliza result["alerts"].
        - NO utiliza telegram_sent.
        - NO utiliza alertas_enviadas.csv.
        - NO depende de si un partido generó value.
        - Cuenta únicamente los partidos pendientes de cada
          competición a partir de los eventos procesados.
        """

        today = datetime.now().date()

        monday = (
            today
            - timedelta(days=today.weekday())
        )

        sunday = (
            monday
            + timedelta(days=6)
        )

        daily_counts = {
            monday + timedelta(days=i): 0
            for i in range(7)
        }

        competition_counts = {}

        # ----------------------------------------------------
        # CONTAR PARTIDOS PENDIENTES POR COMPETICIÓN
        #
        # Fuente:
        # data/processed/football/<competition>/<season>/events.csv
        #
        # Este bloque es completamente independiente de:
        #   - alertas enviadas
        #   - cuotas
        #   - edge
        #   - histórico de alertas
        # ----------------------------------------------------

        for competition in WPLAY_URLS:

            season = self._get_season(
                competition
            )

            events_path = (
                self.project_root
                / "data"
                / "processed"
                / "football"
                / competition
                / season
                / "events.csv"
            )

            competition_counts[
                competition
            ] = 0

            if not events_path.exists():
                print(
                    "AVISO RESUMEN GERENCIAL: "
                    f"no existe {events_path}"
                )
                continue

            try:

                data = pd.read_csv(
                    events_path,
                    dtype=str,
                )

            except Exception as exc:

                print(
                    "AVISO RESUMEN GERENCIAL: "
                    f"no se pudo leer {events_path}: "
                    f"{exc}"
                )
                continue

            if data.empty:
                continue

            # ------------------------------------------------
            # FECHA
            # ------------------------------------------------

            if "date" not in data.columns:
                print(
                    "AVISO RESUMEN GERENCIAL: "
                    f"falta columna date en {events_path}"
                )
                continue

            dates = data["date"].apply(
                self._parse_date_value
            )

            dates = pd.to_datetime(
                dates,
                errors="coerce",
            ).dt.date

            # ------------------------------------------------
            # PARTIDOS PENDIENTES
            #
            # Un partido se considera pendiente si:
            #   1. Está dentro de hoy -> domingo.
            #   2. No está marcado como finished.
            #   3. No tiene ambos marcadores registrados.
            #
            # NO se consulta ningún histórico de alertas.
            # ------------------------------------------------

            mask = (
                dates.notna()
                & (dates >= today)
                & (dates <= sunday)
            )

            if "status" in data.columns:

                status = (
                    data["status"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .str.casefold()
                )

                mask = (
                    mask
                    & (status != "finished")
                )

            if (
                "home_score" in data.columns
                and "away_score" in data.columns
            ):

                home_score = data[
                    "home_score"
                ].fillna("").astype(str).str.strip()

                away_score = data[
                    "away_score"
                ].fillna("").astype(str).str.strip()

                has_result = (
                    home_score.ne("")
                    & away_score.ne("")
                    & home_score.ne("nan")
                    & away_score.ne("nan")
                )

                mask = (
                    mask
                    & ~has_result
                )

            week_matches = data.loc[
                mask
            ].copy()

            # ------------------------------------------------
            # EVITAR DUPLICADOS DEL MISMO EVENTO
            # ------------------------------------------------

            if not week_matches.empty:

                if "event_id" in week_matches.columns:

                    valid_ids = (
                        week_matches["event_id"]
                        .fillna("")
                        .astype(str)
                        .str.strip()
                    )

                    with_id = (
                        valid_ids != ""
                    )

                    if with_id.any():

                        duplicated_ids = (
                            valid_ids[
                                with_id
                            ]
                            .duplicated(
                                keep="first"
                            )
                        )

                        duplicate_index = (
                            valid_ids[
                                with_id
                            ]
                            .index[
                                duplicated_ids
                            ]
                        )

                        if len(
                            duplicate_index
                        ) > 0:

                            week_matches = (
                                week_matches.drop(
                                    duplicate_index
                                )
                            )

                # Fallback por fecha + equipos
                # para filas sin event_id.
                duplicate_columns = [
                    column
                    for column in [
                        "date",
                        "home",
                        "away",
                    ]
                    if column in week_matches.columns
                ]

                if duplicate_columns:

                    week_matches = (
                        week_matches.drop_duplicates(
                            subset=duplicate_columns
                        )
                    )

            count = len(
                week_matches
            )

            competition_counts[
                competition
            ] = count

            # ------------------------------------------------
            # DISTRIBUCIÓN DIARIA
            # ------------------------------------------------

            for match_date in dates.loc[
                week_matches.index
            ]:

                if match_date in daily_counts:

                    daily_counts[
                        match_date
                    ] += 1

        total_matches = sum(
            daily_counts.values()
        )

        # ----------------------------------------------------
        # NOMBRES AMIGABLES
        # ----------------------------------------------------

        day_names = [
            "Lunes",
            "Martes",
            "Miércoles",
            "Jueves",
            "Viernes",
            "Sábado",
            "Domingo",
        ]

        # ----------------------------------------------------
        # CONSTRUIR MENSAJE
        # ----------------------------------------------------

        lines = [
            "RESUMEN GERENCIAL SEMANAL",
            "",
            (
                f"Semana: "
                f"{monday:%d/%m/%Y}"
                f" → "
                f"{sunday:%d/%m/%Y}"
            ),
            (
                f"Fecha de corte: "
                f"{today:%d/%m/%Y}"
            ),
            "",
            (
                f"PARTIDOS RESTANTES: "
                f"{total_matches}"
            ),
            "",
            "DISTRIBUCIÓN POR DÍA",
        ]

        for i in range(7):

            current_date = (
                monday
                + timedelta(days=i)
            )

            if current_date < today:
                continue

            lines.append(
                f"{day_names[i]} "
                f"{current_date:%d/%m}: "
                f"{daily_counts[current_date]}"
            )

        lines.extend([
            "",
            "POR COMPETICIÓN",
        ])

        for competition in WPLAY_URLS:

            count = competition_counts.get(
                competition,
                0,
            )

            name = COMPETITION_NAMES.get(
                competition,
                competition,
            )

            lines.append(
                f"{name}: {count}"
            )

        return "\n".join(lines)

    def send_weekly_summary(
        self,
        results: dict,
    ) -> bool:

        message = self._build_weekly_summary(
            results
        )

        print()
        print("=" * 70)
        print("RESUMEN GERENCIAL SEMANAL")
        print("=" * 70)
        print(message)
        print("=" * 70)

        success = self.telegram.send_message(
            message
        )

        if success:
            print(
                "RESUMEN GERENCIAL: "
                "Telegram enviado correctamente."
            )
        else:
            print(
                "RESUMEN GERENCIAL: "
                f"error enviando Telegram: "
                f"{self.telegram.last_error}"
            )

        return success


    # ========================================================
    # EJECUCIÓN PRINCIPAL
    # ========================================================

    def run(self):

        started_at = datetime.now()

        print("=" * 70)
        print("MORNING JOB - SISTEMA DE APUESTAS")
        print("=" * 70)

        print(
            f"INICIO: "
            f"{started_at.isoformat()}"
        )

        print(
            f"PROYECTO: "
            f"{self.project_root}"
        )

        print(
            f"HISTÓRICO ALERTAS: "
            f"{ALERT_HISTORY_PATH}"
        )

        # ----------------------------------------------------
        # 1. ACTUALIZAR HISTÓRICOS
        # ----------------------------------------------------

        self.update_data()

        # ----------------------------------------------------
        # 2. ANALIZAR COMPETICIONES
        # ----------------------------------------------------

        results = {}

        for competition, wplay_url in WPLAY_URLS.items():

            try:

                result = self.analyze_competition(
                    sport="football",
                    competition=competition,
                    season=self._get_season(
                        competition
                    ),
                    wplay_url=wplay_url,
                )

                results[
                    competition
                ] = result

            except Exception as exc:

                print()
                print(
                    f"ERROR en {competition}: "
                    f"{exc}"
                )

        # ----------------------------------------------------
        # 3. RESUMEN GERENCIAL SEMANAL
        # ----------------------------------------------------

        weekly_summary_sent = self.send_weekly_summary(
            results
        )

        # ----------------------------------------------------
        # 4. RESUMEN MORNING JOB
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("RESUMEN MORNING JOB")
        print("=" * 70)

        total_alerts = 0

        total_sent = 0

        for competition, result in results.items():

            alerts = len(
                result["alerts"]
            )

            sent = result.get(
                "telegram_sent",
                0,
            )

            total_alerts += alerts

            total_sent += sent

            print(
                f"{competition}: "
                f"{alerts} alertas | "
                f"{sent} nuevas enviadas"
            )

        print()

        print(
            f"TOTAL VALUE: "
            f"{total_alerts}"
        )

        print(
            f"TOTAL TELEGRAM NUEVAS: "
            f"{total_sent}"
        )

        print(
            f"RESUMEN GERENCIAL TELEGRAM: "
            f"{'OK' if weekly_summary_sent else 'ERROR'}"
        )

        finished_at = datetime.now()

        print()

        print(
            f"FIN: "
            f"{finished_at.isoformat()}"
        )

        print("=" * 70)

        return results

    # ========================================================
    # TEMPORADAS
    # ========================================================

    @staticmethod
    def _get_season(
        competition: str,
    ) -> str:

        seasons = {

            "premier_league":
                "2026-27",

            "serie_a":
                "2026-27",

            "ligue_1":
                "2026-27",

            "la_liga":
                "2026-27",

            "bundesliga":
                "2026-27",

            "brasileirao":
                "2026",

            "primera_a_clausura":
                "2026",
        }

        if competition not in seasons:

            raise ValueError(
                f"No existe temporada "
                f"configurada para: "
                f"{competition}"
            )

        return seasons[
            competition
        ]


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    job = MorningJob()

    job.run()