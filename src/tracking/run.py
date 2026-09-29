from datetime import datetime
from pathlib import Path

import pandas as pd


class RunTracker:
    """
    Gestiona la identificación y registro de cada ejecución
    del proceso de actualización.
    """

    def __init__(self, base_path: str = "data/historical"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.runs_file = self.base_path / "runs.csv"

    def start_run(self) -> str:
        """
        Crea un identificador único para la ejecución.
        """
        return datetime.now().strftime("RUN_%Y%m%d_%H%M%S")

    def register_run(
        self,
        run_id: str,
        status: str,
        competitions: int = 0,
        events: int = 0,
        changes: int = 0,
        errors: int = 0,
    ) -> None:
        """
        Registra el resultado de una ejecución.
        """

        row = {
            "run_id": run_id,
            "execution_date": datetime.now().isoformat(),
            "status": status,
            "competitions": competitions,
            "events": events,
            "changes": changes,
            "errors": errors,
        }

        new_data = pd.DataFrame([row])

        if self.runs_file.exists():
            old_data = pd.read_csv(self.runs_file)
            data = pd.concat(
                [old_data, new_data],
                ignore_index=True
            )
        else:
            data = new_data

        data.to_csv(
            self.runs_file,
            index=False,
            encoding="utf-8-sig"
        )