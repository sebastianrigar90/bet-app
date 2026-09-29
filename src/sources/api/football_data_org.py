import os
from datetime import datetime
from typing import List, Optional

import requests

from ...core.interfaces import SportsDataSource
from ...core.models import Event


class FootballDataOrgSource(SportsDataSource):
    """
    Fuente de datos deportivos basada en football-data.org API v4.

    Para Serie A:

        competition_code = "SA"

    La autenticación utiliza la variable de entorno:

        FOOTBALL_DATA_API_TOKEN

    También puede recibirse explícitamente mediante api_token.
    """

    BASE_URL = "https://api.football-data.org/v4"

    def __init__(
        self,
        api_token: Optional[str] = None,
        competition_code: str = "SA",
        competition: str = "serie_a",
        source_name: str = "football_data_org",
        timeout: int = 15,
    ):
        # --------------------------------------------------------
        # Token
        # --------------------------------------------------------

        self.api_token = (
            api_token
            or os.getenv("FOOTBALL_DATA_API_TOKEN")
        )

        # --------------------------------------------------------
        # Configuración
        # --------------------------------------------------------

        self.competition_code = competition_code
        self.competition = competition
        self.source_name = source_name
        self.timeout = timeout

        self._last_error: Optional[str] = None

    # ============================================================
    # PROPIEDADES
    # ============================================================

    @property
    def name(self) -> str:
        """
        Nombre identificador de la fuente.
        """

        return self.source_name

    @property
    def last_error(self) -> Optional[str]:
        """
        Último error registrado por la fuente.
        """

        return self._last_error

    # ============================================================
    # HTTP
    # ============================================================

    def _get_headers(self) -> dict:
        """
        Construye los headers HTTP para la API.
        """

        if not self.api_token:
            return {}

        return {
            "X-Auth-Token": self.api_token,
            "Accept": "application/json",
        }

    def _get_url(self) -> str:
        """
        Construye la URL del endpoint de partidos.
        """

        return (
            f"{self.BASE_URL}/competitions/"
            f"{self.competition_code}/matches"
        )

    # ============================================================
    # DISPONIBILIDAD
    # ============================================================

    def is_available(self) -> bool:
        """
        Verifica si la API está disponible y el token
        permite consultar la competición configurada.
        """

        self._last_error = None

        if not self.api_token:
            self._last_error = (
                "No se encontró api_token para football-data.org."
            )

            return False

        try:

            response = requests.get(
                self._get_url(),
                headers=self._get_headers(),
                params={"limit": 1},
                timeout=self.timeout,
            )

            if response.status_code == 200:
                return True

            self._last_error = (
                f"HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

            return False

        except requests.RequestException as exc:

            self._last_error = str(exc)

            return False

    # ============================================================
    # OBTENER EVENTOS
    # ============================================================

    def get_events(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> List[Event]:
        """
        Obtiene partidos de una competición y los convierte
        al modelo común Event.
        """

        self._last_error = None

        # --------------------------------------------------------
        # Validar deporte
        # --------------------------------------------------------

        if sport.lower() != "football":

            raise ValueError(
                "FootballDataOrgSource solamente soporta football."
            )

        # --------------------------------------------------------
        # Validar competición
        # --------------------------------------------------------

        if competition != self.competition:

            raise ValueError(
                f"Competición no soportada por esta instancia: "
                f"{competition}"
            )

        # --------------------------------------------------------
        # Validar token
        # --------------------------------------------------------

        if not self.api_token:

            raise RuntimeError(
                "No se encontró api_token para football-data.org."
            )

        # --------------------------------------------------------
        # Temporada
        # --------------------------------------------------------

        season_year = self._parse_season_year(
            season
        )

        # --------------------------------------------------------
        # Consulta API
        # --------------------------------------------------------

        try:

            response = requests.get(
                self._get_url(),
                headers=self._get_headers(),
                params={
                    "season": season_year,
                },
                timeout=self.timeout,
            )

            response.raise_for_status()

            data = response.json()

        except requests.RequestException as exc:

            self._last_error = str(exc)

            raise RuntimeError(
                f"Error consultando football-data.org: {exc}"
            ) from exc

        except ValueError as exc:

            self._last_error = str(exc)

            raise RuntimeError(
                f"Respuesta inválida de football-data.org: {exc}"
            ) from exc

        # --------------------------------------------------------
        # Procesar partidos
        # --------------------------------------------------------

        matches = data.get(
            "matches",
            []
        )

        events: List[Event] = []

        for match in matches:

            event = self._parse_match(
                match=match,
                sport=sport,
                competition=competition,
                season=season,
            )

            if event is not None:
                events.append(event)

        return events

    # ============================================================
    # PARSEAR PARTIDO
    # ============================================================

    def _parse_match(
        self,
        match: dict,
        sport: str,
        competition: str,
        season: str,
    ) -> Optional[Event]:
        """
        Convierte un partido de football-data.org
        al modelo Event.
        """

        try:

            match_id = match.get(
                "id"
            )

            utc_date = match.get(
                "utcDate"
            )

            if not utc_date:
                return None

            date = self._parse_datetime(
                utc_date
            )

            home_team = (
                match.get("homeTeam")
                or {}
            )

            away_team = (
                match.get("awayTeam")
                or {}
            )

            home_name = home_team.get(
                "name"
            )

            away_name = away_team.get(
                "name"
            )

            if not home_name or not away_name:
                return None

            # ----------------------------------------------------
            # Estado
            # ----------------------------------------------------

            status = self._normalize_status(
                match.get("status")
            )

            # ----------------------------------------------------
            # Marcador
            # ----------------------------------------------------

            score = (
                match.get("score")
                or {}
            )

            full_time = (
                score.get("fullTime")
                or {}
            )

            home_score = full_time.get(
                "home"
            )

            away_score = full_time.get(
                "away"
            )

            # ----------------------------------------------------
            # Event
            # ----------------------------------------------------

            return Event(
                sport=sport,
                competition=competition,
                season=season,
                date=date,
                home=home_name,
                away=away_name,
                home_score=home_score,
                away_score=away_score,
                status=status,
                source=self.source_name,
                source_id=(
                    str(match_id)
                    if match_id is not None
                    else None
                ),
            )

        except Exception:

            return None

    # ============================================================
    # FECHA
    # ============================================================

    @staticmethod
    def _parse_datetime(
        value: str,
    ) -> datetime:
        """
        Convierte una fecha ISO 8601 de la API
        a datetime.
        """

        value = value.replace(
            "Z",
            "+00:00"
        )

        return datetime.fromisoformat(
            value
        )

    # ============================================================
    # TEMPORADA
    # ============================================================

    @staticmethod
    def _parse_season_year(
        season: str,
    ) -> int:
        """
        Convierte temporadas como:

            2026-27
            2026/27
            2026

        al año inicial:

            2026
        """

        season = str(
            season
        ).strip()

        if "-" in season:

            season = season.split(
                "-"
            )[0]

        elif "/" in season:

            season = season.split(
                "/"
            )[0]

        return int(
            season
        )

    # ============================================================
    # ESTADO
    # ============================================================

    @staticmethod
    def _normalize_status(
        status: Optional[str],
    ) -> str:
        """
        Normaliza los estados de football-data.org
        al modelo interno.
        """

        if not status:

            return "scheduled"

        status = (
            status
            .upper()
            .strip()
        )

        status_map = {

            "SCHEDULED": "scheduled",

            "TIMED": "scheduled",

            "POSTPONED": "postponed",

            "SUSPENDED": "suspended",

            "CANCELLED": "cancelled",

            "LIVE": "live",

            "IN_PLAY": "live",

            "PAUSED": "live",

            "FINISHED": "finished",
        }

        return status_map.get(
            status,
            status.lower(),
        )