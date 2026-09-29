from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.normalization.teams import TeamNormalizer


class OddsComparator:
    """
    Compara cuotas teóricas del modelo contra cuotas reales.

    Antes del cruce, ambos orígenes pasan por TeamNormalizer.
    """

    def __init__(
        self,
        team_config_path: str = "config/teams.yaml",
    ):
        self.team_normalizer = TeamNormalizer(
            team_config_path
        )

    def compare(
        self,
        model_odds: pd.DataFrame,
        market_odds: pd.DataFrame,
    ) -> pd.DataFrame:

        required_model = {
            "local",
            "visitante",
            "fair_odds_home",
            "fair_odds_draw",
            "fair_odds_away",
        }

        required_market = {
            "local",
            "visitante",
            "cuota_local",
            "cuota_empate",
            "cuota_visita",
        }

        missing_model = (
            required_model
            - set(model_odds.columns)
        )

        missing_market = (
            required_market
            - set(market_odds.columns)
        )

        if missing_model:
            raise ValueError(
                f"Faltan columnas del modelo: "
                f"{sorted(missing_model)}"
            )

        if missing_market:
            raise ValueError(
                f"Faltan columnas del mercado: "
                f"{sorted(missing_market)}"
            )

        model = model_odds.copy()
        market = market_odds.copy()

        # --------------------------------------------------
        # NORMALIZAR EQUIPOS
        # --------------------------------------------------

        model["local_std"] = (
            model["local"]
            .apply(
                self.team_normalizer.normalize
            )
        )

        model["visitante_std"] = (
            model["visitante"]
            .apply(
                self.team_normalizer.normalize
            )
        )

        market["local_std"] = (
            market["local"]
            .apply(
                self.team_normalizer.normalize
            )
        )

        market["visitante_std"] = (
            market["visitante"]
            .apply(
                self.team_normalizer.normalize
            )
        )

        # --------------------------------------------------
        # CRUCE
        # --------------------------------------------------

        result = model.merge(
            market[
                [
                    "local_std",
                    "visitante_std",
                    "cuota_local",
                    "cuota_empate",
                    "cuota_visita",
                ]
            ],
            on=[
                "local_std",
                "visitante_std",
            ],
            how="inner",
        )

        if result.empty:
            return pd.DataFrame()

        # --------------------------------------------------
        # EDGE
        # --------------------------------------------------

        result["edge_local"] = (
            result["cuota_local"]
            / result["fair_odds_home"]
            - 1
        )

        result["edge_empate"] = (
            result["cuota_empate"]
            / result["fair_odds_draw"]
            - 1
        )

        result["edge_visitante"] = (
            result["cuota_visita"]
            / result["fair_odds_away"]
            - 1
        )

        # --------------------------------------------------
        # SALIDA
        # --------------------------------------------------

        columns = [
            "local",
            "visitante",
            * (["fecha"] if "fecha" in result.columns else []),
            "fair_odds_home",
            "fair_odds_draw",
            "fair_odds_away",
            "cuota_local",
            "cuota_empate",
            "cuota_visita",
            "edge_local",
            "edge_empate",
            "edge_visitante",
        ]

        return result[
            columns
        ].reset_index(
            drop=True
        )