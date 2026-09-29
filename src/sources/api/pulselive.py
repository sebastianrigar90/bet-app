from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone

import requests

from ...core.interfaces import SportsDataSource
from ...core.models import Event


class PulseLiveSource(SportsDataSource):
    """
    Fuente de datos deportivos basada en la API de PulseLive.

    Implementación concreta para obtener eventos deportivos
    desde una API de tipo PulseLive.
    """

    API_URL = "https://footballapi.pulselive.com/football/fixtures"

    def __init__(
        self,
        competition_id: int,
        competition_season_id: int,
        source_name: str = "pulselive",
        raw_dir: Optional[str] = None,
    ):
        self.competition_id = competition_id
        self.competition_season_id = competition_season_id
        self.source_name = source_name

        self.raw_dir = (
            Path(raw_dir)
            if raw_dir
            else None
        )

    # =========================================================
    # PROPIEDADES
    # =========================================================

    @property
    def name(self) -> str:
        """Nombre identificador de la fuente."""
        return self.source_name

    # =========================================================
    # DISPONIBILIDAD
    # =========================================================

    def is_available(self) -> bool:
        """Verifica si la API está disponible."""

        try:
            response = requests.get(
                self.API_URL,
                headers=self._headers(),
                params={
                    "comps": self.competition_id,
                    "compSeasons": self.competition_season_id,
                    "page": 0,
                    "pageSize": 1,
                    "altIds": "true",
                },
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
        """
        Obtiene los eventos de una competición y temporada.
        """

        fixtures = self._get_all_fixtures()

        events = []

        for fixture in fixtures:

            event = self._fixture_to_event(
                fixture=fixture,
                sport=sport,
                competition=competition,
                season=season,
            )

            if event is not None:
                events.append(event)

        return events

    # =========================================================
    # HEADERS
    # =========================================================

    @staticmethod
    def _headers() -> dict:
        """Headers utilizados para consultar PulseLive."""

        return {
            "Origin": "https://www.premierleague.com",
            "Referer": "https://www.premierleague.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }

    # =========================================================
    # CONSULTAR API COMPLETA
    # =========================================================

    def _get_all_fixtures(self) -> list:
        """
        Descarga todos los fixtures utilizando paginación.

        Esta función únicamente se encarga de extracción.
        El almacenamiento será responsabilidad del Repository.
        """

        params = {
            "comps": self.competition_id,
            "compSeasons": self.competition_season_id,
            "page": 0,
            "pageSize": 100,
            "altIds": "true",
        }

        response = requests.get(
            self.API_URL,
            headers=self._headers(),
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        first_page = response.json()

        all_fixtures = list(
            first_page.get("content", [])
        )

        page_info = first_page.get(
            "pageInfo",
            {}
        )

        num_pages = page_info.get(
            "numPages",
            1
        )

        for page in range(1, num_pages):

            params["page"] = page

            page_response = requests.get(
                self.API_URL,
                headers=self._headers(),
                params=params,
                timeout=30,
            )

            page_response.raise_for_status()

            page_data = page_response.json()

            all_fixtures.extend(
                page_data.get("content", [])
            )

        return all_fixtures

    # =========================================================
    # TRANSFORMAR FIXTURE → EVENT
    # =========================================================

    def _fixture_to_event(
        self,
        fixture: dict,
        sport: str,
        competition: str,
        season: str,
    ) -> Optional[Event]:
        """
        Convierte un fixture de PulseLive
        al modelo estándar Event.
        """

        teams = fixture.get(
            "teams",
            []
        )

        if len(teams) < 2:
            return None

        kickoff = fixture.get(
            "kickoff",
            {}
        )

        kickoff_millis = kickoff.get(
            "millis"
        )

        if kickoff_millis is None:
            return None

        home = teams[0]
        away = teams[1]

        status_code = fixture.get(
            "status"
        )

        home_score = home.get(
            "score"
        )

        away_score = away.get(
            "score"
        )

        played = (
            status_code in {"C", "L"}
            and home_score is not None
            and away_score is not None
        )

        date = datetime.fromtimestamp(
            kickoff_millis / 1000,
            tz=timezone.utc
        )

        return Event(
            sport=sport,
            competition=competition,
            season=season,
            date=date,

            home=home.get(
                "team",
                {}
            ).get(
                "name"
            ),

            away=away.get(
                "team",
                {}
            ).get(
                "name"
            ),

            home_score=(
                int(home_score)
                if played
                else None
            ),

            away_score=(
                int(away_score)
                if played
                else None
            ),

            status=(
                "finished"
                if played
                else "scheduled"
            ),

            source=self.source_name,

            source_id=(
                str(int(float(fixture["id"])))
                if fixture.get("id") is not None
                else None
            ),
        )