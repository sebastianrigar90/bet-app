
from pathlib import Path

import pandas as pd
import yaml

from src.manager import DataManager
from src.tracking.run import RunTracker


class SportsUpdater:
    """
    Ejecuta la actualización de las competiciones configuradas
    en sources.yaml y registra el resultado de cada ejecución.
    """

    def __init__(
        self,
        config_path: str = "config/sources.yaml",
        team_config_path: str = "config/teams.yaml",
    ):
        self.config_path = Path(config_path)

        self.manager = DataManager(
            config_path=config_path,
            team_config_path=team_config_path,
        )

        self.run_tracker = RunTracker()

    def _load_competitions(self):
        """
        Obtiene las competiciones configuradas en sources.yaml.
        """

        with open(
            self.config_path,
            "r",
            encoding="utf-8",
        ) as file:
            config = yaml.safe_load(file)

        football = config.get("football", {})

        competitions = []

        for competition in football.keys():
            competitions.append(
                {
                    "sport": "football",
                    "competition": competition,
                }
            )

        return competitions

    @staticmethod
    def _get_season(competition: str) -> str:
        """
        Temporada actual configurada para cada competición.
        """

        seasons = {
            "premier_league": "2026-27",
            "primera_a_clausura": "2026",
            "serie_a": "2026-27",
            "ligue_1": "2026-27",
            "la_liga": "2026-27",
            "bundesliga": "2026-27",
            "liga_argentina": "2026",
            "brasileirao": "2026",
        }

        if competition not in seasons:
            raise ValueError(
                f"No existe temporada configurada para: {competition}"
            )

        return seasons[competition]

    def run(self):

        run_id = self.run_tracker.start_run()

        print("=" * 70)
        print("ACTUALIZACIÓN DE DATOS DEPORTIVOS")
        print("=" * 70)
        print(f"RUN ID: {run_id}")
        print()

        competitions = self._load_competitions()

        total_events = 0
        total_errors = 0

        for item in competitions:

            sport = item["sport"]
            competition = item["competition"]
            season = self._get_season(competition)

            print(
                f"[{competition}] "
                f"temporada={season}"
            )

            try:

                events = self.manager.get_events(
                    sport=sport,
                    competition=competition,
                    season=season,
                    save=True,
                )

                total_events += len(events)

                source = self.manager.router.get_last_source()
                errors = self.manager.router.get_last_errors()

                print(
                    f"  OK | eventos={len(events)} "
                    f"| fuente={source}"
                )

                if errors:
                    print(
                        f"  Avisos: {errors}"
                    )

            except Exception as exc:

                total_errors += 1

                print(
                    f"  ERROR: {exc}"
                )

        status = (
            "SUCCESS"
            if total_errors == 0
            else "COMPLETED_WITH_ERRORS"
        )

        self.run_tracker.register_run(
            run_id=run_id,
            status=status,
            competitions=len(competitions),
            events=total_events,
            errors=total_errors,
        )

        print()
        print("=" * 70)
        print("RESUMEN")
        print("=" * 70)
        print(f"RUN ID:        {run_id}")
        print(f"COMPETICIONES: {len(competitions)}")
        print(f"EVENTOS:       {total_events}")
        print(f"ERRORES:       {total_errors}")
        print(f"ESTADO:        {status}")
        print("=" * 70)


if __name__ == "__main__":
    updater = SportsUpdater()
    updater.run()