from pathlib import Path
import pandas as pd


class SnapshotManager:
    """
    Guarda una fotografía de los eventos obtenidos
    en cada ejecución.
    """

    def __init__(self, base_path: str = "data/snapshots"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        run_id: str,
        sport: str,
        competition: str,
        season: str,
        events,
    ) -> Path:
        """
        Guarda los eventos de una competición para una ejecución.
        """

        output_dir = (
            self.base_path
            / run_id
            / sport
            / competition
            / season
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        output_file = output_dir / "events.csv"

        rows = []

        for event in events:
            rows.append({
                "sport": event.sport,
                "competition": event.competition,
                "season": event.season,
                "date": event.date,
                "home": event.home,
                "away": event.away,
                "home_score": event.home_score,
                "away_score": event.away_score,
                "status": event.status,
                "source": event.source,
                "source_id": event.source_id,
            })

        df = pd.DataFrame(rows)

        df.to_csv(
            output_file,
            index=False,
            encoding="utf-8-sig"
        )

        return output_file