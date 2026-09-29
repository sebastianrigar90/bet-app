from __future__ import annotations

import pandas as pd


class ValueDetector:
    """
    Detecta oportunidades cuando el edge supera
    un umbral configurable.

    No envía alertas.
    No ejecuta apuestas.
    Solo identifica entradas potenciales.
    """

    def __init__(
        self,
        min_edge: float = 0.05,
    ):
        self.min_edge = min_edge

    def detect(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        required_columns = {
            "local",
            "visitante",
            "fair_odds_home",
            "fair_odds_draw",
            "fair_odds_away",
            "cuota_local",
            "cuota_empate",
            "cuota_visita",
            "edge_local",
            "edge_empate",
            "edge_visitante",
        }

        missing = (
            required_columns
            - set(df.columns)
        )

        if missing:
            raise ValueError(
                f"Faltan columnas: {sorted(missing)}"
            )

        rows = []

        for _, row in df.iterrows():

            markets = [
                (
                    "LOCAL",
                    row["fair_odds_home"],
                    row["cuota_local"],
                    row["edge_local"],
                ),
                (
                    "EMPATE",
                    row["fair_odds_draw"],
                    row["cuota_empate"],
                    row["edge_empate"],
                ),
                (
                    "VISITANTE",
                    row["fair_odds_away"],
                    row["cuota_visita"],
                    row["edge_visitante"],
                ),
            ]

            for market, fair_odd, real_odd, edge in markets:

                if pd.isna(edge):
                    continue

                if edge < self.min_edge:
                    continue

                rows.append(
                    {
                        "local": row["local"],
                        "visitante": row["visitante"],
                        **({"fecha": row["fecha"]} if "fecha" in row.index else {}),
                        "mercado": market,
                        "cuota_teorica": fair_odd,
                        "cuota_real": real_odd,
                        "edge": edge,
                    }
                )

        result = pd.DataFrame(rows)

        if result.empty:
            return result

        return result.sort_values(
            "edge",
            ascending=False,
        ).reset_index(
            drop=True
        )