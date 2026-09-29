from typing import Dict, List, Optional

from .interfaces import SportsDataSource
from .models import Event


class SourceRouter:
    """
    Router de fuentes deportivas.

    Responsabilidades:
    - Registrar fuentes por deporte y competición.
    - Ordenarlas por prioridad.
    - Intentar las fuentes en orden.
    - Hacer fallback si una fuente falla.
    - Registrar la última fuente utilizada.
    - Registrar los errores de la última consulta.
    """

    def __init__(self):

        self._sources: Dict[
            str,
            Dict[str, List[SportsDataSource]]
        ] = {}

        # Última fuente que consiguió datos
        self._last_source: Optional[str] = None

        # Errores de la última consulta
        self._last_errors: List[str] = []

    # =========================================================
    # REGISTRAR FUENTE
    # =========================================================

    def register(
        self,
        source: SportsDataSource,
        sport: str,
        competition: str,
        priority: int = 100,
    ) -> None:

        sport_key = self._normalize_key(sport)
        competition_key = self._normalize_key(competition)

        self._sources.setdefault(
            sport_key,
            {}
        )

        self._sources[sport_key].setdefault(
            competition_key,
            []
        )

        sources = self._sources[
            sport_key
        ][competition_key]

        # Evitar duplicados
        if any(
            existing.name == source.name
            for existing in sources
        ):
            return

        # Guardar prioridad
        source._router_priority = priority

        sources.append(source)

        # Menor número = mayor prioridad
        sources.sort(
            key=lambda item: item._router_priority
        )

    # =========================================================
    # OBTENER FUENTE DISPONIBLE
    # =========================================================

    def get_source(
        self,
        sport: str,
        competition: str,
    ) -> Optional[SportsDataSource]:

        sources = self._get_sources(
            sport,
            competition,
        )

        for source in sources:

            try:

                if source.is_available():
                    return source

            except Exception:

                continue

        return None

    # =========================================================
    # OBTENER EVENTOS
    # =========================================================

    def get_events(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> List[Event]:

        # Reiniciar estado
        self._last_source = None
        self._last_errors = []

        sources = self._get_sources(
            sport,
            competition,
        )

        if not sources:

            raise ValueError(
                "No existen fuentes registradas para "
                f"sport='{sport}', "
                f"competition='{competition}'"
            )

        # -----------------------------------------------------
        # Intentar fuentes por prioridad
        # -----------------------------------------------------

        for source in sources:

            try:

                # ---------------------------------------------
                # Verificar disponibilidad
                # ---------------------------------------------

                if not source.is_available():

                    self._last_errors.append(
                        f"{source.name}: "
                        "fuente no disponible"
                    )

                    continue

                # ---------------------------------------------
                # Obtener eventos
                # ---------------------------------------------

                events = source.get_events(
                    sport=sport,
                    competition=competition,
                    season=season,
                )

                # ---------------------------------------------
                # Verificar respuesta
                # ---------------------------------------------

                if events:

                    self._last_source = source.name

                    return events

                self._last_errors.append(
                    f"{source.name}: "
                    "no devolvió eventos"
                )

            except Exception as exc:

                self._last_errors.append(
                    f"{source.name}: {exc}"
                )

        # -----------------------------------------------------
        # Ninguna fuente funcionó
        # -----------------------------------------------------

        error_message = (
            "No fue posible obtener datos para "
            f"sport='{sport}', "
            f"competition='{competition}', "
            f"season='{season}'.\n"
            + "\n".join(
                f" - {error}"
                for error in self._last_errors
            )
        )

        raise RuntimeError(
            error_message
        )

    # =========================================================
    # ÚLTIMA FUENTE UTILIZADA
    # =========================================================

    def get_last_source(self) -> Optional[str]:
        """
        Devuelve la última fuente que consiguió
        datos correctamente.
        """

        return self._last_source

    # =========================================================
    # ÚLTIMOS ERRORES
    # =========================================================

    def get_last_errors(self) -> List[str]:
        """
        Devuelve una copia de los errores encontrados
        durante la última consulta.
        """

        return self._last_errors.copy()

    # =========================================================
    # LISTAR FUENTES
    # =========================================================

    def list_sources(
        self,
        sport: str,
        competition: str,
    ) -> List[str]:

        sources = self._get_sources(
            sport,
            competition,
        )

        return [
            source.name
            for source in sources
        ]

    # =========================================================
    # LISTAR FUENTES + PRIORIDAD
    # =========================================================

    def list_sources_with_priority(
        self,
        sport: str,
        competition: str,
    ) -> List[dict]:

        sources = self._get_sources(
            sport,
            competition,
        )

        return [
            {
                "source": source.name,
                "priority": source._router_priority,
            }
            for source in sources
        ]

    # =========================================================
    # FUENTES INTERNAS
    # =========================================================

    def _get_sources(
        self,
        sport: str,
        competition: str,
    ) -> List[SportsDataSource]:

        sport_key = self._normalize_key(sport)

        competition_key = self._normalize_key(
            competition
        )

        return (
            self._sources
            .get(sport_key, {})
            .get(competition_key, [])
        )

    # =========================================================
    # NORMALIZAR CLAVES
    # =========================================================

    @staticmethod
    def _normalize_key(
        value: str,
    ) -> str:

        return (
            str(value)
            .strip()
            .lower()
        )