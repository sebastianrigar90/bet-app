from pathlib import Path
from typing import List

import json
import pandas as pd

from ..core.models import Event


class SportsRepository:
    """
    Responsable del almacenamiento de datos deportivos.

    Separa la extracción de datos de su persistencia.
    """

    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)

    # =========================================================
    # RAW
    # =========================================================

    def save_raw(
        self,
        data: list,
        sport: str,
        competition: str,
        season: str,
        source: str,
    ) -> Path:
        """
        Guarda información RAW proveniente de una fuente.
        """

        directory = (
            self.base_dir
            / "raw"
            / sport
            / competition
            / season
            / source
        )

        directory.mkdir(
            parents=True,
            exist_ok=True
        )

        file_path = (
            directory
            / "data.json"
        )

        file_path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return file_path

    # =========================================================
    # EVENTS → DATAFRAME
    # =========================================================

    @staticmethod
    def events_to_dataframe(
        events: List[Event],
    ) -> pd.DataFrame:
        """
        Convierte una lista de Event
        en un DataFrame estándar.
        """

        records = []

        for event in events:

            records.append(
                {
                    "sport": event.sport,
                    "competition": event.competition,
                    "season": event.season,
                    "date": event.date,
                    "home": event.home,
                    "away": event.away,
                    "home_score": event.home_score,
                    "away_score": event.away_score,
                    "status": event.status,
                    "source": event.source,
                    "source_id": event.source_id,
                }
            )

        return pd.DataFrame(records)

    # =========================================================
    # PROCESSED
    # =========================================================

    def save_events(
        self,
        events: List[Event],
        sport: str,
        competition: str,
        season: str,
        filename: str = "events.parquet",
    ) -> Path:
        """
        Guarda eventos normalizados.
        """

        directory = (
            self.base_dir
            / "processed"
            / sport
            / competition
            / season
        )

        directory.mkdir(
            parents=True,
            exist_ok=True
        )

        df = self.events_to_dataframe(
            events
        )

        file_path = directory / filename

        if file_path.suffix.lower() == ".csv":

            df.to_csv(
                file_path,
                index=False,
                encoding="utf-8-sig",
            )

        elif file_path.suffix.lower() == ".parquet":

            df.to_parquet(
                file_path,
                index=False,
            )

        else:

            raise ValueError(
                "Formato no soportado. "
                "Utiliza .csv o .parquet"
            )

        return file_path

    # =========================================================
    # HISTORICAL
    # =========================================================

    def save_historical(
        self,
        events: List[Event],
        sport: str,
        competition: str,
        filename: str = "historical.parquet",
    ) -> Path:
        """
        Guarda el histórico consolidado de una competición.
        """

        directory = (
            self.base_dir
            / "historical"
            / sport
            / competition
        )

        directory.mkdir(
            parents=True,
            exist_ok=True
        )

        df = self.events_to_dataframe(
            events
        )

        file_path = directory / filename

        if file_path.suffix.lower() == ".csv":

            df.to_csv(
                file_path,
                index=False,
                encoding="utf-8-sig",
            )

        else:

            df.to_parquet(
                file_path,
                index=False,
            )

        return file_path