import os
from typing import Any, Callable, Dict


from .api.pulselive import PulseLiveSource
from .api.football_data_org import FootballDataOrgSource
from .scraper.colombia_com import ColombiaComSource
from .csv.football_data import FootballDataSource


class SourceRegistry:
    """
    Registro central de fuentes de datos deportivos.

    Mantiene un catálogo de fuentes y permite que SourceFactory
    obtenga el constructor correspondiente a cada fuente.
    """

    def __init__(self):
        self._creators: Dict[str, Callable[..., Any]] = {}

        self._register_defaults()

    # ============================================================
    # REGISTRO
    # ============================================================

    def register(
        self,
        name: str,
        creator: Callable[..., Any],
    ) -> None:
        """
        Registra una fuente de datos.
        """

        name = self._normalize_name(name)

        self._creators[name] = creator

    # ============================================================
    # OBTENER CONSTRUCTOR
    # ============================================================

    def get(
        self,
        name: str,
    ) -> Callable[..., Any]:
        """
        Obtiene el constructor de una fuente.

        Este método es utilizado por SourceFactory.
        """

        name = self._normalize_name(name)

        if name not in self._creators:
            raise ValueError(
                f"Fuente no registrada: {name}"
            )

        return self._creators[name]

    # ============================================================
    # FUENTES POR DEFECTO
    # ============================================================

    def _register_defaults(self) -> None:
        """
        Registra las fuentes disponibles por defecto.
        """

        self.register(
            name="pulselive",
            creator=PulseLiveSource,
        )

        self.register(
            name="colombia_com",
            creator=ColombiaComSource,
        )

        self.register(
            name="football_data",
            creator=FootballDataSource,
        )

        self.register(
            name="football_data_org",
            creator=FootballDataOrgSource,
        )

    # ============================================================
    # CREAR FUENTE DIRECTAMENTE
    # ============================================================

    def create(
        self,
        name: str,
        config: Dict[str, Any] | None = None,
    ) -> Any:
        """
        Crea directamente una instancia de una fuente.

        Este método permite utilizar el Registry sin pasar
        por SourceFactory.
        """

        name = self._normalize_name(name)

        creator = self.get(name)

        config = dict(config or {})

        # --------------------------------------------------------
        # Inyección automática del token
        # --------------------------------------------------------

        if name == "football_data_org":

            api_token = os.getenv(
                "FOOTBALL_DATA_API_TOKEN"
            )

            if api_token:
                config.setdefault(
                    "api_token",
                    api_token,
                )

        return creator(**config)

    # ============================================================
    # CONSULTAR EXISTENCIA
    # ============================================================

    def has(
        self,
        name: str,
    ) -> bool:
        """
        Indica si una fuente está registrada.
        """

        name = self._normalize_name(name)

        return name in self._creators

    # ============================================================
    # LISTAR FUENTES
    # ============================================================

    def list_sources(self) -> list[str]:
        """
        Devuelve los nombres de las fuentes registradas.
        """

        return sorted(
            self._creators.keys()
        )

    # ============================================================
    # NORMALIZACIÓN
    # ============================================================

    @staticmethod
    def _normalize_name(
        name: str,
    ) -> str:
        """
        Normaliza el nombre de una fuente.
        """

        return str(name).strip().lower()