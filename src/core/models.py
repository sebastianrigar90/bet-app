from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Sport:
    """
    Deporte.
    
    Ejemplos:
    - football
    - basketball
    - tennis
    """

    code: str
    name: str


@dataclass
class Competition:
    """
    Competición deportiva.

    Ejemplos:
    - Serie A
    - Premier League
    - NBA
    - ATP
    """

    code: str
    name: str
    sport: str
    country: Optional[str] = None


@dataclass
class Season:
    """
    Temporada o periodo de una competición.

    Ejemplos:
    - 2025-26
    - 2026-27
    - 2026
    """

    code: str
    competition: str


@dataclass
class Participant:
    """
    Participante de un evento deportivo.

    Puede representar:
    - Equipo de fútbol
    - Equipo de baloncesto
    - Jugador de tenis
    - Selección nacional
    """

    name: str
    sport: str
    participant_type: str


@dataclass
class Event:
    """
    Evento deportivo genérico.

    Es deliberadamente independiente del deporte.
    """

    sport: str
    competition: str
    season: str

    date: datetime

    home: Optional[str] = None
    away: Optional[str] = None

    home_score: Optional[int] = None
    away_score: Optional[int] = None

    status: Optional[str] = None

    source: Optional[str] = None
    source_id: Optional[str] = None
    