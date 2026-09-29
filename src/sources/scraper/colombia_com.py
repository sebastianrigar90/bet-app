from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from ...core.interfaces import SportsDataSource
from ...core.models import Event


class ColombiaComSource(SportsDataSource):
    """
    Fuente de resultados deportivos de Colombia.com.

    Actualmente utilizada para la Liga BetPlay / FPC.

    Responsabilidades:
        1. Consultar la página web.
        2. Extraer los partidos.
        3. Convertirlos al modelo estándar Event.

    NO es responsable de:
        - homologar nombres de equipos;
        - validar datos;
        - guardar archivos.
    """

    URL = (
        "https://www.colombia.com/"
        "futbol/liga-colombiana/torneo/"
    )

    DEFAULT_TIMEOUT = 30

    MONTHS = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }

    STATUSES = {
        "Jugado",
        "Aplazado",
        "Por jugar",
        "En juego",
    }

    DATE_RE = re.compile(
        r"^(?:lunes|martes|miércoles|jueves|viernes|"
        r"sábado|domingo),?\s*"
        r"(\d{1,2})\s+"
        r"([A-Za-záéíóúñ]+)\s+"
        r"(\d{4})$",
        re.IGNORECASE,
    )

    ROUND_RE = re.compile(
        r"^Fecha\s+(\d+)$",
        re.IGNORECASE,
    )

    TIME_RE = re.compile(
        r"^\d{1,2}:\d{2}\s*(?:AM|PM)?$",
        re.IGNORECASE,
    )

    SCORE_RE = re.compile(
        r"^(?:\(\d+\))?"
        r"(\d+)\s*-\s*(\d+)"
        r"(?:\(\d+\))?$"
    )

    def __init__(
        self,
        source_name: str = "colombia_com",
        url: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.source_name = source_name
        self.url = url or self.URL
        self.timeout = timeout

    # =========================================================
    # PROPIEDADES
    # =========================================================

    @property
    def name(self) -> str:
        return self.source_name

    # =========================================================
    # DISPONIBILIDAD
    # =========================================================

    def is_available(self) -> bool:
        try:

            response = requests.get(
                self.url,
                headers=self._headers(),
                timeout=self.timeout,
            )

            return response.ok

        except requests.RequestException:

            return False

    # =========================================================
    # OBTENER EVENTOS
    # =========================================================

    def get_events(
        self,
        sport: str,
        competition: str,
        season: str,
    ) -> List[Event]:

        html = self._download_page()

        lines = self._html_to_lines(
            html
        )

        records = self._extract_matches(
            lines=lines,
            sport=sport,
            competition=competition,
            season=season,
        )

        return records

    # =========================================================
    # HEADERS
    # =========================================================

    @staticmethod
    def _headers() -> dict:

        return {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/139.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "*/*;q=0.8"
            ),
            "Accept-Language": (
                "es-CO,es;q=0.9,en;q=0.8"
            ),
        }

    # =========================================================
    # DESCARGAR HTML
    # =========================================================

    def _download_page(self) -> str:

        response = requests.get(
            self.url,
            headers=self._headers(),
            timeout=self.timeout,
        )

        response.raise_for_status()

        return response.text

    # =========================================================
    # HTML → TEXTO
    # =========================================================

    @staticmethod
    def _html_to_lines(
        html: str,
    ) -> List[str]:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        text = soup.get_text("\n")

        lines = [
            re.sub(
                r"\s+",
                " ",
                line,
            ).strip()
            for line in text.splitlines()
        ]

        return [
            line
            for line in lines
            if line
        ]

    # =========================================================
    # EXTRAER PARTIDOS
    # =========================================================

    def _extract_matches(
        self,
        lines: List[str],
        sport: str,
        competition: str,
        season: str,
    ) -> List[Event]:

        events = []

        current_round = None
        current_date = None
        active_tournament = False

        i = 0

        while i < len(lines):

            line = lines[i]

            # -------------------------------------------------
            # TORNEOS
            # -------------------------------------------------

            if "TORNEO CLAUSURA" in line.upper():

                active_tournament = True

                i += 1
                continue

            if "TORNEO APERTURA" in line.upper():

                active_tournament = False

                i += 1
                continue

            if not active_tournament:

                i += 1
                continue

            # -------------------------------------------------
            # JORNADA
            # -------------------------------------------------

            match_round = self.ROUND_RE.match(
                line
            )

            if match_round:

                current_round = int(
                    match_round.group(1)
                )

                i += 1
                continue

            # -------------------------------------------------
            # FECHA
            # -------------------------------------------------

            parsed_date = self._parse_spanish_date(
                line
            )

            if parsed_date is not None:

                current_date = parsed_date

                i += 1
                continue

            # -------------------------------------------------
            # MARCADORES
            # -------------------------------------------------

            score_match = self.SCORE_RE.match(
                line
            )

            if (
                score_match
                and i >= 1
                and i + 1 < len(lines)
            ):

                home_team = lines[i - 1]
                away_team = lines[i + 1]

                if (
                    self._is_invalid_team(home_team)
                    or self._is_invalid_team(away_team)
                ):

                    i += 1
                    continue

                status = (
                    lines[i + 2]
                    if i + 2 < len(lines)
                    else "Jugado"
                )

                if status not in self.STATUSES:

                    status = "Jugado"

                goals_home, goals_away = map(
                    int,
                    score_match.groups(),
                )

                event = self._build_event(
                    sport=sport,
                    competition=competition,
                    season=season,
                    current_round=current_round,
                    current_date=current_date,
                    home=home_team,
                    away=away_team,
                    home_score=goals_home,
                    away_score=goals_away,
                    status=status,
                )

                events.append(event)

                i += 3
                continue

            # -------------------------------------------------
            # PARTIDOS CON HORA
            # -------------------------------------------------

            if self.TIME_RE.match(line):

                # =================================================
                # 1. PARTIDO APLAZADO
                # =================================================

                postponed_match = (
                    self._find_postponed_match(
                        lines=lines,
                        time_index=i,
                    )
                )

                if postponed_match is not None:

                    (
                        postponed_home,
                        postponed_away,
                        postponed_date,
                        consumed_index,
                    ) = postponed_match

                    event = self._build_event(
                        sport=sport,
                        competition=competition,
                        season=season,
                        current_round=current_round,
                        current_date=postponed_date,
                        home=postponed_home,
                        away=postponed_away,
                        home_score=None,
                        away_score=None,
                        status="Aplazado",
                    )

                    events.append(event)

                    i = consumed_index + 1

                    continue

                # =================================================
                # 2. PLACEHOLDER
                # =================================================

                placeholder_match = (
                    self._find_placeholder_match(
                        lines=lines,
                        time_index=i,
                    )
                )

                if placeholder_match is not None:

                    (
                        home_team,
                        away_team,
                        home_score,
                        away_score,
                        status,
                        consumed_index,
                    ) = placeholder_match

                    status = self._resolve_status(
                        status=status,
                        match_date=current_date,
                        match_time=line,
                        home_score=home_score,
                        away_score=away_score,
                    )

                    if status != "Jugado":
                        home_score = None
                        away_score = None

                    event = self._build_event(
                        sport=sport,
                        competition=competition,
                        season=season,
                        current_round=current_round,
                        current_date=current_date,
                        home=home_team,
                        away=away_team,
                        home_score=home_score,
                        away_score=away_score,
                        status=status,
                    )

                    events.append(event)

                    i = consumed_index + 1

                    continue

                # =================================================
                # 3. PARTIDO FUTURO
                # =================================================

                future_match = (
                    self._find_future_match(
                        lines=lines,
                        time_index=i,
                    )
                )

                if future_match is not None:

                    (
                        home_team,
                        away_team,
                        status,
                        consumed_index,
                    ) = future_match

                    status = self._resolve_status(
                        status=status,
                        match_date=current_date,
                        match_time=line,
                        home_score=None,
                        away_score=None,
                    )

                    event = self._build_event(
                        sport=sport,
                        competition=competition,
                        season=season,
                        current_round=current_round,
                        current_date=current_date,
                        home=home_team,
                        away=away_team,
                        home_score=None,
                        away_score=None,
                        status=status,
                    )

                    events.append(event)

                    i = consumed_index + 1

                    continue

            i += 1

        return events

    # =========================================================
    # PARTIDOS APLAZADOS
    # =========================================================

    def _find_postponed_match(
        self,
        lines: List[str],
        time_index: int,
    ):
        """
        Detecta:

            hora
            local
            alias
            Aplazado
            Fecha X
            fecha
            visitante
            alias
            ...
        """

        n = len(lines)

        if time_index + 3 >= n:
            return None

        home = lines[
            time_index + 1
        ].strip()

        if self._is_invalid_team(home):
            return None

        status = lines[
            time_index + 3
        ].strip()

        if status != "Aplazado":
            return None

        postponed_date = None
        date_index = None

        for j in range(
            time_index + 4,
            min(time_index + 10, n),
        ):

            parsed_date = (
                self._parse_spanish_date(
                    lines[j]
                )
            )

            if parsed_date is not None:

                postponed_date = parsed_date
                date_index = j

                break

        if date_index is None:
            return None

        away_index = date_index + 1

        if away_index >= n:
            return None

        away = lines[
            away_index
        ].strip()

        if self._is_invalid_team(away):
            return None

        return (
            home,
            away,
            postponed_date,
            away_index,
        )

    # =========================================================
    # PLACEHOLDER
    # =========================================================

    def _find_placeholder_match(
        self,
        lines: List[str],
        time_index: int,
    ):
        """
        Detecta:

            hora
            0
            -
            0
            visitante
            alias
            estado
        """

        n = len(lines)

        if time_index + 4 >= n:
            return None

        if not lines[
            time_index + 1
        ].isdigit():

            return None

        if lines[
            time_index + 2
        ] != "-":

            return None

        if not lines[
            time_index + 3
        ].isdigit():

            return None

        away_index = time_index + 4

        away_team = lines[
            away_index
        ].strip()

        if self._is_invalid_team(
            away_team
        ):

            return None

        status_index = None

        for j in range(
            away_index + 1,
            min(away_index + 6, n),
        ):

            candidate = lines[
                j
            ].strip()

            if candidate in self.STATUSES:

                status_index = j

                break

        if status_index is None:
            return None

        status = lines[
            status_index
        ]

        if time_index <= 0:
            return None

        home_team = lines[
            time_index - 1
        ].strip()

        if self._is_invalid_team(
            home_team
        ):

            return None

        home_score = int(lines[time_index + 1])
        away_score = int(lines[time_index + 3])

        return (
            home_team,
            away_team,
            home_score,
            away_score,
            status,
            status_index,
        )

    # =========================================================
    # FUTURO
    # =========================================================

    def _find_future_match(
        self,
        lines: List[str],
        time_index: int,
    ):
        """
        Detecta estructuras futuras normales.
        """

        n = len(lines)

        if time_index + 1 >= n:
            return None

        away_team = lines[
            time_index + 1
        ].strip()

        if self._is_invalid_team(
            away_team
        ):

            return None

        status_index = None

        for j in range(
            time_index + 2,
            min(time_index + 6, n),
        ):

            candidate = lines[
                j
            ].strip()

            if candidate in self.STATUSES:

                status_index = j

                break

        if status_index is None:
            return None

        status = lines[
            status_index
        ]

        if time_index <= 0:
            return None

        home_team = lines[
            time_index - 1
        ].strip()

        if self._is_invalid_team(
            home_team
        ):

            return None

        return (
            home_team,
            away_team,
            status,
            status_index,
        )

    # =========================================================
    # VALIDAR EQUIPO
    # =========================================================

    def _is_invalid_team(
        self,
        value: str,
    ) -> bool:
        """
        Valida que el texto pueda representar un equipo.

        IMPORTANTE:
        Este método NO es staticmethod porque necesita acceder
        a self.STATUSES.
        """

        if value is None:
            return True

        value = str(
            value
        ).strip()

        if not value:
            return True

        invalid_values = {
            "-",
            "--",
            "—",
            "–",
        }

        if value in invalid_values:
            return True

        if re.fullmatch(
            r"\d+",
            value,
        ):
            return True

        if value in self.STATUSES:
            return True

        if self.TIME_RE.match(value):
            return True

        return False

    # =========================================================
    # RESOLVER ESTADO
    # =========================================================

    @staticmethod
    def _resolve_status(
        status: str,
        match_date,
        match_time: str,
        home_score: Optional[int],
        away_score: Optional[int],
    ) -> str:

        if match_date is None:
            return status

        try:

            today = datetime.now().date()

            match_day = match_date.date()

            if match_day > today:
                return "Por jugar"

            if match_day < today:
                return status

            try:

                parsed_time = datetime.strptime(
                    match_time.strip(),
                    "%I:%M %p",
                ).time()

            except ValueError:

                try:

                    parsed_time = datetime.strptime(
                        match_time.strip(),
                        "%H:%M",
                    ).time()

                except ValueError:

                    return status

            now = datetime.now()

            if parsed_time > now.time():
                return "Por jugar"

        except (
            AttributeError,
            TypeError,
            ValueError,
        ):

            return status

        return status

    # =========================================================
    # CREAR EVENT
    # =========================================================

    def _build_event(
        self,
        sport: str,
        competition: str,
        season: str,
        current_round: Optional[int],
        current_date,
        home: str,
        away: str,
        home_score: Optional[int],
        away_score: Optional[int],
        status: str,
    ) -> Event:

        date = current_date

        if date is None:

            date = datetime(
                int(season),
                1,
                1,
            )

        return Event(
            sport=sport,
            competition=competition,
            season=str(season),
            date=date,
            home=home,
            away=away,
            home_score=home_score,
            away_score=away_score,
            status=self._normalize_status(
                status
            ),
            source=self.source_name,
            source_id=self._build_source_id(
                current_round=current_round,
                date=date,
                home=home,
                away=away,
            ),
        )

    # =========================================================
    # FECHAS
    # =========================================================

    @classmethod
    def _parse_spanish_date(
        cls,
        line: str,
    ):
        """
        Convierte:

            Jueves, 30 Julio 2026

        a datetime.
        """

        line = line.strip()

        match = cls.DATE_RE.match(
            line
        )

        if not match:
            return None

        day, month_name, year = (
            match.groups()
        )

        month = cls.MONTHS.get(
            month_name.lower()
        )

        if month is None:
            return None

        try:

            return datetime(
                int(year),
                month,
                int(day),
            )

        except ValueError:

            return None

    # =========================================================
    # ESTADOS
    # =========================================================

    @staticmethod
    def _normalize_status(
        status: str,
    ) -> str:

        status = (
            str(status)
            .strip()
            .lower()
        )

        status_map = {
            "jugado": "finished",
            "por jugar": "scheduled",
            "aplazado": "postponed",
            "en juego": "live",
        }

        return status_map.get(
            status,
            status,
        )

    # =========================================================
    # SOURCE ID
    # =========================================================

    @staticmethod
    def _build_source_id(
        current_round: Optional[int],
        date,
        home: str,
        away: str,
    ) -> str:

        date_key = (
            date.strftime("%Y%m%d")
            if date is not None
            else "unknown"
        )

        home_key = re.sub(
            r"[^a-z0-9]+",
            "",
            home.lower(),
        )

        away_key = re.sub(
            r"[^a-z0-9]+",
            "",
            away.lower(),
        )

        round_key = (
            str(current_round)
            if current_round is not None
            else "unknown"
        )

        return (
            f"{date_key}_"
            f"{round_key}_"
            f"{home_key}_"
            f"{away_key}"
        )