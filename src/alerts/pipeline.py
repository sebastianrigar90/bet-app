from __future__ import annotations

import pandas as pd

from src.modeling.trainer import ModelTrainer
from src.odds.wplay import WplaySource
from src.odds.comparator import OddsComparator
from src.alerts.value_detector import ValueDetector
from src.tracking.run import RunTracker


class AlertPipeline:

    def __init__(
        self,
        min_edge: float = 0.05,
        stake: float = 10000.0,
    ):
        self.min_edge = min_edge
        self.stake = stake

        self.trainer = ModelTrainer()

        self.comparator = OddsComparator()

        self.detector = ValueDetector(
            min_edge=min_edge
        )

        self.run_tracker = RunTracker()

    # =========================================================
    # ESQUEMA VACÍO DE COMPARACIÓN
    # =========================================================

    @staticmethod
    def _empty_comparison() -> pd.DataFrame:

        return pd.DataFrame(
            columns=[
                "local",
                "visitante",
                "cuota_local",
                "cuota_empate",
                "cuota_visita",
                "fair_odds_home",
                "fair_odds_draw",
                "fair_odds_away",
                "edge_local",
                "edge_empate",
                "edge_visitante",
            ]
        )

    # =========================================================
    # EJECUTAR PIPELINE
    # =========================================================

    def run(
        self,
        sport: str,
        competition: str,
        season: str,
        wplay_url: str,
    ) -> dict:

        # -----------------------------------------------------
        # 1. RUN ID
        # -----------------------------------------------------

        run_id = self.run_tracker.start_run()

        # -----------------------------------------------------
        # 2. OBTENER MODELO
        # -----------------------------------------------------

        model, model_is_new = (
            self.trainer.get_or_train(
                sport=sport,
                competition=competition,
                season=season,
            )
        )

        # -----------------------------------------------------
        # 3. DATOS PROCESADOS
        # -----------------------------------------------------

        df = self.trainer.load_processed_data(
            sport=sport,
            competition=competition,
            season=season,
        )

        future = df[
            df["home_score"].isna()
            & df["away_score"].isna()
        ].copy()

        if future.empty:

            empty = self._empty_comparison()

            return {
                "run_id": run_id,
                "future": future,
                "predictions": pd.DataFrame(),
                "market": pd.DataFrame(),
                "comparison": empty,
                "detected_alerts": empty.copy(),
                "alerts": empty.copy(),
                "model_is_new": model_is_new,
            }

        # -----------------------------------------------------
        # 4. PREDICCIONES
        # -----------------------------------------------------

        rows = []

        for _, row in future.iterrows():

            prediction = model.predict_match(
                home=row["home"],
                away=row["away"],
            )

            rows.append(
                {
                    "local": row["home"],
                    "visitante": row["away"],
                    "fecha": row.get("date", row.get("fecha")),

                    "fair_odds_home": prediction[
                        "fair_odds_home"
                    ],

                    "fair_odds_draw": prediction[
                        "fair_odds_draw"
                    ],

                    "fair_odds_away": prediction[
                        "fair_odds_away"
                    ],

                    "prob_home": prediction[
                        "prob_home"
                    ],

                    "prob_draw": prediction[
                        "prob_draw"
                    ],

                    "prob_away": prediction[
                        "prob_away"
                    ],

                    "home_lambda": prediction[
                        "home_lambda"
                    ],

                    "away_lambda": prediction[
                        "away_lambda"
                    ],
                }
            )

        predictions = pd.DataFrame(rows)

        # -----------------------------------------------------
        # 5. WPLAY
        # -----------------------------------------------------

        source = WplaySource(
            url=wplay_url,
            competition=competition,
        )

        market = source.get_odds(
            sport,
            competition,
        )

        # -----------------------------------------------------
        # 6. COMPARACIÓN
        # -----------------------------------------------------

        comparison = self.comparator.compare(
            predictions,
            market,
        )

        # -----------------------------------------------------
        # PROTECCIÓN CONTRA DATAFRAME VACÍO
        # -----------------------------------------------------

        if comparison.empty:

            comparison = self._empty_comparison()

            print()
            print(
                "  AVISO: no hubo coincidencias "
                "entre modelo y Wplay."
            )

            print(
                "  VALUE DETECTADO: 0"
            )

            return {
                "run_id": run_id,
                "future": future,
                "predictions": predictions,
                "market": market,
                "comparison": comparison,
                "detected_alerts": comparison.copy(),
                "alerts": comparison.copy(),
                "model_is_new": model_is_new,
            }

        # -----------------------------------------------------
        # 7. DETECCIÓN DE VALUE
        # -----------------------------------------------------

        detected_alerts = self.detector.detect(
            comparison
        )

        # -----------------------------------------------------
        # 8. ALERTAS
        # -----------------------------------------------------
        #
        # IMPORTANTE:
        #
        # Aquí NO registramos apuestas.
        #
        # El sistema solamente detecta value.
        #
        # MorningJob envía la alerta por Telegram.
        #
        # La apuesta se registrará posteriormente cuando
        # el usuario decida invertir.
        #
        # -----------------------------------------------------

        alerts = detected_alerts.copy()

        # -----------------------------------------------------
        # 9. RESULTADO
        # -----------------------------------------------------

        return {
            "run_id": run_id,
            "future": future,
            "predictions": predictions,
            "market": market,
            "comparison": comparison,
            "detected_alerts": detected_alerts,
            "alerts": alerts,
            "model_is_new": model_is_new,
        }


# =============================================================
# PRUEBA DIRECTA
# =============================================================

if __name__ == "__main__":

    pipeline = AlertPipeline(
        min_edge=0.05,
        stake=10000.0,
    )

    result = pipeline.run(
        sport="football",
        competition="premier_league",
        season="2026-27",
        wplay_url=(
            "https://apuestas.wplay.co/es/"
            "PremierLeague"
        ),
    )

    print("=" * 60)
    print("PIPELINE DE ANÁLISIS")
    print("=" * 60)

    print(
        "RUN ID:",
        result["run_id"],
    )

    print(
        "MODELO NUEVO:",
        result["model_is_new"],
    )

    print(
        "PARTIDOS FUTUROS:",
        len(result["future"]),
    )

    print(
        "CUOTAS WPLAY:",
        len(result["market"]),
    )

    print(
        "COMPARACIONES:",
        len(result["comparison"]),
    )

    print(
        "VALUE DETECTADO:",
        len(result["detected_alerts"]),
    )

    print(
        "ALERTAS:",
        len(result["alerts"]),
    )

    if not result["alerts"].empty:

        print()

        print(
            result["alerts"].to_string(
                index=False
            )
        )

    print("=" * 60)