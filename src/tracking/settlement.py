from __future__ import annotations

from pathlib import Path
import pandas as pd


class SettlementManager:
    """
    Liquida automáticamente las entradas abiertas
    cuando encuentra el resultado final del partido.
    """

    def __init__(
        self,
        bets_path: str = "data/historical/bets.csv",
        events_path: str = "data/processed",
    ):
        self.bets_path = Path(bets_path)
        self.events_path = Path(events_path)

    def settle_open_bets(self) -> pd.DataFrame:

        if not self.bets_path.exists():
            return pd.DataFrame()

        bets = pd.read_csv(
            self.bets_path,
            dtype=str,
        )

        if bets.empty:
            return bets

        open_mask = (
            bets["status"] == "OPEN"
        )

        if not open_mask.any():
            return bets

        settled = []

        for index in bets[
            open_mask
        ].index:

            bet = bets.loc[index]

            event = self._find_event(
                bet
            )

            if event is None:
                continue

            result = self._calculate_result(
                bet,
                event,
            )

            if result is None:
                continue

            pnl = self._calculate_pnl(
                bet,
                result,
            )

            bets.loc[
                index,
                "status"
            ] = "SETTLED"

            bets.loc[
                index,
                "result"
            ] = result

            bets.loc[
                index,
                "pnl"
            ] = pnl

            bets.loc[
                index,
                "settled_at"
            ] = pd.Timestamp.now().isoformat()

            settled.append(
                bets.loc[index].to_dict()
            )

        bets.to_csv(
            self.bets_path,
            index=False,
            encoding="utf-8-sig",
        )

        return pd.DataFrame(
            settled
        )

    # ==========================================================
    # BUSCAR PARTIDO
    # ==========================================================

    def _find_event(
        self,
        bet: pd.Series,
    ):

        sport = str(
            bet.get("sport", "")
        )

        competition = str(
            bet.get("competition", "")
        )

        season = str(
            bet.get("season", "")
        )

        event_file = (
            self.events_path
            / sport
            / competition
            / season
            / "events.csv"
        )

        if not event_file.exists():
            return None

        df = pd.read_csv(
            event_file,
            dtype=str,
        )

        if df.empty:
            return None

        local = self._normalize(
            bet.get("local")
        )

        visitante = self._normalize(
            bet.get("visitante")
        )

        df["_local"] = df[
            "home"
        ].apply(self._normalize)

        df["_visitante"] = df[
            "away"
        ].apply(self._normalize)

        matches = df[
            (df["_local"] == local)
            & (
                df["_visitante"]
                == visitante
            )
        ]

        if matches.empty:
            return None

        event = matches.iloc[0]

        status = str(
            event.get(
                "status",
                ""
            )
        ).lower()

        if status != "finished":
            return None

        if pd.isna(
            event.get("home_score")
        ) or pd.isna(
            event.get("away_score")
        ):
            return None

        return event

    # ==========================================================
    # RESULTADO
    # ==========================================================

    @staticmethod
    def _calculate_result(
        bet: pd.Series,
        event: pd.Series,
    ) -> str | None:

        home_score = float(
            event["home_score"]
        )

        away_score = float(
            event["away_score"]
        )

        market = str(
            bet["mercado"]
        ).upper().strip()

        if market == "LOCAL":

            return (
                "WIN"
                if home_score > away_score
                else "LOSS"
            )

        if market == "VISITANTE":

            return (
                "WIN"
                if away_score > home_score
                else "LOSS"
            )

        if market == "EMPATE":

            return (
                "WIN"
                if home_score == away_score
                else "LOSS"
            )

        return None

    # ==========================================================
    # P&L
    # ==========================================================

    @staticmethod
    def _calculate_pnl(
        bet: pd.Series,
        result: str,
    ) -> float:

        stake = float(
            bet["stake"]
        )

        odds = float(
            bet["cuota_real"]
        )

        if result == "WIN":
            return round(
                stake * (odds - 1),
                2,
            )

        if result == "LOSS":
            return round(
                -stake,
                2,
            )

        return 0.0

    # ==========================================================
    # NORMALIZACIÓN
    # ==========================================================

    @staticmethod
    def _normalize(
        value,
    ) -> str:

        if value is None:
            return ""

        return (
            str(value)
            .strip()
            .lower()
        )