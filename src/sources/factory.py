from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .registry import SourceRegistry


class SourceFactory:
    """
    Fábrica genérica de fuentes deportivas.

    La Factory no conoce directamente las clases concretas
    de las fuentes. Utiliza SourceRegistry para resolverlas.

    Flujo:

        sources.yaml
             ↓
        SourceFactory
             ↓
        SourceRegistry
             ↓
        Source concreta
    """

    def __init__(
        self,
        config_path: str = "config/sources.yaml",
        registry: Optional[SourceRegistry] = None,
    ):
        self.config_path = Path(config_path)

        self.registry = (
            registry
            if registry is not None
            else SourceRegistry()
        )

    # =========================================================
    # CREAR FUENTE
    # =========================================================

    def create(
        self,
        source_name: str,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Crea una fuente utilizando el Registry.
        """

        config = config or {}

        creator = self.registry.get(
            source_name
        )

        return creator(
            **config
        )

    # =========================================================
    # LEER CONFIGURACIÓN
    # =========================================================

    def load_config(self) -> Dict[str, Any]:
        """
        Carga sources.yaml.
        """

        if not self.config_path.exists():

            raise FileNotFoundError(
                f"No existe el archivo: "
                f"{self.config_path}"
            )

        with open(
            self.config_path,
            "r",
            encoding="utf-8",
        ) as file:

            data = yaml.safe_load(file)

        if not data:

            raise ValueError(
                "sources.yaml está vacío."
            )

        return data

    # =========================================================
    # CREAR FUENTES DE UNA COMPETICIÓN
    # =========================================================

    def create_for_competition(
        self,
        sport: str,
        competition: str,
    ):
        """
        Lee sources.yaml y crea todas las fuentes
        configuradas para una competición.

        Returns
        -------
        list
            Lista de:

                (source_instance, priority)
        """

        config = self.load_config()

        sport_config = config.get(
            sport,
            {}
        )

        competition_config = (
            sport_config.get(
                competition,
                []
            )
        )

        sources = []

        for item in competition_config:

            source_name = item.get(
                "source"
            )

            if not source_name:

                raise ValueError(
                    f"Fuente sin nombre para "
                    f"{sport}/{competition}"
                )

            priority = int(
                item.get(
                    "priority",
                    100,
                )
            )

            source_config = item.get(
                "config",
                {}
            )

            source = self.create(
                source_name=source_name,
                config=source_config,
            )

            sources.append(
                (
                    source,
                    priority,
                )
            )

        return sources

    # =========================================================
    # FUENTES DISPONIBLES
    # =========================================================

    def available_sources(self):

        return self.registry.list_sources()