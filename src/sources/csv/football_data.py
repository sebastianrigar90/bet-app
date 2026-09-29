from pathlib import Path
from typing import List, Optional

import pandas as pd
import requests

from ...core.interfaces import SportsDataSource
from ...core.models import Event


class FootballDataSource(SportsDataSource):
    """
    Fuente de resultados deportivos de football-data.co.uk.

    Actualmente configurada para Serie A.

    La fuente entrega un CSV remoto que posteriormente
    se transforma al modelo común Event.
    """

    BASE_URL = (
        "https://www.football-data.co.uk/mmz4281"
    )

    def __init__(
        self,
        league_code: str = "I1",
        season_code: str = "2627",
        competition: str = "serie_a",
        source_name: str = "football_data",
        raw_dir: Optional[str] = None,
    ):
        self.league_code = league_code
        self.season_code = season_code
        self.competition = competition
        self.source_name = source_name

        self.raw_dir = (
            Path(raw_dir)
            if raw_dir
            else Path("data/raw/serie_a")
        )

    # =========================================================
    # PROPIEDADES
    # =========================================================

    @property
    def name(self) -> str:
        return self.source_name

    @property
    def url(self) -> str:
        """
        Construye dinámicamente la URL de la fuente.
        """

        return (
            f"{self.BASE_URL}/"
            f"{self.season_code}/"
            f"{self.league_code}.csv"
        )

    # =========================================================
    # DISPONIBILIDAD
    # =========================================================

    def is_available(self) -> bool:
        """
        Comprueba si la fuente responde correctamente.

        No descarga todavía todos los datos.
        """

        try:

            response = requests.get(
                self.url,
                timeout=10,
            )

            return response.ok

        except requests.RequestException:

            return False

    # =========================================================
    # OBTENER EVENTOS
    # =========================================================

    def get_events(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> List[Event]:

        if sport.lower() != "football":

            raise ValueError(
                "FootballDataSource solamente "
                "soporta football."
            )

        self.raw_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        raw_file = (
            self.raw_dir
            / f"{self.competition}_{season}.csv"
        )

        # -----------------------------------------------------
        # DESCARGAR
        # -----------------------------------------------------

        response = requests.get(
            self.url,
            timeout=30,
        )

        response.raise_for_status()

        raw_file.write_bytes(
            response.content
        )

        # -----------------------------------------------------
        # LEER CSV
        # -----------------------------------------------------

        raw = pd.read_csv(
            raw_file,
            encoding="latin1",
        )

        required = [
            "Date",
            "HomeTeam",
            "AwayTeam",
            "FTHG",
            "FTAG",
        ]

        missing = [
            column
            for column in required
            if column not in raw.columns
        ]

        if missing:

            raise ValueError(
                "Faltan columnas en "
                f"football-data.co.uk: {missing}"
            )

        # -----------------------------------------------------
        # CONVERTIR EVENTOS
        # -----------------------------------------------------

        events: List[Event] = []

        for index, row in raw.iterrows():

            date = pd.to_datetime(
                row["Date"],
                dayfirst=True,
                errors="coerce",
            )

            if pd.isna(date):
                continue

            home_score = (
                int(row["FTHG"])
                if pd.notna(row["FTHG"])
                else None
            )

            away_score = (
                int(row["FTAG"])
                if pd.notna(row["FTAG"])
                else None
            )

            status = (
                "finished"
                if (
                    home_score is not None
                    and away_score is not None
                )
                else "scheduled"
            )

            event = Event(
                sport=sport,
                competition=competition,
                season=season,
                date=date.to_pydatetime(),
                home=str(row["HomeTeam"]).strip(),
                away=str(row["AwayTeam"]).strip(),
                home_score=home_score,
                away_score=away_score,
                status=status,
                source=self.source_name,
                source_id=f"{self.source_name}_{index}",
            )

            events.append(event)

        return events