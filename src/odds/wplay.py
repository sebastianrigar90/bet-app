from __future__ import annotations

import re
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .base import OddsSource


class WplaySource(OddsSource):

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/153.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    }

    MONTHS = {
        "ene": 1, "feb": 2, "mar": 3, "abr": 4,
        "may": 5, "jun": 6, "jul": 7, "ago": 8,
        "sep": 9, "oct": 10, "nov": 11, "dic": 12,
    }

    def __init__(
        self,
        url: str,
        competition: str,
        timeout: int = 30,
    ):
        self.url = url
        self.competition = competition
        self.timeout = timeout
        self._last_error: Optional[str] = None

    @property
    def name(self) -> str:
        return "wplay"

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    # ==========================================================
    # HTTP
    # ==========================================================

    def _get_response(self):
        response = requests.get(
            self.url,
            headers=self.DEFAULT_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response

    def is_available(self) -> bool:
        self._last_error = None

        try:
            response = self._get_response()
            return response.status_code == 200
        except requests.RequestException as exc:
            self._last_error = str(exc)
            return False

    # ==========================================================
    # API PÚBLICA
    # ==========================================================

    def get_odds(
        self,
        sport: str,
        competition: str,
    ) -> pd.DataFrame:

        self._last_error = None

        if sport.lower() != "football":
            raise ValueError(
                "WplaySource actualmente soporta football."
            )

        if competition != self.competition:
            raise ValueError(
                f"Competición no soportada: {competition}"
            )

        try:
            response = self._get_response()
        except requests.RequestException as exc:
            self._last_error = str(exc)
            raise RuntimeError(
                f"Error consultando Wplay: {exc}"
            ) from exc

        return self._extract_events(response.text)

    # ==========================================================
    # EXTRACCIÓN
    # ==========================================================

    def _extract_events(
        self,
        html: str,
    ) -> pd.DataFrame:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        resultados = []
        vistos = set()

        # ------------------------------------------------------
        # ESTRUCTURA 1: Wplay en formato TR
        # ------------------------------------------------------
        # Es la estructura observada, entre otros, en Brasil.
        filas = soup.select(
            "tr.mkt.mkt_content.pager-item"
        )

        for fila in filas:

            evento = self._parse_match_row(fila)

            if evento is None:
                continue

            event_id = evento["event_id"]

            if event_id in vistos:
                continue

            vistos.add(event_id)
            resultados.append(evento)

        # ------------------------------------------------------
        # ESTRUCTURA 2: Wplay en formato DIV.table-row
        # ------------------------------------------------------
        # Primera A Colombia utiliza esta estructura.
        #
        # div.table-row.row-wrap.mkt.mkt_content.mkt-*.pager-item
        #     └── buttons name=add-to-slip
        #           class contiene ev-XXXXXXXX
        #
        # Cada partido tiene tres botones: local, empate, visitante.
        if not resultados:

            filas_colombia = soup.select(
                "div.table-row.mkt.mkt_content.pager-item"
            )

            for fila in filas_colombia:

                evento = self._parse_match_div_row(fila)

                if evento is None:
                    continue

                event_id = evento["event_id"]

                if event_id in vistos:
                    continue

                vistos.add(event_id)
                resultados.append(evento)

        if not resultados:
            raise RuntimeError(
                "Wplay respondió correctamente, "
                "pero no se encontraron partidos válidos."
            )

        df = pd.DataFrame(resultados)

        columnas = [
            "fecha",
            "hora",
            "local",
            "visitante",
            "cuota_local",
            "cuota_empate",
            "cuota_visita",
            "event_id",
            "source",
            "competition",
        ]

        df = df[columnas]

        df = df.drop_duplicates(
            subset=[
                "fecha",
                "hora",
                "local",
                "visitante",
            ]
        )

        df = df.sort_values(
            ["fecha", "hora"]
        ).reset_index(drop=True)

        return df

    # ==========================================================
    # PARSEAR FILA DIV DE WPLAY
    # ==========================================================

    def _parse_match_div_row(
        self,
        fila,
    ) -> Optional[dict]:

        botones = fila.select(
            'button[name="add-to-slip"]'
        )

        if not botones:
            return None

        # ------------------------------------------------------
        # EVENT ID
        # ------------------------------------------------------
        event_id = None

        for boton in botones:
            for clase in boton.get("class", []):
                match = re.fullmatch(
                    r"ev-(\d+)",
                    str(clase).strip(),
                )
                if match:
                    event_id = match.group(1)
                    break
            if event_id:
                break

        if not event_id:
            return None

        # ------------------------------------------------------
        # FECHA / HORA
        # ------------------------------------------------------
        texto_fila = fila.get_text(
            " ",
            strip=True,
        )

        match_fecha = re.search(
            r"(\d{1,2}:\d{2})\s+"
            r"(\d{1,2}\s+"
            r"(?:Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic))",
            texto_fila,
            re.IGNORECASE,
        )

        if not match_fecha:
            return None

        hora = match_fecha.group(1)
        fecha_texto = match_fecha.group(2)

        fecha = self._parse_date_text(
            fecha_texto
        )

        if fecha is None:
            return None

        # ------------------------------------------------------
        # SELECCIONES Y CUOTAS
        # ------------------------------------------------------
        selecciones = []

        for boton in botones:

            nombre = self._get_selection_name(
                boton
            )

            cuota = self._get_decimal_odd(
                boton
            )

            if (
                nombre is None
                or cuota is None
            ):
                continue

            selecciones.append(
                (nombre, cuota)
            )

        cuotas = self._extract_1x2(
            selecciones
        )

        if cuotas is None:
            return None

        # ------------------------------------------------------
        # EQUIPOS
        # ------------------------------------------------------
        equipos = self._get_teams(
            fila,
            selecciones,
        )

        if equipos is None:
            return None

        local, visitante = equipos

        if not local or not visitante:
            return None

        if (
            self._normalize_name(local)
            == self._normalize_name(visitante)
        ):
            return None

        cuota_local = cuotas[0]
        cuota_empate = cuotas[1]
        cuota_visita = cuotas[2]

        if not all(
            self._valid_odd(x)
            for x in (
                cuota_local,
                cuota_empate,
                cuota_visita,
            )
        ):
            return None

        return {
            "fecha": fecha,
            "hora": hora,
            "local": local,
            "visitante": visitante,
            "cuota_local": cuota_local,
            "cuota_empate": cuota_empate,
            "cuota_visita": cuota_visita,
            "event_id": event_id,
            "source": self.name,
            "competition": self.competition,
        }

    # ==========================================================
    # PARSEAR UNA FILA
    # ==========================================================

    def _parse_match_row(
        self,
        fila,
    ) -> Optional[dict]:

        # ------------------------------------------------------
        # EVENT ID
        # ------------------------------------------------------

        event_node = fila.select_one(
            "div.ev[data-ev_id]"
        )

        event_id = None

        if event_node is not None:
            event_id = str(
                event_node.get("data-ev_id", "")
            ).strip()

        if not event_id:
            enlace = fila.select_one(
                'a[href*="/es/e/"]'
            )

            if enlace is not None:
                match = re.search(
                    r"/es/e/(\d+)/",
                    enlace.get("href", ""),
                )

                if match:
                    event_id = match.group(1)

        if not event_id:
            return None

        # ------------------------------------------------------
        # FECHA / HORA
        # ------------------------------------------------------

        ev_node = fila.select_one(
            "div.ev"
        )

        if ev_node is None:
            return None

        time_node = ev_node.select_one(
            "span.time"
        )

        date_node = ev_node.select_one(
            "span.date"
        )

        if (
            time_node is None
            or date_node is None
        ):
            return None

        hora = time_node.get_text(
            " ",
            strip=True,
        )

        fecha_texto = date_node.get_text(
            " ",
            strip=True,
        )

        if not re.fullmatch(
            r"\d{1,2}:\d{2}",
            hora,
        ):
            return None

        fecha = self._parse_date_text(
            fecha_texto
        )

        if fecha is None:
            return None

        # ------------------------------------------------------
        # SELECCIONES Y CUOTAS
        # ------------------------------------------------------

        selecciones = []

        botones = fila.select(
            'button[name="add-to-slip"]'
        )

        for boton in botones:

            nombre = self._get_selection_name(
                boton
            )

            cuota = self._get_decimal_odd(
                boton
            )

            if (
                nombre is None
                or cuota is None
            ):
                continue

            selecciones.append(
                (
                    nombre,
                    cuota,
                )
            )

        # Debe existir exactamente:
        # local + empate + visitante
        cuotas = self._extract_1x2(
            selecciones
        )

        if cuotas is None:
            return None

        # ------------------------------------------------------
        # EQUIPOS
        # ------------------------------------------------------

        equipos = self._get_teams(
            fila,
            selecciones,
        )

        if equipos is None:
            return None

        local, visitante = equipos

        if not local or not visitante:
            return None

        if (
            self._normalize_name(local)
            == self._normalize_name(visitante)
        ):
            return None

        cuota_local = cuotas[0]
        cuota_empate = cuotas[1]
        cuota_visita = cuotas[2]

        if not all(
            self._valid_odd(x)
            for x in (
                cuota_local,
                cuota_empate,
                cuota_visita,
            )
        ):
            return None

        return {
            "fecha": fecha,
            "hora": hora,
            "local": local,
            "visitante": visitante,
            "cuota_local": cuota_local,
            "cuota_empate": cuota_empate,
            "cuota_visita": cuota_visita,
            "event_id": event_id,
            "source": self.name,
            "competition": self.competition,
        }

    # ==========================================================
    # EQUIPOS
    # ==========================================================

    @staticmethod
    def _get_teams(
        fila,
        selecciones,
    ) -> Optional[tuple[str, str]]:

        # ------------------------------------------------------
        # MÉTODO PRINCIPAL:
        # usar directamente las dos selecciones del mercado.
        #
        # Esto evita depender del slug del enlace del evento,
        # que en algunas páginas de Wplay puede venir URL-encoded
        # o contener caracteres de control.
        # ------------------------------------------------------

        equipos = []

        for nombre, _ in selecciones:

            nombre_limpio = WplaySource._clean_team_name(
                nombre
            )

            nombre_normalizado = WplaySource._normalize_name(
                nombre_limpio
            )

            # Wplay puede presentar temporalmente una selección
            # placeholder "-". Nunca debe convertirse en equipo.
            if nombre_normalizado in {
                "",
                "-",
                "empate",
            }:
                continue

            equipos.append(nombre_limpio)

        if len(equipos) == 2:
            if any(
                self_name == "-"
                for self_name in equipos
            ):
                return None

            return (
                equipos[0],
                equipos[1],
            )

        # ------------------------------------------------------
        # FALLBACK:
        # obtener los equipos desde el slug del evento.
        # ------------------------------------------------------

        enlace = fila.select_one(
            'a[href*="/es/e/"]'
        )

        if enlace is not None:

            href = enlace.get(
                "href",
                "",
            )

            match = re.search(
                r"/es/e/\d+/([^?#]+)",
                href,
            )

            if match:

                slug = match.group(1)

                equipos_slug = WplaySource._split_event_title(
                    slug
                )

                if equipos_slug is not None:
                    return equipos_slug

        return None

    @staticmethod
    def _split_event_title(
        title: str,
    ) -> Optional[tuple[str, str]]:

        if not title:
            return None

        title = str(title).strip()

        # El slug de Wplay usa guiones.
        # Los convertimos a espacios antes del split.
        title = re.sub(
            r"[-_]+",
            " ",
            title,
        )

        title = re.sub(
            r"\s+",
            " ",
            title,
        ).strip()

        match = re.match(
            r"^(.*?)\s+v(?:s\.?)?\s+(.*?)$",
            title,
            re.IGNORECASE,
        )

        if not match:
            return None

        local = WplaySource._clean_team_name(
            match.group(1)
        )

        visitante = WplaySource._clean_team_name(
            match.group(2)
        )

        if (
            not local
            or not visitante
            or local == "-"
            or visitante == "-"
        ):
            return None

        return (
            local,
            visitante,
        )

    # ==========================================================
    # NOMBRES DE SELECCIONES
    # ==========================================================

    @staticmethod
    def _get_selection_name(
        boton,
    ) -> Optional[str]:

        # Local / visitante
        node = boton.select_one(
            ".seln-name"
        )

        # Empate
        if node is None:
            node = boton.select_one(
                ".seln-draw-label"
            )

        if node is None:

            title = str(
                boton.get("title", "")
            ).strip()

            if not title:
                return None

            return WplaySource._clean_team_name(
                title
            )

        nombre = node.get_text(
            " ",
            strip=True,
        )

        if not nombre:
            return None

        return WplaySource._clean_team_name(
            nombre
        )

    # ==========================================================
    # CUOTA DECIMAL
    # ==========================================================

    @staticmethod
    def _get_decimal_odd(
        boton,
    ) -> Optional[float]:

        node = boton.select_one(
            ".price.dec"
        )

        if node is None:
            return None

        texto = node.get_text(
            " ",
            strip=True,
        )

        match = re.search(
            r"\b\d+(?:\.\d+)?\b",
            texto,
        )

        if not match:
            return None

        try:
            return float(
                match.group(0)
            )
        except ValueError:
            return None

    # ==========================================================
    # MAPEO 1X2
    # ==========================================================

    @staticmethod
    def _extract_1x2(
        selecciones,
    ) -> Optional[tuple[float, float, float]]:

        if len(selecciones) != 3:
            return None

        empate = None
        otros = []

        for nombre, cuota in selecciones:

            if (
                WplaySource._normalize_name(nombre)
                == "empate"
            ):
                empate = cuota
            else:
                otros.append(
                    (
                        nombre,
                        cuota,
                    )
                )

        if empate is None:
            return None

        if len(otros) != 2:
            return None

        return (
            float(otros[0][1]),
            float(empate),
            float(otros[1][1]),
        )

    # ==========================================================
    # LIMPIEZA
    # ==========================================================

    @staticmethod
    def _clean_team_name(
        name: str,
    ) -> str:

        name = str(name)

        name = name.replace(
            "★",
            " ",
        )

        name = re.sub(
            r"\b\d{1,2}:\d{2}\b",
            " ",
            name,
        )

        name = re.sub(
            r"\b\d{1,2}\s+"
            r"(Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic)\b",
            " ",
            name,
            flags=re.IGNORECASE,
        )

        name = re.sub(
            r"\b\d+/\d+\b",
            " ",
            name,
        )

        name = re.sub(
            r"[+-]\d{2,4}\b",
            " ",
            name,
        )

        name = re.sub(
            r"\b\d+\.\d+\b",
            " ",
            name,
        )

        name = re.sub(
            r"\b\d+\b",
            " ",
            name,
        )

        name = name.replace(
            "*",
            " ",
        )

        name = re.sub(
            r"\s+",
            " ",
            name,
        ).strip()

        return name

    @staticmethod
    def _normalize_name(
        name: str,
    ) -> str:

        return WplaySource._clean_team_name(
            name
        ).casefold().strip()

    @staticmethod
    def _valid_odd(
        cuota: float,
    ) -> bool:

        try:
            cuota = float(cuota)
        except (
            TypeError,
            ValueError,
        ):
            return False

        return 1 < cuota < 100

    # ==========================================================
    # FECHA
    # ==========================================================

    @classmethod
    def _parse_date_text(
        cls,
        texto: str,
    ) -> Optional[pd.Timestamp]:

        if not texto:
            return None

        match = re.search(
            r"(\d{1,2})\s+"
            r"(Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic)",
            str(texto),
            re.IGNORECASE,
        )

        if not match:
            return None

        dia = int(
            match.group(1)
        )

        mes = cls.MONTHS.get(
            match.group(2).lower()[:3]
        )

        if mes is None:
            return None

        ahora = pd.Timestamp.now()

        try:
            fecha = pd.Timestamp(
                year=ahora.year,
                month=mes,
                day=dia,
            )
        except ValueError:
            return None

        # Ajuste para partidos de enero-marzo
        # que correspondan al siguiente año.
        if (
            fecha < ahora - pd.Timedelta(days=180)
            and mes <= 3
        ):
            try:
                fecha = pd.Timestamp(
                    year=ahora.year + 1,
                    month=mes,
                    day=dia,
                )
            except ValueError:
                return None

        return fecha
