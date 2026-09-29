from typing import List, Optional

from .core.models import Event
from .core.router import SourceRouter
from .normalization.matches import MatchNormalizer
from .normalization.teams import TeamNormalizer
from .sources.factory import SourceFactory
from .storage.repository import SportsRepository
from .validation.validator import SportsDataValidator


class DataManager:
    """
    Orquestador principal del sistema de datos deportivos.

    Flujo:

        sources.yaml
             ↓
        SourceFactory
             ↓
        SourceRouter
             ↓
           Source
             ↓
        Normalizer
             ↓
         Validator
             ↓
         Repository

    El DataManager no conoce detalles específicos de
    PulseLive, Colombia.com u otras fuentes.
    """

    def __init__(
        self,
        config_path: str = "config/sources.yaml",
        team_config_path: Optional[str] = "config/teams.yaml",
        repository: Optional[SportsRepository] = None,
    ):
        # -----------------------------------------------------
        # CONFIGURACIÓN DE FUENTES
        # -----------------------------------------------------

        self.config_path = config_path

        self.source_factory = SourceFactory(
            config_path=config_path
        )

        # -----------------------------------------------------
        # ROUTER
        # -----------------------------------------------------

        self.router = SourceRouter()

        self._load_sources()

        # -----------------------------------------------------
        # NORMALIZACIÓN
        # -----------------------------------------------------

        self.team_normalizer = TeamNormalizer(
            config_path=team_config_path
            if team_config_path
            else None
        )

        self.match_normalizer = MatchNormalizer(
            team_normalizer=self.team_normalizer
        )

        # -----------------------------------------------------
        # VALIDACIÓN
        # -----------------------------------------------------

        self.validator = SportsDataValidator()

        # -----------------------------------------------------
        # PERSISTENCIA
        # -----------------------------------------------------

        self.repository = (
            repository
            if repository is not None
            else SportsRepository()
        )

    # =========================================================
    # CARGAR FUENTES DESDE YAML
    # =========================================================

    def _load_sources(self) -> None:
        """
        Lee sources.yaml y registra automáticamente
        todas las fuentes configuradas en el Router.
        """

        config = self.source_factory.load_config()

        for sport, competitions in config.items():

            if not isinstance(
                competitions,
                dict
            ):
                continue

            for competition in competitions:

                sources = (
                    self.source_factory
                    .create_for_competition(
                        sport=sport,
                        competition=competition,
                    )
                )

                for source, priority in sources:

                    self.router.register(
                        source=source,
                        sport=sport,
                        competition=competition,
                        priority=priority,
                    )

    # =========================================================
    # OBTENER EVENTOS
    # =========================================================

    def get_events(
        self,
        sport: str,
        competition: str,
        season: str,
        save: bool = False,
        filename: str = "events.csv",
    ) -> List[Event]:
        """
        Ejecuta el pipeline completo:

            Router
              ↓
            Source
              ↓
            Normalizer
              ↓
            Validator
              ↓
            Repository
        """

        # -----------------------------------------------------
        # 1. SOURCE ROUTER
        # -----------------------------------------------------

        events = self.router.get_events(
            sport=sport,
            competition=competition,
            season=season,
        )

        # -----------------------------------------------------
        # 2. NORMALIZATION
        # -----------------------------------------------------

        normalized_events = (
            self.match_normalizer.normalize_events(
                events
            )
        )

        # -----------------------------------------------------
        # 3. VALIDATION
        # -----------------------------------------------------

        valid_events, errors = (
            self.validator.validate_events(
                normalized_events
            )
        )

        # -----------------------------------------------------
        # 4. ERRORES
        # -----------------------------------------------------

        if errors:

            print(
                f"[WARNING] "
                f"{len(errors)} errores encontrados."
            )

            for error in errors[:10]:

                print(
                    f"  - {error}"
                )

        # -----------------------------------------------------
        # 5. REPOSITORY
        # -----------------------------------------------------

        if save:

            path = self.repository.save_events(
                valid_events,
                sport=sport,
                competition=competition,
                season=season,
                filename=filename,
            )

            print(
                f"[OK] Datos guardados en: {path}"
            )

        return valid_events

    # =========================================================
    # DISPONIBILIDAD
    # =========================================================

    def is_available(
        self,
        sport: str,
        competition: str,
    ) -> bool:
        """
        Verifica si existe al menos una fuente disponible.
        """

        source = self.router.get_source(
            sport=sport,
            competition=competition,
        )

        return source is not None

    # =========================================================
    # FUENTES
    # =========================================================

    def list_sources(
        self,
        sport: str,
        competition: str,
    ) -> List[str]:
        """
        Lista las fuentes configuradas para una competición.
        """

        return self.router.list_sources(
            sport=sport,
            competition=competition,
        )