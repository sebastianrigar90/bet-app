
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class ModelEvaluator:
    """
    Evaluador estándar para modelos de clasificación multiclase.

    Calcula:
    - Log-loss
    - Brier Score
    - Accuracy
    - Métricas de calibración
    - Cobertura de evaluación

    No depende del algoritmo utilizado para generar
    las probabilidades.
    """

    def __init__(
        self,
        labels: list[str] | None = None,
        n_bins: int = 10,
        epsilon: float = 1e-15,
    ):
        self.labels = labels or [
            "home",
            "draw",
            "away",
        ]

        self.n_bins = n_bins
        self.epsilon = epsilon

        if self.n_bins < 2:
            raise ValueError(
                "n_bins debe ser al menos 2."
            )

    # -------------------------------------------------
    # VALIDACIÓN DE ENTRADAS
    # -------------------------------------------------

    def _validate(
        self,
        y_true: np.ndarray,
        probabilities: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:

        y_true = np.asarray(y_true)
        probabilities = np.asarray(
            probabilities,
            dtype=float,
        )

        if probabilities.ndim != 2:
            raise ValueError(
                "Las probabilidades deben ser "
                "una matriz bidimensional."
            )

        if len(y_true) != len(probabilities):
            raise ValueError(
                "La cantidad de resultados reales "
                "no coincide con las predicciones."
            )

        if probabilities.shape[1] != len(self.labels):
            raise ValueError(
                "La cantidad de columnas de "
                "probabilidades no coincide con labels."
            )

        if len(y_true) == 0:
            raise ValueError(
                "No existen observaciones para evaluar."
            )

        if not np.isfinite(probabilities).all():
            raise ValueError(
                "Las probabilidades contienen "
                "valores NaN o infinitos."
            )

        if (
            (probabilities < 0).any()
            or (probabilities > 1).any()
        ):
            raise ValueError(
                "Las probabilidades deben estar "
                "entre 0 y 1."
            )

        row_sums = probabilities.sum(axis=1)

        if not np.allclose(
            row_sums,
            1.0,
            atol=1e-6,
        ):
            raise ValueError(
                "Las probabilidades de cada "
                "observación deben sumar 1."
            )

        if not np.isin(
            y_true,
            np.arange(len(self.labels)),
        ).all():
            raise ValueError(
                "Se encontraron etiquetas reales "
                "fuera del rango esperado."
            )

        return y_true.astype(int), probabilities

    # -------------------------------------------------
    # LOG-LOSS
    # -------------------------------------------------

    def _log_loss(
        self,
        y_true: np.ndarray,
        probabilities: np.ndarray,
    ) -> float:

        probabilities = np.clip(
            probabilities,
            self.epsilon,
            1.0,
        )

        probabilities = (
            probabilities
            / probabilities.sum(axis=1, keepdims=True)
        )

        selected = probabilities[
            np.arange(len(y_true)),
            y_true,
        ]

        return float(
            -np.mean(np.log(selected))
        )

    # -------------------------------------------------
    # BRIER SCORE MULTICLASE
    # -------------------------------------------------

    @staticmethod
    def _brier_score(
        y_true: np.ndarray,
        probabilities: np.ndarray,
    ) -> float:

        one_hot = np.eye(
            probabilities.shape[1]
        )[y_true]

        return float(
            np.mean(
                np.sum(
                    (probabilities - one_hot) ** 2,
                    axis=1,
                )
            )
        )

    # -------------------------------------------------
    # CALIBRACIÓN
    # -------------------------------------------------

    def _calibration_report(
        self,
        y_true: np.ndarray,
        probabilities: np.ndarray,
    ) -> pd.DataFrame:

        rows = []

        bin_edges = np.linspace(
            0.0,
            1.0,
            self.n_bins + 1,
        )

        for class_index, label in enumerate(
            self.labels
        ):

            predicted = probabilities[
                :,
                class_index,
            ]

            observed = (
                y_true == class_index
            ).astype(int)

            bins = pd.cut(
                predicted,
                bins=bin_edges,
                include_lowest=True,
                right=True,
            )

            for bin_interval in bins.categories:

                mask = (
                    bins == bin_interval
                )

                count = int(mask.sum())

                if count == 0:
                    continue

                mean_predicted = float(
                    predicted[mask].mean()
                )

                observed_frequency = float(
                    observed[mask].mean()
                )

                rows.append(
                    {
                        "class": label,
                        "probability_bin": str(
                            bin_interval
                        ),
                        "observations": count,
                        "mean_predicted": mean_predicted,
                        "observed_frequency": (
                            observed_frequency
                        ),
                        "calibration_error": (
                            observed_frequency
                            - mean_predicted
                        ),
                        "absolute_error": abs(
                            observed_frequency
                            - mean_predicted
                        ),
                    }
                )

        return pd.DataFrame(rows)

    # -------------------------------------------------
    # EVALUACIÓN COMPLETA
    # -------------------------------------------------

    def evaluate(
        self,
        y_true: Any,
        probabilities: Any,
        model_name: str,
        model_version: str | None = None,
        sport: str | None = None,
        competition: str | None = None,
        season: str | None = None,
    ) -> dict:

        y_true, probabilities = self._validate(
            y_true,
            probabilities,
        )

        predictions = np.argmax(
            probabilities,
            axis=1,
        )

        accuracy = float(
            np.mean(
                predictions == y_true
            )
        )

        log_loss = self._log_loss(
            y_true,
            probabilities,
        )

        brier_score = self._brier_score(
            y_true,
            probabilities,
        )

        calibration = self._calibration_report(
            y_true,
            probabilities,
        )

        if calibration.empty:
            mean_calibration_error = None
        else:
            weights = calibration[
                "observations"
            ].to_numpy()

            errors = calibration[
                "absolute_error"
            ].to_numpy()

            mean_calibration_error = float(
                np.average(
                    errors,
                    weights=weights,
                )
            )

        metrics = {
            "model_name": model_name,
            "model_version": model_version,
            "sport": sport,
            "competition": competition,
            "season": season,
            "evaluation_rows": int(
                len(y_true)
            ),
            "accuracy": accuracy,
            "log_loss": log_loss,
            "brier_score": brier_score,
            "mean_calibration_error": (
                mean_calibration_error
            ),
            "evaluation_status": "SUCCESS",
        }

        return {
            "metrics": metrics,
            "calibration": calibration,
        }

    # -------------------------------------------------
    # EXPORTACIÓN ESTÁNDAR
    # -------------------------------------------------

    @staticmethod
    def save_report(
        result: dict,
        output_dir: str = "outputs/model_evaluation",
        run_id: str | None = None,
    ) -> dict:

        output_path = Path(output_dir)

        output_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        if run_id is None:
            run_id = pd.Timestamp.now().strftime(
                "%Y%m%d_%H%M%S"
            )

        metrics_file = (
            output_path
            / f"model_metrics_{run_id}.csv"
        )

        calibration_file = (
            output_path
            / f"calibration_report_{run_id}.csv"
        )

        json_file = (
            output_path
            / f"evaluation_{run_id}.json"
        )

        metrics_df = pd.DataFrame(
            [result["metrics"]]
        )

        metrics_df.to_csv(
            metrics_file,
            index=False,
            encoding="utf-8-sig",
        )

        result["calibration"].to_csv(
            calibration_file,
            index=False,
            encoding="utf-8-sig",
        )

        metrics_df.to_json(
            json_file,
            orient="records",
            indent=4,
            force_ascii=False,
        )

        return {
            "metrics": str(metrics_file),
            "calibration": str(calibration_file),
            "json": str(json_file),
        }