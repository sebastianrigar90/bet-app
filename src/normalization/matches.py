from typing import List, Optional

from ..core.models import Event
from .teams import TeamNormalizer


class MatchNormalizer:
    """
    Normaliza eventos deportivos independientemente
    de la fuente de origen.

    También utiliza TeamNormalizer para homologar
    nombres de equipos/participantes.
    """

    def __init__(
        self,
        team_normalizer: Optional[TeamNormalizer] = None,
    ):
        """
        Parameters
        ----------
        team_normalizer:
            Instancia encargada de homologar los nombres
            de equipos o participantes.
        """

        self.team_normalizer = (
            team_normalizer
            if team_normalizer is not None
            else TeamNormalizer()
        )

    # =========================================================
    # NORMALIZAR LISTA DE EVENTOS
    # =========================================================

    def normalize_events(
        self,
        events: List[Event],
    ) -> List[Event]:
        """
        Normaliza una lista completa de eventos.
        """

        normalized_events = []

        for event in events:

            normalized_event = self.normalize_event(
                event
            )

            if normalized_event is not None:
                normalized_events.append(
                    normalized_event
                )

        return normalized_events

    # =========================================================
    # NORMALIZAR EVENTO
    # =========================================================

    def normalize_event(
        self,
        event: Event,
    ) -> Event:
        """
        Normaliza un evento individual.
        """

        # -----------------------------------------------------
        # Equipos / participantes
        # -----------------------------------------------------

        event.home = (
            self.team_normalizer.normalize(
                event.home
            )
        )

        event.away = (
            self.team_normalizer.normalize(
                event.away
            )
        )

        # -----------------------------------------------------
        # Información general
        # -----------------------------------------------------

        event.sport = self.normalize_text(
            event.sport
        )

        event.competition = self.normalize_text(
            event.competition
        )

        event.season = str(
            event.season
        ).strip()

        # -----------------------------------------------------
        # Estado
        # -----------------------------------------------------

        if event.status:
            event.status = (
                self.normalize_status(
                    event.status
                )
            )

        return event

    # =========================================================
    # TEXTO GENERAL
    # =========================================================

    @staticmethod
    def normalize_text(
        value: Optional[str],
    ) -> str:
        """
        Normaliza texto general.
        """

        if value is None:
            return ""

        return (
            str(value)
            .strip()
            .lower()
        )

    # =========================================================
    # ESTADOS
    # =========================================================

    @staticmethod
    def normalize_status(
        status: str,
    ) -> str:
        """
        Convierte estados diferentes de distintas
        fuentes a estados comunes.
        """

        status = (
            str(status)
            .strip()
            .lower()
        )

        status_map = {

            "finished": "finished",
            "complete": "finished",
            "completed": "finished",
            "final": "finished",

            "scheduled": "scheduled",
            "upcoming": "scheduled",
            "not started": "scheduled",

            "live": "live",
            "in play": "live",
            "in_progress": "live",

            "postponed": "postponed",

            "cancelled": "cancelled",
            "canceled": "cancelled",
        }

        return status_map.get(
            status,
            status,
        )