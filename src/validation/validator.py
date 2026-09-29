from typing import List, Tuple

from ..core.models import Event


class SportsDataValidator:
    """
    Valida eventos deportivos antes de almacenarlos.

    El objetivo es detectar registros incompletos,
    inconsistentes o potencialmente inválidos.
    """

    REQUIRED_FIELDS = [
        "sport",
        "competition",
        "season",
        "date",
        "home",
        "away",
        "status",
        "source",
    ]

    VALID_STATUSES = {
        "finished",
        "scheduled",
        "live",
        "postponed",
        "cancelled",
    }

    # =========================================================
    # VALIDAR LISTA
    # =========================================================

    def validate_events(
        self,
        events: List[Event],
    ) -> Tuple[List[Event], List[str]]:
        """
        Valida una lista de eventos.

        Returns
        -------
        valid_events:
            Eventos que cumplen las reglas.

        errors:
            Lista de errores encontrados.
        """

        valid_events = []
        errors = []

        for index, event in enumerate(events):

            event_errors = self.validate_event(
                event
            )

            if event_errors:

                errors.extend(
                    [
                        f"Evento {index}: {error}"
                        for error in event_errors
                    ]
                )

            else:

                valid_events.append(event)

        return valid_events, errors

    # =========================================================
    # VALIDAR EVENTO
    # =========================================================

    def validate_event(
        self,
        event: Event,
    ) -> List[str]:
        """
        Valida un evento individual.
        """

        errors = []

        # -----------------------------------------------------
        # Campos obligatorios
        # -----------------------------------------------------

        for field in self.REQUIRED_FIELDS:

            value = getattr(
                event,
                field,
                None,
            )

            if value is None:

                errors.append(
                    f"Campo obligatorio vacío: {field}"
                )

            elif isinstance(value, str) and not value.strip():

                errors.append(
                    f"Campo obligatorio vacío: {field}"
                )

        # -----------------------------------------------------
        # Home / Away
        # -----------------------------------------------------

        if (
            event.home
            and event.away
            and event.home == event.away
        ):

            errors.append(
                "Equipo local y visitante son iguales"
            )

        # -----------------------------------------------------
        # Estado
        # -----------------------------------------------------

        if event.status:

            if event.status not in self.VALID_STATUSES:

                errors.append(
                    f"Estado no válido: {event.status}"
                )

        # -----------------------------------------------------
        # Marcador
        # -----------------------------------------------------

        if event.status == "finished":

            if event.home_score is None:

                errors.append(
                    "Partido terminado sin goles_local"
                )

            if event.away_score is None:

                errors.append(
                    "Partido terminado sin goles_visitante"
                )

        # -----------------------------------------------------
        # Scores negativos
        # -----------------------------------------------------

        if event.home_score is not None:

            if event.home_score < 0:

                errors.append(
                    "home_score no puede ser negativo"
                )

        if event.away_score is not None:

            if event.away_score < 0:

                errors.append(
                    "away_score no puede ser negativo"
                )

        return errors