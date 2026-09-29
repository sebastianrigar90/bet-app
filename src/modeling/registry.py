from __future__ import annotations

import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd


class ModelRegistry:
    """
    Registro central de modelos deportivos.

    Mantiene:

    - versiones históricas de modelos
    - modelo activo
    - métricas de cada versión
    - hash del dataset utilizado
    - modelo con mejor performance
    """

    def __init__(
        self,
        base_path: str = "data/models",
    ):
        self.base_path = Path(base_path)

        self.base_path.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _competition_path(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> Path:

        path = (
            self.base_path
            / sport
            / competition
            / season
        )

        path.mkdir(
            parents=True,
            exist_ok=True,
        )

        return path

    def _registry_file(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> Path:

        return (
            self._competition_path(
                sport,
                competition,
                season,
            )
            / "registry.csv"
        )

    def _active_file(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> Path:

        active_dir = (
            self._competition_path(
                sport,
                competition,
                season,
            )
            / "active"
        )

        active_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        return active_dir / "model.pkl"

    def _versions_dir(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> Path:

        path = (
            self._competition_path(
                sport,
                competition,
                season,
            )
            / "versions"
        )

        path.mkdir(
            parents=True,
            exist_ok=True,
        )

        return path

    def register(
        self,
        model: Any,
        sport: str,
        competition: str,
        season: str,
        data_hash: str,
        training_rows: int,
        validation_rows: int,
        log_loss: Optional[float],
        accuracy: Optional[float],
        activate: bool = False,
    ) -> str:

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        model_id = (
            f"model_{timestamp}"
        )

        model_file = (
            self._versions_dir(
                sport,
                competition,
                season,
            )
            / f"{model_id}.pkl"
        )

        # -------------------------------------------------
        # GUARDAR MODELO
        # -------------------------------------------------

        with open(
            model_file,
            "wb",
        ) as file:

            pickle.dump(
                model,
                file,
            )

        # -------------------------------------------------
        # REGISTRO
        # -------------------------------------------------

        row = {
            "model_id": model_id,
            "created_at": datetime.now().isoformat(),
            "sport": sport,
            "competition": competition,
            "season": season,
            "data_hash": data_hash,
            "training_rows": training_rows,
            "validation_rows": validation_rows,
            "log_loss": log_loss,
            "accuracy": accuracy,
            "status": (
                "active"
                if activate
                else "archived"
            ),
            "model_file": str(
                model_file
            ),
        }

        registry_file = self._registry_file(
            sport,
            competition,
            season,
        )

        if registry_file.exists():

            registry = pd.read_csv(
                registry_file
            )

        else:

            registry = pd.DataFrame()

        # Si este modelo se convierte en activo,
        # todos los anteriores pasan a archived.

        if activate and not registry.empty:

            registry["status"] = "archived"

        registry = pd.concat(
            [
                registry,
                pd.DataFrame([row]),
            ],
            ignore_index=True,
        )

        registry.to_csv(
            registry_file,
            index=False,
            encoding="utf-8-sig",
        )

        # -------------------------------------------------
        # COPIAR COMO MODELO ACTIVO
        # -------------------------------------------------

        if activate:

            active_file = self._active_file(
                sport,
                competition,
                season,
            )

            with open(
                model_file,
                "rb",
            ) as source:

                model_bytes = source.read()

            with open(
                active_file,
                "wb",
            ) as target:

                target.write(
                    model_bytes
                )

        return model_id

    def load_active(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> Optional[Any]:

        active_file = self._active_file(
            sport,
            competition,
            season,
        )

        if not active_file.exists():

            return None

        with open(
            active_file,
            "rb",
        ) as file:

            return pickle.load(file)

    def get_registry(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> pd.DataFrame:

        registry_file = self._registry_file(
            sport,
            competition,
            season,
        )

        if not registry_file.exists():

            return pd.DataFrame()

        return pd.read_csv(
            registry_file
        )

    def list_models(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> pd.DataFrame:
        """
        Devuelve todas las versiones registradas,
        ordenadas desde la más reciente.
        """

        registry = self.get_registry(
            sport,
            competition,
            season,
        )

        if registry.empty:

            return registry

        if "created_at" in registry.columns:

            registry = registry.sort_values(
                "created_at",
                ascending=False,
            )

        return registry.reset_index(
            drop=True
        )

    def get_active_record(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> Optional[dict]:

        registry = self.get_registry(
            sport,
            competition,
            season,
        )

        if registry.empty:

            return None

        active = registry[
            registry["status"] == "active"
        ]

        if active.empty:

            return None

        return active.iloc[-1].to_dict()

    def get_latest_record(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> Optional[dict]:
        """
        Devuelve la versión más reciente registrada.
        """

        registry = self.list_models(
            sport,
            competition,
            season,
        )

        if registry.empty:

            return None

        return registry.iloc[0].to_dict()

    def get_best_record(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> Optional[dict]:
        """
        Devuelve el modelo con menor log_loss.

        Menor log_loss = mejor desempeño
        en la validación registrada.
        """

        registry = self.get_registry(
            sport,
            competition,
            season,
        )

        if registry.empty:

            return None

        if "log_loss" not in registry.columns:

            return None

        candidates = registry.copy()

        candidates["log_loss"] = pd.to_numeric(
            candidates["log_loss"],
            errors="coerce",
        )

        candidates = candidates.dropna(
            subset=["log_loss"]
        )

        if candidates.empty:

            return None

        best = candidates.sort_values(
            "log_loss",
            ascending=True,
        ).iloc[0]

        return best.to_dict()

    def has_same_data(
        self,
        sport: str,
        competition: str,
        season: str,
        data_hash: str,
    ) -> bool:

        record = self.get_active_record(
            sport,
            competition,
            season,
        )

        if record is None:

            return False

        return (
            str(record["data_hash"])
            == str(data_hash)
        )