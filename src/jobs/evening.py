from __future__ import annotations

from datetime import datetime

from src.tracking.settlement import SettlementManager
from src.tracking.bankroll import BankrollTracker
from src.tracking.portfolio import PortfolioTracker
from src.alerts.telegram import TelegramNotifier


class EveningJob:
    """
    Cierre automático del día.

    Flujo:

        resultados actualizados
                ↓
        SettlementManager
                ↓
        WIN / LOSS / VOID
                ↓
        P&L
                ↓
        BankrollTracker
                ↓
        PortfolioTracker
                ↓
        Telegram
    """

    def __init__(self):

        self.settlement = SettlementManager()

        self.bankroll = BankrollTracker()

        self.portfolio = PortfolioTracker(
            bankroll=self.bankroll
        )

        self.telegram = TelegramNotifier()

    def run(self):

        start = datetime.now().isoformat()

        print("=" * 70)
        print("EVENING JOB - CIERRE DEL SISTEMA")
        print("=" * 70)

        print(f"INICIO: {start}")
        print()

        # ==========================================================
        # 1. LIQUIDAR ENTRADAS
        # ==========================================================

        print("=" * 70)
        print("1. LIQUIDACIÓN DE ENTRADAS")
        print("=" * 70)

        settled = (
            self.settlement.settle_open_bets()
        )

        print(
            "ENTRADAS LIQUIDADAS:",
            len(settled),
        )

        # ==========================================================
        # 2. CALCULAR P&L DEL DÍA
        # ==========================================================

        pnl = 0.0

        if not settled.empty:

            pnl = (
                settled["pnl"]
                .astype(float)
                .sum()
            )

        pnl = round(
            float(pnl),
            2,
        )

        print(
            "P&L DEL DÍA:",
            pnl,
        )

        # ==========================================================
        # 3. ACTUALIZAR BANKROLL
        # ==========================================================

        print()
        print("=" * 70)
        print("2. ACTUALIZACIÓN DE BANKROLL")
        print("=" * 70)

        bankroll_result = (
            self.bankroll.register_day(
                pnl=pnl
            )
        )

        print(
            "CAPITAL INICIAL:",
            bankroll_result["capital_inicial"],
        )

        print(
            "RECARGA:",
            bankroll_result["recarga"],
        )

        print(
            "P&L:",
            bankroll_result["pnl"],
        )

        print(
            "CAPITAL FINAL:",
            bankroll_result["capital_final"],
        )

        # ==========================================================
        # 4. ESTADO DEL PORTAFOLIO
        # ==========================================================

        print()
        print("=" * 70)
        print("3. PORTAFOLIO")
        print("=" * 70)

        portfolio = (
            self.portfolio.status()
        )

        print(
            "CAPITAL TOTAL:",
            portfolio["capital_total"],
        )

        print(
            "CAPITAL COMPROMETIDO:",
            portfolio[
                "capital_comprometido"
            ],
        )

        print(
            "CAPITAL DISPONIBLE:",
            portfolio[
                "capital_disponible"
            ],
        )

        print(
            "ENTRADAS ABIERTAS:",
            portfolio[
                "entradas_abiertas"
            ],
        )

        # ==========================================================
        # 5. RESUMEN DE APUESTAS
        # ==========================================================

        summary = (
            self.portfolio.summary()
        )

        print()
        print("=" * 70)
        print("4. RESUMEN HISTÓRICO")
        print("=" * 70)

        print(
            "ENTRADAS:",
            summary["entradas"],
        )

        print(
            "ABIERTAS:",
            summary["abiertas"],
        )

        print(
            "LIQUIDADAS:",
            summary["liquidadas"],
        )

        print(
            "WINS:",
            summary["wins"],
        )

        print(
            "LOSSES:",
            summary["losses"],
        )

        print(
            "VOIDS:",
            summary["voids"],
        )

        print(
            "P&L ACUMULADO:",
            summary["pnl"],
        )

        # ==========================================================
        # 6. TELEGRAM
        # ==========================================================

        message = (
            "CIERRE DIARIO - SISTEMA DE APUESTAS\n\n"
            f"Entradas liquidadas: {len(settled)}\n"
            f"Wins: {summary['wins']}\n"
            f"Losses: {summary['losses']}\n"
            f"Voids: {summary['voids']}\n\n"
            f"P&L del día: {pnl:.2f}\n"
            f"P&L acumulado: {summary['pnl']:.2f}\n\n"
            f"Capital total: "
            f"{portfolio['capital_total']:.2f}\n"
            f"Capital comprometido: "
            f"{portfolio['capital_comprometido']:.2f}\n"
            f"Capital disponible: "
            f"{portfolio['capital_disponible']:.2f}\n"
            f"Entradas abiertas: "
            f"{portfolio['entradas_abiertas']}"
        )

        sent = self.telegram.send_message(
            message
        )

        print()
        print(
            "TELEGRAM:",
            sent,
        )

        if not sent:
            print(
                "TELEGRAM ERROR:",
                self.telegram.last_error,
            )

        # ==========================================================
        # 7. FIN
        # ==========================================================

        finish = datetime.now().isoformat()

        print()
        print("=" * 70)
        print("RESUMEN EVENING JOB")
        print("=" * 70)

        print(
            "LIQUIDADAS:",
            len(settled),
        )

        print(
            "P&L:",
            pnl,
        )

        print(
            "CAPITAL:",
            portfolio["capital_total"],
        )

        print(
            "DISPONIBLE:",
            portfolio["capital_disponible"],
        )

        print(
            "FIN:",
            finish,
        )

        print("=" * 70)


if __name__ == "__main__":

    job = EveningJob()

    job.run()