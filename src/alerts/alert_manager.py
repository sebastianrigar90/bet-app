from __future__ import annotations

import pandas as pd

from src.alerts.telegram import TelegramNotifier
from src.tracking.bets import BetTracker


class AlertManager:
    """
    Coordina:

    ValueDetector
        ↓
    capital disponible
        ↓
    BetTracker
        ↓
    Telegram
    """

    def __init__(
        self,
        min_edge: float = 0.05,
        stake: float = 0.0,
    ):
        self.min_edge = min_edge
        self.stake = stake

        self.telegram = TelegramNotifier()
        self.bet_tracker = BetTracker()

    def process(
        self,
        comparison: pd.DataFrame,
        run_id: str,
        sport: str,
        competition: str,
        season: str,
    ) -> pd.DataFrame:

        if comparison.empty:
            return pd.DataFrame()

        candidates = comparison[
            comparison["edge"]
            >= self.min_edge
        ].copy()

        if candidates.empty:
            return pd.DataFrame()

        alerts = []

        for _, row in candidates.iterrows():

            entry = pd.DataFrame([{
                "local": row["local"],
                "visitante": row["visitante"],
                "mercado": row["mercado"],
                "cuota_teorica": row[
                    "cuota_teorica"
                ],
                "cuota_real": row[
                    "cuota_real"
                ],
                "edge": row["edge"],
            }])

            registered = self.bet_tracker.register(
                entries=entry,
                run_id=run_id,
                stake=self.stake,
                sport=sport,
                competition=competition,
                season=season,
            )

            if registered.empty:
                continue

            sent = self.telegram.send_alert(
                local=row["local"],
                visitante=row["visitante"],
                mercado=row["mercado"],
                cuota_teorica=float(
                    row["cuota_teorica"]
                ),
                cuota_real=float(
                    row["cuota_real"]
                ),
                edge=float(
                    row["edge"]
                ),
            )

            alerts.append({
                "local": row["local"],
                "visitante": row["visitante"],
                "mercado": row["mercado"],
                "cuota_teorica": row[
                    "cuota_teorica"
                ],
                "cuota_real": row[
                    "cuota_real"
                ],
                "edge": row["edge"],
                "stake": self.stake,
                "telegram": sent,
            })

        return pd.DataFrame(alerts)

    def summary(self) -> dict:
        return self.bet_tracker.summary()