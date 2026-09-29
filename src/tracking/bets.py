from __future__ import annotations

from datetime import datetime
from pathlib import Path
import uuid

import pandas as pd

from src.tracking.bankroll import BankrollTracker


class BetTracker:
    """
    Registro y control de entradas.

    Una entrada solo se registra si existe capital disponible
    suficiente para cubrir su stake.
    """

    COLUMNS = [
        "bet_id",
        "run_id",
        "detected_at",
        "sport",
        "competition",
        "season",
        "match_date",
        "local",
        "visitante",
        "mercado",
        "cuota_teorica",
        "cuota_real",
        "edge",
        "stake",
        "status",
        "result",
        "pnl",
        "settled_at",
    ]

    def __init__(
        self,
        base_path: str = "data/historical",
        bankroll: BankrollTracker | None = None,
    ):
        self.base_path = Path(base_path)

        self.base_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.file = (
            self.base_path / "bets.csv"
        )

        self.bankroll = (
            bankroll
            or BankrollTracker(
                base_path=base_path
            )
        )

    # ==========================================================
    # REGISTRAR ENTRADAS
    # ==========================================================

    def register(
        self,
        entries: pd.DataFrame,
        run_id: str,
        stake: float = 0.0,
        sport: str = "football",
        competition: str = "",
        season: str = "",
    ) -> pd.DataFrame:

        if entries.empty:
            return pd.DataFrame(
                columns=self.COLUMNS
            )

        stake = float(stake)

        if stake < 0:
            raise ValueError(
                "El stake no puede ser negativo."
            )

        existing = self._load()

        existing_keys = set()

        if not existing.empty:
            existing_keys = set(
                existing.apply(
                    self._entry_key,
                    axis=1,
                )
            )

        # ------------------------------------------------------
        # CAPITAL DISPONIBLE
        # ------------------------------------------------------

        capital_total = (
            self.bankroll.current_capital()
        )

        capital_comprometido = 0.0

        if not existing.empty:

            open_bets = existing[
                existing["status"] == "OPEN"
            ]

            capital_comprometido = (
                pd.to_numeric(
                    open_bets["stake"],
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )

        capital_disponible = (
            capital_total
            - capital_comprometido
        )

        rows = []

        # ------------------------------------------------------
        # REGISTRAR ENTRADAS
        # ------------------------------------------------------

        for _, row in entries.iterrows():

            record = {
                "bet_id": str(
                    uuid.uuid4()
                ),
                "run_id": run_id,
                "detected_at": datetime.now().isoformat(),
                "sport": sport,
                "competition": competition,
                "season": season,
                "match_date": row.get(
                    "match_date",
                    row.get("fecha"),
                ),
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
                "stake": stake,
                "status": "OPEN",
                "result": None,
                "pnl": None,
                "settled_at": None,
            }

            key = self._entry_key(
                pd.Series(record)
            )

            # Evitar duplicados
            if key in existing_keys:
                continue

            # No permitir sobreinversión
            if stake > capital_disponible:
                break

            rows.append(record)

            existing_keys.add(key)

            capital_disponible -= stake

        # ------------------------------------------------------
        # GUARDAR
        # ------------------------------------------------------

        if not rows:
            return pd.DataFrame(
                columns=self.COLUMNS
            )

        new_data = pd.DataFrame(
            rows,
            columns=self.COLUMNS,
        )

        if existing.empty:
            data = new_data
        else:
            data = pd.concat(
                [
                    existing,
                    new_data,
                ],
                ignore_index=True,
            )

        data.to_csv(
            self.file,
            index=False,
            encoding="utf-8-sig",
        )

        return new_data

    # ==========================================================
    # LIQUIDAR ENTRADA
    # ==========================================================

    def settle(
        self,
        bet_id: str,
        result: str,
    ) -> None:

        data = self._load()

        if data.empty:
            raise ValueError(
                "No existen entradas registradas."
            )

        result = result.upper().strip()

        if result not in {
            "WIN",
            "LOSS",
            "VOID",
        }:
            raise ValueError(
                "Resultado inválido. "
                "Use WIN, LOSS o VOID."
            )

        mask = (
            data["bet_id"].astype(str)
            == str(bet_id)
        )

        if not mask.any():
            raise ValueError(
                f"No existe bet_id: {bet_id}"
            )

        stake = pd.to_numeric(
            data.loc[
                mask,
                "stake",
            ],
            errors="coerce",
        ).fillna(0)

        odds = pd.to_numeric(
            data.loc[
                mask,
                "cuota_real",
            ],
            errors="coerce",
        ).fillna(0)

        if result == "WIN":

            pnl = (
                stake
                * (odds - 1)
            )

        elif result == "LOSS":

            pnl = -stake

        else:

            pnl = 0.0

        data.loc[
            mask,
            "status",
        ] = "SETTLED"

        data.loc[
            mask,
            "result",
        ] = result

        data.loc[
            mask,
            "pnl",
        ] = float(
            pnl.iloc[0]
        )

        data.loc[
            mask,
            "settled_at",
        ] = datetime.now().isoformat()

        data.to_csv(
            self.file,
            index=False,
            encoding="utf-8-sig",
        )

    # ==========================================================
    # CONSULTAR
    # ==========================================================

    def load(
        self,
    ) -> pd.DataFrame:

        return self._load()

    def summary(
        self,
    ) -> dict:

        data = self._load()

        if data.empty:

            return {
                "entradas": 0,
                "abiertas": 0,
                "liquidadas": 0,
                "wins": 0,
                "losses": 0,
                "voids": 0,
                "pnl": 0.0,
            }

        settled = data[
            data["status"] == "SETTLED"
        ]

        pnl = pd.to_numeric(
            settled["pnl"],
            errors="coerce",
        ).fillna(0)

        return {
            "entradas": len(data),
            "abiertas": int(
                (
                    data["status"]
                    == "OPEN"
                ).sum()
            ),
            "liquidadas": len(
                settled
            ),
            "wins": int(
                (
                    settled["result"]
                    == "WIN"
                ).sum()
            ),
            "losses": int(
                (
                    settled["result"]
                    == "LOSS"
                ).sum()
            ),
            "voids": int(
                (
                    settled["result"]
                    == "VOID"
                ).sum()
            ),
            "pnl": float(
                pnl.sum()
            ),
        }

    # ==========================================================
    # PRIVADOS
    # ==========================================================

    def _load(
        self,
    ) -> pd.DataFrame:

        if not self.file.exists():

            return pd.DataFrame(
                columns=self.COLUMNS
            )

        data = pd.read_csv(
            self.file,
            dtype=str,
        )

        for column in self.COLUMNS:

            if column not in data.columns:
                data[column] = None

        return data[
            self.COLUMNS
        ]

    @staticmethod
    def _entry_key(
        row: pd.Series,
    ):

        return (
            str(
                row.get(
                    "competition",
                    "",
                )
            )
            .strip()
            .casefold(),

            str(
                row.get(
                    "season",
                    "",
                )
            )
            .strip()
            .casefold(),

            str(
                row.get(
                    "local",
                    "",
                )
            )
            .strip()
            .casefold(),

            str(
                row.get(
                    "visitante",
                    "",
                )
            )
            .strip()
            .casefold(),

            str(
                row.get(
                    "mercado",
                    "",
                )
            )
            .strip()
            .casefold(),
        )