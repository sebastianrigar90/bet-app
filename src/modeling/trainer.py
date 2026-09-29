
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

from .evaluation import ModelEvaluator
from .poisson_model import PoissonModel
from .registry import ModelRegistry


class ModelTrainer:
    """
    Gestión central de modelos deportivos.

    Responsabilidades:
    - Cargar datos procesados.
    - Preparar datos de entrenamiento.
    - Detectar si el dataset cambió.
    - Reutilizar el modelo activo cuando no hay datos nuevos.
    - Entrenar una nueva versión cuando hay datos nuevos.
    - Evaluar el modelo con métricas estandarizadas.
    - Guardar reportes de evaluación.
    - Registrar cada versión del modelo.
    - Mantener un modelo activo.
    """

    def __init__(
        self,
        config_path: str = "config/models.yaml",
        registry_path: str = "data/models",
        evaluation_path: str = "outputs/model_evaluation",
    ):
        self.config_path = Path(config_path)
        self.config = self._load_config()

        self.registry = ModelRegistry(
            base_path=registry_path
        )

        self.evaluator = ModelEvaluator()
        self.evaluation_path = Path(evaluation_path)

    # ---------------------------------------------------------
    # CONFIGURACIÓN
    # ---------------------------------------------------------

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"No existe el archivo: {self.config_path}"
            )

        with open(
            self.config_path,
            "r",
            encoding="utf-8",
        ) as file:
            return yaml.safe_load(file) or {}

    def get_config(
        self,
        sport: str,
        competition: str,
    ) -> dict:
        try:
            config = self.config[sport][competition]

        except KeyError as exc:
            raise ValueError(
                f"No existe configuración para "
                f"{sport}/{competition}"
            ) from exc

        return config

    # ---------------------------------------------------------
    # CARGA DE DATOS
    # ---------------------------------------------------------

    @staticmethod
    def load_processed_data(
        sport: str,
        competition: str,
        season: str,
    ) -> pd.DataFrame:

        path = (
            Path("data")
            / "processed"
            / sport
            / competition
            / season
            / "events.csv"
        )

        if not path.exists():
            raise FileNotFoundError(
                f"No existe histórico procesado:\n{path}"
            )

        df = pd.read_csv(path)

        if df.empty:
            raise ValueError(
                f"El histórico está vacío:\n{path}"
            )

        return df

    @staticmethod
    def prepare_data(
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        required = {
            "date",
            "home",
            "away",
            "home_score",
            "away_score",
        }

        missing = required - set(df.columns)

        if missing:
            raise ValueError(
                f"Faltan columnas requeridas: {sorted(missing)}"
            )

        data = df[
            [
                "date",
                "home",
                "away",
                "home_score",
                "away_score",
            ]
        ].copy()

        data["date"] = pd.to_datetime(
            data["date"],
            errors="coerce",
        )

        data["home_score"] = pd.to_numeric(
            data["home_score"],
            errors="coerce",
        )

        data["away_score"] = pd.to_numeric(
            data["away_score"],
            errors="coerce",
        )

        data = data.dropna(
            subset=[
                "date",
                "home",
                "away",
                "home_score",
                "away_score",
            ]
        )

        # Los marcadores deben ser valores válidos
        # y no negativos.
        data = data[
            (data["home_score"] >= 0)
            & (data["away_score"] >= 0)
        ].copy()

        data = data.sort_values(
            "date"
        ).reset_index(drop=True)

        if data.empty:
            raise ValueError(
                "No existen partidos finalizados disponibles "
                "para entrenar."
            )

        return data

    # ---------------------------------------------------------
    # HUELLA DEL DATASET
    # ---------------------------------------------------------

    @staticmethod
    def _data_hash(
        data: pd.DataFrame,
    ) -> str:
        """
        Genera una huella estable del dataset
        utilizado para entrenamiento.
        """

        columns = [
            "date",
            "home",
            "away",
            "home_score",
            "away_score",
        ]

        available = [
            column
            for column in columns
            if column in data.columns
        ]

        normalized = (
            data[available]
            .sort_values(available)
            .reset_index(drop=True)
        )

        content = normalized.to_csv(
            index=False
        ).encode("utf-8")

        return hashlib.sha256(
            content
        ).hexdigest()

    # ---------------------------------------------------------
    # SEPARACIÓN TEMPORAL
    # ---------------------------------------------------------

    @staticmethod
    def _split_train_validation(
        data: pd.DataFrame,
        validation_fraction: float = 0.20,
        min_train_rows: int = 10,
        min_validation_rows: int = 1,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Separa cronológicamente los datos.

        Si no existe un volumen mínimo para entrenar
        y validar de forma independiente, devuelve
        una validación vacía.

        Nunca utiliza los mismos partidos para
        entrenamiento y evaluación.
        """

        if not 0 < validation_fraction < 1:
            raise ValueError(
                "validation_fraction debe estar entre 0 y 1."
            )

        if len(data) < (
            min_train_rows + min_validation_rows
        ):
            return data.copy(), data.iloc[0:0].copy()

        split = int(
            len(data) * (1 - validation_fraction)
        )

        split = max(
            min_train_rows,
            min(
                split,
                len(data) - min_validation_rows,
            ),
        )

        train = data.iloc[:split].copy()
        validation = data.iloc[split:].copy()

        return train, validation

    # ---------------------------------------------------------
    # CONSTRUCCIÓN DE RESULTADOS REALES
    # ---------------------------------------------------------

    @staticmethod
    def _actual_result(
        home_score: int,
        away_score: int,
    ) -> int:
        """
        Codificación de resultados:
        0 = victoria local
        1 = empate
        2 = victoria visitante
        """

        if home_score > away_score:
            return 0

        if home_score == away_score:
            return 1

        return 2

    # ---------------------------------------------------------
    # PREDICCIONES DE VALIDACIÓN
    # ---------------------------------------------------------

    @classmethod
    def _collect_predictions(
        cls,
        model: PoissonModel,
        validation: pd.DataFrame,
    ) -> tuple[list[int], list[list[float]], int]:
        """
        Genera probabilidades y resultados reales.

        Los partidos con equipos desconocidos o
        predicciones inválidas se excluyen del cálculo.
        """

        y_true = []
        probabilities = []

        skipped = 0

        for _, row in validation.iterrows():

            try:
                prediction = model.predict_match(
                    row["home"],
                    row["away"],
                )

                probs = [
                    float(prediction["prob_home"]),
                    float(prediction["prob_draw"]),
                    float(prediction["prob_away"]),
                ]

            except (ValueError, KeyError, TypeError):
                skipped += 1
                continue

            # Validar que las probabilidades sean utilizables.
            if (
                len(probs) != 3
                or any(
                    not pd.notna(p)
                    or p < 0
                    or p > 1
                    for p in probs
                )
            ):
                skipped += 1
                continue

            probability_sum = sum(probs)

            if (
                probability_sum <= 0
                or abs(probability_sum - 1.0) > 1e-6
            ):
                skipped += 1
                continue

            actual = cls._actual_result(
                int(row["home_score"]),
                int(row["away_score"]),
            )

            y_true.append(actual)
            probabilities.append(probs)

        return y_true, probabilities, skipped

    # ---------------------------------------------------------
    # EVALUACIÓN ESTANDARIZADA
    # ---------------------------------------------------------

    def _evaluate_model(
        self,
        model: PoissonModel,
        validation: pd.DataFrame,
        sport: str = "football",
        competition: str = "unknown",
        season: str = "unknown",
        model_name: str = "poisson",
        model_version: str = "candidate",
    ) -> dict:
        """
        Evalúa el modelo y devuelve métricas estándar.

        Si no hay suficientes observaciones válidas,
        la evaluación se marca como INSUFFICIENT_DATA.
        """

        y_true, probabilities, skipped = (
            self._collect_predictions(
                model=model,
                validation=validation,
            )
        )

        evaluation_rows = len(y_true)

        if evaluation_rows == 0:
            return {
                "metrics": {
                    "model_name": model_name,
                    "model_version": model_version,
                    "sport": sport,
                    "competition": competition,
                    "season": season,
                    "evaluation_rows": 0,
                    "skipped_rows": skipped,
                    "accuracy": None,
                    "log_loss": None,
                    "brier_score": None,
                    "mean_calibration_error": None,
                    "evaluation_status": "INSUFFICIENT_DATA",
                },
                "calibration": pd.DataFrame(),
            }

        result = self.evaluator.evaluate(
            y_true=y_true,
            probabilities=probabilities,
            model_name=model_name,
            model_version=model_version,
            sport=sport,
            competition=competition,
            season=season,
        )

        metrics = result["metrics"].copy()

        metrics["evaluation_rows"] = evaluation_rows
        metrics["skipped_rows"] = skipped

        if evaluation_rows < 10:
            metrics["evaluation_status"] = (
                "LOW_SAMPLE_SIZE"
            )

        return {
            "metrics": metrics,
            "calibration": result["calibration"],
        }

    # ---------------------------------------------------------
    # ENTRENAMIENTO
    # ---------------------------------------------------------

    def train(
        self,
        sport: str,
        competition: str,
        season: str,
        data: Optional[pd.DataFrame] = None,
    ) -> PoissonModel:

        config = self.get_config(
            sport=sport,
            competition=competition,
        )

        model_name = config.get(
            "model",
            "poisson",
        )

        if model_name != "poisson":
            raise ValueError(
                f"Modelo no soportado: {model_name}"
            )

        if data is None:
            data = self.load_processed_data(
                sport=sport,
                competition=competition,
                season=season,
            )

        prepared = self.prepare_data(data)

        model = PoissonModel(
            random_starts=config.get(
                "random_starts",
                20,
            ),
            max_goals=config.get(
                "max_goals",
                10,
            ),
        )

        model.fit(prepared)

        return model

    # ---------------------------------------------------------
    # ENTRENAMIENTO O REUTILIZACIÓN
    # ---------------------------------------------------------

    def get_or_train(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> tuple[PoissonModel, bool]:

        data = self.load_processed_data(
            sport=sport,
            competition=competition,
            season=season,
        )

        prepared = self.prepare_data(data)

        data_hash = self._data_hash(prepared)

        # -----------------------------------------------------
        # 1. ¿YA TENEMOS MODELO CON ESTE DATASET?
        # -----------------------------------------------------

        if self.registry.has_same_data(
            sport=sport,
            competition=competition,
            season=season,
            data_hash=data_hash,
        ):

            active = self.registry.load_active(
                sport=sport,
                competition=competition,
                season=season,
            )

            if active is not None:
                return active, False

        # -----------------------------------------------------
        # 2. HAY DATOS NUEVOS → ENTRENAR
        # -----------------------------------------------------

        train_data, validation_data = (
            self._split_train_validation(prepared)
        )

        model = self.train(
            sport=sport,
            competition=competition,
            season=season,
            data=train_data,
        )

        evaluation = self._evaluate_model(
            model=model,
            validation=validation_data,
            sport=sport,
            competition=competition,
            season=season,
            model_name="poisson",
        )

        metrics = evaluation["metrics"]

        # Guardar reportes cuando existan observaciones evaluables.
        if metrics["evaluation_rows"] > 0:
            self.evaluator.save_report(
                result=evaluation,
                output_dir=self.evaluation_path,
            )

        # -----------------------------------------------------
        # 3. COMPARAR CONTRA MODELO ACTIVO
        # -----------------------------------------------------

        active_record = self.registry.get_active_record(
            sport=sport,
            competition=competition,
            season=season,
        )

        activate = active_record is None

        # Conservamos temporalmente el criterio anterior:
        # menor log-loss que el modelo activo.
        #
        # La selección multicriterio se implementará
        # después de validar el historial de métricas.

        if (
            active_record is not None
            and metrics["log_loss"] is not None
            and pd.notna(active_record.get("log_loss"))
        ):

            activate = (
                metrics["log_loss"]
                < float(active_record["log_loss"])
            )

        # -----------------------------------------------------
        # 4. REGISTRAR NUEVA VERSIÓN
        # -----------------------------------------------------

        self.registry.register(
            model=model,
            sport=sport,
            competition=competition,
            season=season,
            data_hash=data_hash,
            training_rows=len(train_data),
            validation_rows=metrics["evaluation_rows"],
            log_loss=metrics["log_loss"],
            accuracy=metrics["accuracy"],
            activate=activate,
        )

        # -----------------------------------------------------
        # 5. DEVOLVER MODELO ACTIVO
        # -----------------------------------------------------

        if activate:
            return model, True

        active = self.registry.load_active(
            sport=sport,
            competition=competition,
            season=season,
        )

        if active is None:
            raise RuntimeError(
                "No existe un modelo activo "
                "después del entrenamiento."
            )

        return active, False

    # ---------------------------------------------------------
    # CARGAR MODELO ACTIVO
    # ---------------------------------------------------------

    def load_active_model(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> PoissonModel:

        model = self.registry.load_active(
            sport=sport,
            competition=competition,
            season=season,
        )

        if model is None:
            raise FileNotFoundError(
                "No existe un modelo activo para "
                f"{sport}/{competition}/{season}. "
                "Ejecute get_or_train() primero."
            )

        return model