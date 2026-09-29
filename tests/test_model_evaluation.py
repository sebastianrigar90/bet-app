
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json

import numpy as np
import pandas as pd

from src.modeling.trainer import ModelTrainer
from src.modeling.evaluation import ModelEvaluator


# =========================================================
# CONFIGURACIÓN
# =========================================================

SPORT = "football"
COMPETITION = "premier_league"
SEASON = "2026-27"

OUTPUT_DIR = Path("outputs/model_evaluation")

# Una muestra menor a este valor se clasifica como baja.
MIN_VALIDATION_ROWS = 30

PROBABILITY_TOLERANCE = 1e-6


# =========================================================
# UTILIDADES
# =========================================================

def find_column(
    dataframe: pd.DataFrame,
    candidates: list[str],
) -> str:
    """
    Busca una columna usando una lista de nombres posibles.
    La búsqueda no distingue mayúsculas y minúsculas.
    """

    columns = {
        str(column).strip().lower(): column
        for column in dataframe.columns
    }

    for candidate in candidates:
        key = candidate.strip().lower()

        if key in columns:
            return columns[key]

    raise KeyError(
        "No se encontró ninguna de estas columnas: "
        f"{candidates}. Columnas disponibles: "
        f"{list(dataframe.columns)}"
    )


def get_real_result(
    home_goals: float,
    away_goals: float,
) -> tuple[int, str]:
    """
    Codificación:
        0 = victoria local
        1 = empate
        2 = victoria visitante
    """

    if home_goals > away_goals:
        return 0, "home"

    if home_goals == away_goals:
        return 1, "draw"

    return 2, "away"


def classify_sample(
    validation_rows: int,
) -> str:
    """
    Clasificación operativa de la muestra de validación.
    """

    if validation_rows < MIN_VALIDATION_ROWS:
        return "LOW_SAMPLE_SIZE"

    return "PRELIMINARY"


# =========================================================
# EVALUACIÓN
# =========================================================

def main():

    run_id = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 80)
    print("EVALUACIÓN INTEGRAL DEL MODELO")
    print("=" * 80)

    print(f"Deporte: {SPORT}")
    print(f"Competición: {COMPETITION}")
    print(f"Temporada: {SEASON}")
    print(f"Run ID: {run_id}")

    # -----------------------------------------------------
    # 1. CARGA DEL HISTÓRICO
    # -----------------------------------------------------

    print("\n1. Cargando histórico...")

    trainer = ModelTrainer()

    raw_data = trainer.load_processed_data(
        sport=SPORT,
        competition=COMPETITION,
        season=SEASON,
    )

    data = trainer.prepare_data(raw_data)

    if data.empty:
        raise ValueError(
            "El histórico está vacío después del preprocesamiento."
        )

    print(f"Partidos disponibles: {len(data)}")

    # -----------------------------------------------------
    # 2. SEPARACIÓN CRONOLÓGICA
    # -----------------------------------------------------

    print("\n2. Separando entrenamiento y validación...")

    train_data, validation_data = (
        trainer._split_train_validation(data)
    )

    print(f"Entrenamiento: {len(train_data)}")
    print(f"Validación: {len(validation_data)}")

    if train_data.empty:
        raise ValueError(
            "No existen suficientes partidos para entrenar."
        )

    if validation_data.empty:
        raise ValueError(
            "No existen partidos para realizar la evaluación."
        )

    # -----------------------------------------------------
    # 3. ENTRENAMIENTO TEMPORAL
    # -----------------------------------------------------

    print("\n3. Entrenando modelo temporal...")

    model = trainer.train(
        sport=SPORT,
        competition=COMPETITION,
        season=SEASON,
        data=train_data,
    )

    print("Entrenamiento completado.")

    # -----------------------------------------------------
    # 4. IDENTIFICAR COLUMNAS DE RESULTADOS
    # -----------------------------------------------------

    home_goals_col = find_column(
        validation_data,
        [
            "home_goals",
            "goals_home",
            "goles_local",
            "goles_locales",
            "home_score",
            "score_home",
            "goles_local_modelo",
        ],
    )

    away_goals_col = find_column(
        validation_data,
        [
            "away_goals",
            "goals_away",
            "goles_visitante",
            "goles_visitantes",
            "away_score",
            "score_away",
            "goles_visitante_modelo",
        ],
    )

    print(
        f"Columna de goles locales: {home_goals_col}"
    )

    print(
        f"Columna de goles visitantes: {away_goals_col}"
    )

    # -----------------------------------------------------
    # 5. DIAGNÓSTICO DE PREDICCIONES
    # -----------------------------------------------------

    print("\n4. Evaluando partidos...")
    print("-" * 80)

    prediction_rows = []
    skipped_rows = []

    for index, row in validation_data.iterrows():

        home = row["home"]
        away = row["away"]

        home_goals = row[home_goals_col]
        away_goals = row[away_goals_col]

        diagnostic = {
            "source_index": index,
            "home": home,
            "away": away,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "prob_home": np.nan,
            "prob_draw": np.nan,
            "prob_away": np.nan,
            "probability_sum": np.nan,
            "actual_result": None,
            "predicted_result": None,
            "prediction_valid": False,
            "skip_reason": None,
        }

        try:

            if pd.isna(home_goals) or pd.isna(away_goals):
                raise ValueError(
                    "Resultado real incompleto."
                )

            actual_result, actual_label = get_real_result(
                float(home_goals),
                float(away_goals),
            )

            prediction = model.predict_match(
                home,
                away,
            )

            probabilities = np.array(
                [
                    float(prediction["prob_home"]),
                    float(prediction["prob_draw"]),
                    float(prediction["prob_away"]),
                ],
                dtype=float,
            )

            probability_sum = float(
                probabilities.sum()
            )

            diagnostic.update(
                {
                    "prob_home": probabilities[0],
                    "prob_draw": probabilities[1],
                    "prob_away": probabilities[2],
                    "probability_sum": probability_sum,
                    "actual_result": actual_label,
                    "predicted_result": [
                        "home",
                        "draw",
                        "away",
                    ][int(np.argmax(probabilities))],
                }
            )

            # Validaciones de integridad.
            if not np.isfinite(probabilities).all():
                raise ValueError(
                    "Probabilidades NaN o infinitas."
                )

            if (
                (probabilities < 0).any()
                or (probabilities > 1).any()
            ):
                raise ValueError(
                    "Probabilidades fuera del rango [0, 1]."
                )

            if abs(
                probability_sum - 1.0
            ) > PROBABILITY_TOLERANCE:
                raise ValueError(
                    "Probabilidades no normalizadas."
                )

            diagnostic["prediction_valid"] = True

            prediction_rows.append(
                {
                    "y_true": actual_result,
                    "probabilities": probabilities,
                    "diagnostic": diagnostic,
                }
            )

            print(
                f"{home} vs {away} | "
                f"Real: {actual_label} | "
                f"Probabilidades: "
                f"{probabilities.tolist()} | "
                f"Suma: {probability_sum:.12f} | "
                f"VÁLIDA"
            )

        except Exception as exc:

            diagnostic["skip_reason"] = (
                f"{type(exc).__name__}: {exc}"
            )

            skipped_rows.append(diagnostic)

            print(
                f"{home} vs {away} | "
                f"OMITIDO: {diagnostic['skip_reason']}"
            )

    # -----------------------------------------------------
    # 6. RESUMEN DE COBERTURA
    # -----------------------------------------------------

    valid_count = len(prediction_rows)
    skipped_count = len(skipped_rows)
    validation_count = len(validation_data)

    coverage = (
        valid_count / validation_count
        if validation_count > 0
        else 0.0
    )

    print("\n5. Resumen de cobertura")
    print("-" * 80)

    print(f"Partidos de validación: {validation_count}")
    print(f"Predicciones válidas: {valid_count}")
    print(f"Partidos omitidos: {skipped_count}")
    print(f"Cobertura: {coverage:.2%}")

    # -----------------------------------------------------
    # 7. EVALUACIÓN DE MÉTRICAS
    # -----------------------------------------------------

    if valid_count == 0:
        raise ValueError(
            "No existen predicciones válidas para evaluar."
        )

    y_true = np.array(
        [
            item["y_true"]
            for item in prediction_rows
        ],
        dtype=int,
    )

    probabilities = np.vstack(
        [
            item["probabilities"]
            for item in prediction_rows
        ]
    )

    evaluator = ModelEvaluator(
        labels=["home", "draw", "away"],
        n_bins=10,
    )

    result = evaluator.evaluate(
        y_true=y_true,
        probabilities=probabilities,
        model_name="poisson",
        model_version=None,
        sport=SPORT,
        competition=COMPETITION,
        season=SEASON,
    )

    # -----------------------------------------------------
    # 8. ENRIQUECER MÉTRICAS
    # -----------------------------------------------------

    metrics = result["metrics"]

    metrics.update(
        {
            "run_id": run_id,
            "training_rows": len(train_data),
            "validation_rows": validation_count,
            "valid_predictions": valid_count,
            "skipped_rows": skipped_count,
            "coverage": coverage,
            "sample_status": classify_sample(valid_count),
            "probability_tolerance": PROBABILITY_TOLERANCE,
        }
    )

    if valid_count < MIN_VALIDATION_ROWS:
        metrics["evaluation_status"] = "LOW_SAMPLE_SIZE"
    else:
        metrics["evaluation_status"] = "PRELIMINARY"

    # -----------------------------------------------------
    # 9. EXPORTAR REPORTES
    # -----------------------------------------------------

    print("\n6. Guardando reportes...")

    report_paths = ModelEvaluator.save_report(
        result=result,
        output_dir=str(OUTPUT_DIR),
        run_id=run_id,
    )

    # Reescribir el CSV de métricas con los campos adicionales.
    metrics_file = Path(
        report_paths["metrics"]
    )

    pd.DataFrame(
        [metrics]
    ).to_csv(
        metrics_file,
        index=False,
        encoding="utf-8-sig",
    )

    # Reporte individual de partidos.
    diagnostics = [
        item["diagnostic"]
        for item in prediction_rows
    ] + skipped_rows

    diagnostics_df = pd.DataFrame(
        diagnostics
    )

    diagnostics_file = (
        OUTPUT_DIR
        / f"match_diagnostics_{run_id}.csv"
    )

    diagnostics_df.to_csv(
        diagnostics_file,
        index=False,
        encoding="utf-8-sig",
    )

    # Reporte JSON enriquecido.
    json_file = Path(
        report_paths["json"]
    )

    with json_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            {
                "metrics": metrics,
                "report_paths": {
                    **report_paths,
                    "match_diagnostics": str(
                        diagnostics_file
                    ),
                },
            },
            file,
            indent=4,
            ensure_ascii=False,
            default=str,
        )

    # -----------------------------------------------------
    # 10. RESULTADO FINAL
    # -----------------------------------------------------

    print("\n" + "=" * 80)
    print("EVALUACIÓN COMPLETADA")
    print("=" * 80)

    print(
        f"Accuracy: "
        f"{metrics['accuracy']:.4f}"
    )

    print(
        f"Log Loss: "
        f"{metrics['log_loss']:.4f}"
    )

    print(
        f"Brier Score: "
        f"{metrics['brier_score']:.4f}"
    )

    calibration_error = metrics[
        "mean_calibration_error"
    ]

    if calibration_error is not None:
        print(
            f"Error medio de calibración: "
            f"{calibration_error:.4f}"
        )

    print(
        f"Estado de evaluación: "
        f"{metrics['evaluation_status']}"
    )

    print(
        f"Estado de muestra: "
        f"{metrics['sample_status']}"
    )

    print("\nArchivos generados:")

    for name, path in report_paths.items():
        print(f"- {name}: {path}")

    print(f"- Diagnóstico: {diagnostics_file}")

    print("\nLa evaluación no modifica el modelo activo.")


if __name__ == "__main__":
    main()