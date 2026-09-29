from abc import ABC, abstractmethod
from typing import List

import pandas as pd


class OddsSource(ABC):
    """
    Interfaz común para cualquier casa de apuestas.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def get_odds(
        self,
        sport: str,
        competition: str,
    ) -> pd.DataFrame:
        """
        Retorna las cuotas disponibles.

        Columnas esperadas:

        fecha
        local
        visitante
        cuota_local
        cuota_empate
        cuota_visita
        """
        pass