from typing import List

from src.core.interfaces import SportsDataSource
from src.core.models import Event
from src.core.router import SourceRouter


class FailingSource(SportsDataSource):
    """
    Fuente simulada que siempre falla.

    Se utiliza únicamente para probar
    el mecanismo de fallback del Router.
    """

    @property
    def name(self) -> str:
        return "failing_source"

    def is_available(self) -> bool:
        return False

    def get_events(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> List[Event]:
        raise RuntimeError(
            "Fuente simulada no disponible"
        )


class WorkingSource(SportsDataSource):
    """
    Fuente simulada que funciona correctamente.
    """

    @property
    def name(self) -> str:
        return "working_source"

    def is_available(self) -> bool:
        return True

    def get_events(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> List[Event]:

        return [
            Event(
                sport=sport,
                competition=competition,
                season=season,
                date=None,
                home="Team A",
                away="Team B",
                home_score=2,
                away_score=1,
                status="finished",
                source=self.name,
                source_id="test-001",
            )
        ]


def test_router_fallback():
    """
    Verifica que el Router utilice la segunda fuente
    cuando la primera no está disponible.
    """

    router = SourceRouter()

    # ---------------------------------------------------------
    # Fuente 1: falla
    # ---------------------------------------------------------

    router.register(
        source=FailingSource(),
        sport="football",
        competition="test_competition",
        priority=1,
    )

    # ---------------------------------------------------------
    # Fuente 2: funciona
    # ---------------------------------------------------------

    router.register(
        source=WorkingSource(),
        sport="football",
        competition="test_competition",
        priority=2,
    )

    # ---------------------------------------------------------
    # Ejecutar Router
    # ---------------------------------------------------------

    events = router.get_events(
        sport="football",
        competition="test_competition",
        season="2026",
    )

    # ---------------------------------------------------------
    # Validaciones
    # ---------------------------------------------------------

    assert len(events) == 1

    assert events[0].source == "working_source"

    assert events[0].home == "Team A"

    assert events[0].away == "Team B"


if __name__ == "__main__":
    test_router_fallback()

    print(
        "ROUTER FALLBACK TEST OK"
    )