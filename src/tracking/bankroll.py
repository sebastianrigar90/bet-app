from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


class BankrollTracker:
    """
    Control histórico del capital.

    Modelo:

        capital anterior
        + recarga real
        + P&L
        = capital final

    No realiza recargas automáticas.
    """

    COLUMNS = [
        "date",
        "capital_inicial",
        "recarga",
        "pnl",
        "capital_final",
    ]

    def __init__(
        self,
        base_path: str = "data/historical",
    ):
        self.base_path = Path(base_path)

        self.base_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.file = (
            self.base_path / "bankroll.csv"
        )

    # ==========================================================
    # REGISTRAR DÍA
    # ==========================================================

    def register_day(
        self,
        pnl: float = 0.0,
        recharge: float = 0.0,
    ) -> dict:

        today = datetime.now().strftime(
            "%Y-%m-%d"
        )

        recharge = float(recharge)
        pnl = float(pnl)

        data = self._load()

        # Evitar registrar dos veces
        # el mismo día.
        if not data.empty:

            existing = data[
                data["date"].astype(str)
                == today
            ]

            if not existing.empty:

                return existing.iloc[
                    -1
                ].to_dict()

        # ------------------------------------------------------
        # CAPITAL INICIAL
        # ------------------------------------------------------

        if data.empty:

            capital_inicial = 0.0

        else:

            capital_inicial = float(
                data.iloc[-1][
                    "capital_final"
                ]
            )

        # ------------------------------------------------------
        # CAPITAL FINAL
        # ------------------------------------------------------

        capital_final = (
            capital_inicial
            + recharge
            + pnl
        )

        row = {
            "date": today,
            "capital_inicial": capital_inicial,
            "recarga": recharge,
            "pnl": pnl,
            "capital_final": capital_final,
        }

        new_data = pd.DataFrame(
            [row],
            columns=self.COLUMNS,
        )

        if data.empty:

            result = new_data

        else:

            result = pd.concat(
                [
                    data,
                    new_data,
                ],
                ignore_index=True,
            )

        result.to_csv(
            self.file,
            index=False,
            encoding="utf-8-sig",
        )

        return row

    # ==========================================================
    # CONSULTAR HISTÓRICO
    # ==========================================================

    def load(self) -> pd.DataFrame:

        return self._load()

    # ==========================================================
    # CAPITAL ACTUAL
    # ==========================================================

    def current_capital(self) -> float:

        data = self._load()

        if data.empty:

            return 0.0

        return float(
            data.iloc[-1][
                "capital_final"
            ]
        )

    # ==========================================================
    # PRIVADO
    # ==========================================================

    def _load(self) -> pd.DataFrame:

        if not self.file.exists():

            return pd.DataFrame(
                columns=self.COLUMNS
            )

        data = pd.read_csv(
            self.file
        )

        for column in self.COLUMNS:

            if column not in data.columns:

                data[column] = None

        return data[
            self.COLUMNS
        ]