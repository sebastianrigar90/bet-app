from pathlib import Path
from typing import List

import pandas as pd

from ...core.interfaces import SportsDataSource
from ...core.models import Event


class CSVDataSource(SportsDataSource):
    """
    Fuente de datos basada en archivos CSV.

    La fuente lee un CSV y lo convierte al modelo Event.
    """

    def __init__(
        self,
        file_path: str,
        source_name: str = "csv"
    ):
        self.file_path = Path(file_path)
        self.source_name = source_name

    @property
    def name(self) -> str:
        return self.source_name

    def is_available(self) -> bool:
        return self.file_path.exists()

    def get_events(
        self,
        sport: str,
        competition: str,
        season: str
    ) -> List[Event]:

        if not self.is_available():
            raise FileNotFoundError(
                f"No existe el archivo: {self.file_path}"
            )

        df = pd.read_csv(self.file_path)

        events = []

        for _, row in df.iterrows():

            event = Event(
                sport=sport,
                competition=competition,
                season=season,
                date=pd.to_datetime(row["date"]),
                home=str(row["home"]),
                away=str(row["away"]),
                home_score=self._get_score(row, "home_score"),
                away_score=self._get_score(row, "away_score"),
                status=row.get("status"),
                source=self.source_name
            )

            events.append(event)

        return events

    @staticmethod
    def _get_score(
        row: pd.Series,
        column: str
    ):
        value = row.get(column)

        if pd.isna(value):
            return None

        return int(value)