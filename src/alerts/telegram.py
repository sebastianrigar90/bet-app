from __future__ import annotations

import os
from typing import Optional

import requests


class TelegramNotifier:
    """
    Envío de alertas mediante Telegram.

    Variables de entorno:

        TELEGRAM_BOT_TOKEN
        TELEGRAM_CHAT_IDS

    Ejemplo:

        TELEGRAM_CHAT_IDS="123456789,987654321"
    """

    BASE_URL = "https://api.telegram.org"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_ids: Optional[str] = None,
        timeout: int = 15,
    ):
        self.bot_token = (
            bot_token
            or os.getenv("TELEGRAM_BOT_TOKEN")
        )

        raw_chat_ids = (
            chat_ids
            or os.getenv("TELEGRAM_CHAT_IDS")
            or ""
        )

        self.chat_ids = [
            chat_id.strip()
            for chat_id in raw_chat_ids.split(",")
            if chat_id.strip()
        ]

        self.timeout = timeout
        self._last_error = None

    @property
    def last_error(self):
        return self._last_error

    def is_configured(self) -> bool:
        return bool(
            self.bot_token
            and self.chat_ids
        )

    def send_message(
        self,
        message: str,
    ) -> bool:

        self._last_error = None

        if not self.is_configured():
            self._last_error = (
                "Telegram no está configurado. "
                "Faltan TELEGRAM_BOT_TOKEN "
                "o TELEGRAM_CHAT_IDS."
            )
            return False

        if not message:
            self._last_error = (
                "El mensaje de Telegram está vacío."
            )
            return False

        url = (
            f"{self.BASE_URL}/bot"
            f"{self.bot_token}/sendMessage"
        )

        success = True

        for chat_id in self.chat_ids:

            payload = {
                "chat_id": chat_id,
                "text": message,
            }

            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout,
                )

                response.raise_for_status()

                data = response.json()

                if not data.get("ok"):
                    self._last_error = (
                        f"Error en chat {chat_id}: "
                        f"{data}"
                    )
                    success = False

            except requests.RequestException as exc:
                self._last_error = (
                    f"Error en chat {chat_id}: "
                    f"{exc}"
                )
                success = False

        return success

    def send_alert(
        self,
        local: str,
        visitante: str,
        mercado: str,
        cuota_teorica: float,
        cuota_real: float,
        edge: float,
    ) -> bool:

        message = (
            "ALERTA DE VALOR\n\n"
            f"{local} vs {visitante}\n"
            f"Mercado: {mercado}\n"
            f"Cuota teórica: {cuota_teorica:.3f}\n"
            f"Cuota real: {cuota_real:.2f}\n"
            f"Edge: {edge:.2%}"
        )

        return self.send_message(message)