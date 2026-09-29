from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.tracking.bankroll import BankrollTracker
from src.tracking.bets import BetTracker


class PortfolioTracker:
    """
    Vista consolidada del capital y las entradas.

    No modifica bets.csv ni bankroll.csv.
    Calcula:

        capital total
        capital comprometido
        capital disponible
        entradas abiertas
    """

    def __init__(
        self,
        bankroll: BankrollTracker | None = None,
        bets: BetTracker | None = None,
    ):
        self.bankroll = (
            bankroll
            or BankrollTracker()
        )

        self.bets = (
            bets
            or BetTracker()
        )

    # ==========================================================
    # ESTADO ACTUAL
    # ==========================================================

    def status(self) -> dict:

        capital_total = (
            self.bankroll.current_capital()
        )

        bets = self.bets.load()

        if bets.empty:
            capital_comprometido = 0.0
            entradas_abiertas = 0
        else:
            open_bets = bets[
                bets["status"] == "OPEN"
            ].copy()

            capital_comprometido = pd.to_numeric(
                open_bets["stake"],
                errors="coerce",
            ).fillna(0).sum()

            entradas_abiertas = len(
                open_bets
            )

        capital_disponible = (
            capital_total
            - capital_comprometido
        )

        return {
            "capital_total": round(
                capital_total,
                2,
            ),
            "capital_comprometido": round(
                float(capital_comprometido),
                2,
            ),
            "capital_disponible": round(
                float(capital_disponible),
                2,
            ),
            "entradas_abiertas": (
                entradas_abiertas
            ),
        }

    # ==========================================================
    # VALIDAR STAKE
    # ==========================================================

    def can_open(
        self,
        stake: float,
    ) -> bool:

        status = self.status()

        return (
            float(stake)
            <= status["capital_disponible"]
        )

    # ==========================================================
    # RESUMEN
    # ==========================================================

    def summary(self) -> dict:

        status = self.status()
        bets_summary = self.bets.summary()

        return {
            **status,
            **bets_summary,
        }