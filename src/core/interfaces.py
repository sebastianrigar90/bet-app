from abc import ABC, abstractmethod
from typing import List

from .models import Event


class SportsDataSource(ABC):
    """
    Interfaz base para cualquier fuente de datos deportivos.

    Todas las fuentes (API, CSV, scraper, etc.)
    deberán implementar esta interfaz.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre identificador de la fuente."""
        pass

    @abstractmethod
    def get_events(
        self,
        sport: str,
        competition: str,
        season: str
    ) -> List[Event]:
        """
        Obtiene eventos deportivos desde la fuente.

        Parameters
        ----------
        sport:
            Deporte. Ej: football, basketball, tennis.

        competition:
            Competición. Ej: serie_a, nba, atp.

        season:
            Temporada o periodo.

        Returns
        -------
        List[Event]
            Eventos normalizados al modelo común.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Verifica si la fuente está disponible.
        """
        pass