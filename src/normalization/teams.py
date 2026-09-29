from __future__ import annotations

from pathlib import Path
import re
import unicodedata
from typing import Any

import yaml


class TeamNormalizer:
    """
    Normalizador central de nombres de equipos.

    Lee estructuras jerárquicas como:

    football:
      england:
        premier_league:
          arsenal:
            canonical: "Arsenal"
            aliases:
              - "Arsenal"
              - "Arsenal FC"
    """

    def __init__(
        self,
        config_path: str = "config/teams.yaml",
    ):
        self.config_path = Path(config_path)

        if not self.config_path.exists():
            raise FileNotFoundError(
                f"No se encontró: {self.config_path}"
            )

        self.aliases: dict[str, str] = {}

        self._load()

    # ==========================================================
    # CARGA
    # ==========================================================

    def _load(self) -> None:

        with open(
            self.config_path,
            "r",
            encoding="utf-8",
        ) as file:
            config = yaml.safe_load(file) or {}

        if not isinstance(config, dict):
            raise ValueError(
                "teams.yaml debe contener una estructura YAML válida."
            )

        self._walk_config(config)

        if not self.aliases:
            raise ValueError(
                f"No se encontraron equipos en {self.config_path}"
            )

    def _walk_config(
        self,
        node: Any,
    ) -> None:

        if not isinstance(node, dict):
            return

        # ------------------------------------------------------
        # Detectar una definición de equipo:
        #
        # arsenal:
        #   canonical: "Arsenal"
        #   aliases: [...]
        # ------------------------------------------------------

        for key, value in node.items():

            if (
                isinstance(value, dict)
                and "canonical" in value
            ):

                canonical = value.get(
                    "canonical"
                )

                aliases = value.get(
                    "aliases",
                    [],
                )

                self._register(
                    canonical,
                    canonical,
                )

                if isinstance(
                    aliases,
                    list,
                ):

                    for alias in aliases:
                        self._register(
                            alias,
                            canonical,
                        )

                elif isinstance(
                    aliases,
                    str,
                ):

                    self._register(
                        aliases,
                        canonical,
                    )

                continue

            # --------------------------------------------------
            # Seguir recorriendo la estructura
            # --------------------------------------------------

            if isinstance(
                value,
                dict,
            ):
                self._walk_config(
                    value
                )

    # ==========================================================
    # REGISTRO
    # ==========================================================

    def _register(
        self,
        alias: Any,
        canonical: Any,
    ) -> None:

        if alias is None or canonical is None:
            return

        alias_key = self._clean(
            alias
        )

        canonical_value = str(
            canonical
        ).strip()

        if not alias_key or not canonical_value:
            return

        self.aliases[
            alias_key
        ] = canonical_value

    # ==========================================================
    # NORMALIZACIÓN
    # ==========================================================

    def normalize(
        self,
        value: Any,
    ) -> str:

        cleaned = self._clean(
            value
        )

        if not cleaned:
            return ""

        # Coincidencia exacta
        if cleaned in self.aliases:
            return self.aliases[
                cleaned
            ]

        # Intento adicional eliminando FC
        without_fc = re.sub(
            r"\bfc\b",
            "",
            cleaned,
        )

        without_fc = re.sub(
            r"\s+",
            " ",
            without_fc,
        ).strip()

        if without_fc in self.aliases:
            return self.aliases[
                without_fc
            ]

        # Si no existe alias, devolver
        # el nombre limpio original.
        return str(value).strip()

    # Alias compatible con código anterior
    def normalizar(
        self,
        value: Any,
    ) -> str:

        return self.normalize(
            value
        )

    # ==========================================================
    # LIMPIEZA
    # ==========================================================

    @staticmethod
    def _clean(
        value: Any,
    ) -> str:

        if value is None:
            return ""

        text = str(
            value
        ).strip().lower()

        if not text:
            return ""

        # Eliminar estrellas
        text = text.replace(
            "*",
            " ",
        )

        # Normalizar Unicode
        text = unicodedata.normalize(
            "NFKD",
            text,
        )

        text = "".join(
            char
            for char in text
            if not unicodedata.combining(
                char
            )
        )

        # Eliminar horas
        text = re.sub(
            r"\b\d{1,2}:\d{2}\b",
            " ",
            text,
        )

        # Eliminar espacios múltiples
        text = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        return text

    # ==========================================================
    # UTILIDADES
    # ==========================================================

    def __len__(self) -> int:
        return len(
            self.aliases
        )

    def __contains__(
        self,
        value: Any,
    ) -> bool:

        return (
            self._clean(value)
            in self.aliases
        )