from __future__ import annotations

from pathlib import Path
from datetime import datetime

import pandas as pd


class ChangeLog:
    """
    Detecta cambios reales entre dos estados de eventos
    y mantiene un histórico acumulado.

    IMPORTANTE:
    compare() devuelve únicamente los cambios detectados
    en la ejecución actual.

    El archivo change_log.csv mantiene todo el histórico.
    """

    def __init__(
        self,
        base_path: str = "data/historical",
    ):
        self.base_path = Path(base_path)
        self.base_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.file = (
            self.base_path
            / "change_log.csv"
        )

    def compare(
        self,
        previous,
        current,
        run_id: str,
    ) -> pd.DataFrame:

        changes = []

        previous_map = {
            self._event_key(row): row
            for row in previous
        }

        current_map = {
            self._event_key(row): row
            for row in current
        }

        # ==========================================================
        # EVENTOS NUEVOS O ACTUALIZADOS
        # ==========================================================

        for key, event in current_map.items():

            if key not in previous_map:

                changes.append(
                    self._change(
                        run_id=run_id,
                        event=event,
                        change_type="NEW_EVENT",
                        old_state=None,
                        new_state=self._event_state(
                            event
                        ),
                    )
                )

                continue

            old = previous_map[key]

            old_state = self._event_state(old)
            new_state = self._event_state(event)

            if old_state != new_state:

                changes.append(
                    self._change(
                        run_id=run_id,
                        event=event,
                        change_type="EVENT_UPDATED",
                        old_state=old_state,
                        new_state=new_state,
                    )
                )

        # ==========================================================
        # EVENTOS QUE DESAPARECIERON
        # ==========================================================

        for key, event in previous_map.items():

            if key not in current_map:

                changes.append(
                    self._change(
                        run_id=run_id,
                        event=event,
                        change_type="EVENT_REMOVED",
                        old_state=self._event_state(
                            event
                        ),
                        new_state=None,
                    )
                )

        # ==========================================================
        # RESULTADO DE ESTA EJECUCIÓN
        # ==========================================================

        result = pd.DataFrame(changes)

        # ==========================================================
        # GUARDAR HISTÓRICO
        #
        # IMPORTANTE:
        # Aquí sí se concatena con el histórico,
        # pero NO se devuelve ese histórico.
        # ==========================================================

        if not result.empty:

            if self.file.exists():

                old_log = pd.read_csv(
                    self.file,
                    dtype=str,
                )

                historical = pd.concat(
                    [
                        old_log,
                        result,
                    ],
                    ignore_index=True,
                )

            else:

                historical = result.copy()

            historical.to_csv(
                self.file,
                index=False,
                encoding="utf-8-sig",
            )

        # ==========================================================
        # DEVOLVER SOLO CAMBIOS DE ESTA EJECUCIÓN
        # ==========================================================

        return result

    # ==============================================================
    # IDENTIDAD DEL PARTIDO
    # ==============================================================

    @staticmethod
    def _event_key(event):

        if isinstance(event, dict):

            sport = event.get("sport")
            competition = event.get("competition")
            season = event.get("season")
            date = event.get("date")
            home = event.get("home")
            away = event.get("away")

        else:

            sport = event.sport
            competition = event.competition
            season = event.season
            date = event.date
            home = event.home
            away = event.away

        return (
            ChangeLog._normalize_text(sport),
            ChangeLog._normalize_text(competition),
            ChangeLog._normalize_text(season),
            ChangeLog._normalize_date(date),
            ChangeLog._normalize_text(home),
            ChangeLog._normalize_text(away),
        )

    # ==============================================================
    # ESTADO DEL PARTIDO
    # ==============================================================

    @staticmethod
    def _event_state(event):

        if isinstance(event, dict):

            return {
                "home_score": ChangeLog._normalize_score(
                    event.get("home_score")
                ),
                "away_score": ChangeLog._normalize_score(
                    event.get("away_score")
                ),
                "status": ChangeLog._normalize_text(
                    event.get("status")
                ),
                "date": ChangeLog._normalize_date(
                    event.get("date")
                ),
            }

        return {
            "home_score": ChangeLog._normalize_score(
                event.home_score
            ),
            "away_score": ChangeLog._normalize_score(
                event.away_score
            ),
            "status": ChangeLog._normalize_text(
                event.status
            ),
            "date": ChangeLog._normalize_date(
                event.date
            ),
        }

    # ==============================================================
    # REGISTRO DEL CAMBIO
    # ==============================================================

    @staticmethod
    def _change(
        run_id,
        event,
        change_type,
        old_state,
        new_state,
    ):

        if isinstance(event, dict):

            sport = event.get("sport")
            competition = event.get("competition")
            season = event.get("season")
            source = event.get("source")
            source_id = event.get("source_id")
            home = event.get("home")
            away = event.get("away")

        else:

            sport = event.sport
            competition = event.competition
            season = event.season
            source = event.source
            source_id = event.source_id
            home = event.home
            away = event.away

        return {
            "run_id": run_id,
            "detected_at": datetime.now().isoformat(),

            "sport": sport,
            "competition": competition,
            "season": season,

            "source": source,
            "source_id": source_id,

            "home": home,
            "away": away,

            "change_type": change_type,

            "old_state": str(old_state),
            "new_state": str(new_state),
        }

    # ==============================================================
    # NORMALIZADORES
    # ==============================================================

    @staticmethod
    def _normalize_text(value):

        if value is None:
            return None

        if pd.isna(value):
            return None

        value = str(value).strip()

        if not value:
            return None

        return value.casefold()

    @staticmethod
    def _normalize_date(value):

        if value is None:
            return None

        try:

            timestamp = pd.to_datetime(
                value,
                utc=True,
                errors="coerce",
            )

            if pd.isna(timestamp):
                return None

            return timestamp.isoformat()

        except Exception:

            return str(value).strip()

    @staticmethod
    def _normalize_score(value):

        if value is None:
            return None

        if pd.isna(value):
            return None

        try:

            return int(float(value))

        except (
            ValueError,
            TypeError,
        ):

            return str(value).strip()