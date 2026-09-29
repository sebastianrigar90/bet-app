
from __future__ import annotations

import numpy as np
import pandas as pd

from scipy.optimize import minimize
from scipy.stats import poisson


class PoissonModel:
    """
    Modelo Poisson para estimar:

    - Fuerza ofensiva
    - Fuerza defensiva
    - Ventaja de local
    - Goles esperados
    - Probabilidades 1X2
    - Cuotas teóricas 1X2

    Las probabilidades 1X2 se calculan utilizando una
    matriz de goles con rango dinámico para reducir
    la pérdida de masa por truncamiento.
    """

    def __init__(
        self,
        random_starts: int = 20,
        random_seed: int = 0,
        max_goals: int = 10,
        tail_tolerance: float = 1e-12,
        max_goal_limit: int = 1000,
    ):
        self.random_starts = random_starts
        self.random_seed = random_seed
        self.max_goals = max_goals
        self.tail_tolerance = tail_tolerance
        self.max_goal_limit = max_goal_limit

        self.team_params = None
        self.home_advantage = None
        self.mean_goals = None
        self.objective = None

    def __setstate__(self, state):
        """Compatibilidad con modelos serializados por versiones anteriores."""
        self.__dict__.update(state)
        self.__dict__.setdefault("tail_tolerance", 1e-12)
        self.__dict__.setdefault("max_goal_limit", 1000)

    # ---------------------------------------------------------
    # MEDIA DE GOLES
    # ---------------------------------------------------------

    @staticmethod
    def _calculate_mean_goals(
        matches: pd.DataFrame,
    ) -> float:

        home = matches["home_score"]
        away = matches["away_score"]

        goals = pd.concat(
            [home, away],
            ignore_index=True,
        )

        mean_goals = float(goals.mean())

        if (
            not np.isfinite(mean_goals)
            or mean_goals <= 0
        ):
            raise ValueError(
                "La media de goles debe ser positiva "
                "y finita."
            )

        return mean_goals

    # ---------------------------------------------------------
    # GOLES ESPERADOS
    # ---------------------------------------------------------

    def _expected_goals(
        self,
        matches: pd.DataFrame,
        team_params: pd.DataFrame,
        home_advantage: float,
        mean_goals: float,
    ) -> pd.DataFrame:

        params = team_params.set_index("team")

        home_attack = matches["home"].map(
            params["attack"]
        )

        away_attack = matches["away"].map(
            params["attack"]
        )

        home_defense = matches["home"].map(
            params["defense"]
        )

        away_defense = matches["away"].map(
            params["defense"]
        )

        result = matches.copy()

        result["home_lambda"] = (
            mean_goals
            * home_attack
            * away_defense
            * home_advantage
        )

        result["away_lambda"] = (
            mean_goals
            * away_attack
            * home_defense
            / home_advantage
        )

        home_score = result["home_score"]
        away_score = result["away_score"]

        result["error"] = (
            (home_score - result["home_lambda"]) ** 2
            + (away_score - result["away_lambda"]) ** 2
        )

        return result

    # ---------------------------------------------------------
    # FUNCIÓN OBJETIVO
    # ---------------------------------------------------------

    def _objective(
        self,
        x: np.ndarray,
        matches: pd.DataFrame,
        teams: list[str],
        mean_goals: float,
    ) -> float:

        n = len(teams)

        attack = x[:n]
        defense = x[n:2 * n]
        home_advantage = x[2 * n]

        params = pd.DataFrame(
            {
                "team": teams,
                "attack": attack,
                "defense": defense,
            }
        )

        result = self._expected_goals(
            matches=matches,
            team_params=params,
            home_advantage=home_advantage,
            mean_goals=mean_goals,
        )

        return float(
            result["error"].sum()
        )

    # ---------------------------------------------------------
    # ENTRENAMIENTO
    # ---------------------------------------------------------

    def fit(
        self,
        matches: pd.DataFrame,
    ) -> "PoissonModel":

        required = {
            "home",
            "away",
            "home_score",
            "away_score",
        }

        missing = required - set(matches.columns)

        if missing:
            raise ValueError(
                f"Faltan columnas requeridas: "
                f"{sorted(missing)}"
            )

        data = matches.copy()

        data = data.dropna(
            subset=[
                "home",
                "away",
                "home_score",
                "away_score",
            ]
        )

        data["home_score"] = pd.to_numeric(
            data["home_score"],
            errors="coerce",
        )

        data["away_score"] = pd.to_numeric(
            data["away_score"],
            errors="coerce",
        )

        data = data.dropna(
            subset=[
                "home_score",
                "away_score",
            ]
        )

        data = data[
            (data["home_score"] >= 0)
            & (data["away_score"] >= 0)
        ].copy()

        if data.empty:
            raise ValueError(
                "No existen partidos válidos para entrenar."
            )

        teams = sorted(
            set(data["home"])
            | set(data["away"])
        )

        if not teams:
            raise ValueError(
                "No se encontraron equipos."
            )

        mean_goals = self._calculate_mean_goals(
            data
        )

        n = len(teams)

        x0 = np.r_[
            np.ones(n),
            np.ones(n),
            1.0,
        ]

        constraints = [
            {
                "type": "eq",
                "fun": lambda x: (
                    np.mean(x[:n]) - 1.0
                ),
            },
            {
                "type": "eq",
                "fun": lambda x: (
                    np.mean(x[n:2 * n]) - 1.0
                ),
            },
        ]

        bounds = (
            [(1e-6, 10.0)] * (2 * n)
            + [(0.05, 5.0)]
        )

        starts = [x0]

        rng = np.random.default_rng(
            self.random_seed
        )

        for _ in range(
            max(0, self.random_starts - 1)
        ):

            attack = np.clip(
                rng.normal(1.0, 0.20, n),
                0.05,
                3.0,
            )

            defense = np.clip(
                rng.normal(1.0, 0.20, n),
                0.05,
                3.0,
            )

            attack /= attack.mean()
            defense /= defense.mean()

            home_advantage = float(
                np.clip(
                    rng.normal(1.0, 0.10),
                    0.05,
                    4.9,
                )
            )

            starts.append(
                np.r_[
                    attack,
                    defense,
                    home_advantage,
                ]
            )

        best = None
        successful_results = []

        for start in starts:

            result = minimize(
                self._objective,
                start,
                args=(
                    data,
                    teams,
                    mean_goals,
                ),
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={
                    "ftol": 1e-9,
                    "maxiter": 3000,
                    "disp": False,
                },
            )

            if (
                result.success
                and np.isfinite(result.fun)
                and np.all(np.isfinite(result.x))
            ):
                successful_results.append(result)

        if successful_results:
            best = min(
                successful_results,
                key=lambda result: result.fun,
            )

        else:
            raise RuntimeError(
                "Ninguna inicialización del optimizador "
                "convergió correctamente. No se guardó "
                "una solución fallida."
            )

        x = best.x

        self.team_params = pd.DataFrame(
            {
                "team": teams,
                "attack": x[:n],
                "defense": x[n:2 * n],
            }
        )

        self.home_advantage = float(
            x[2 * n]
        )

        self.mean_goals = mean_goals
        self.objective = float(
            best.fun
        )

        return self

    # ---------------------------------------------------------
    # RANGO DINÁMICO DE GOLES
    # ---------------------------------------------------------

    def _get_goal_range(
        self,
        home_lambda: float,
        away_lambda: float,
    ) -> np.ndarray:
        """
        Determina el máximo de goles requerido para cubrir
        la mayor parte de ambas distribuciones.

        max_goals se mantiene como mínimo configurable.
        El rango se amplía si la cola de Poisson lo requiere.
        """

        lambdas = [
            home_lambda,
            away_lambda,
        ]

        if any(
            not np.isfinite(value)
            or value < 0
            for value in lambdas
        ):
            raise ValueError(
                "Los goles esperados deben ser valores "
                "finitos y no negativos."
            )

        required_max = self.max_goals

        for lam in lambdas:

            quantile = poisson.ppf(
                1 - self.tail_tolerance,
                lam,
            )

            if np.isfinite(quantile):
                required_max = max(
                    required_max,
                    int(np.ceil(quantile)),
                )

        if required_max > self.max_goal_limit:
            raise ValueError(
                "El rango de goles requerido supera "
                f"el límite de seguridad "
                f"({self.max_goal_limit})."
            )

        return np.arange(
            required_max + 1
        )

    # ---------------------------------------------------------
    # PREDICCIÓN 1X2
    # ---------------------------------------------------------

    def predict_match(
        self,
        home: str,
        away: str,
    ) -> dict:

        if self.team_params is None:
            raise RuntimeError(
                "El modelo todavía no ha sido entrenado."
            )

        params = self.team_params.set_index(
            "team"
        )

        if home not in params.index:
            raise ValueError(
                f"Equipo local no encontrado: {home}"
            )

        if away not in params.index:
            raise ValueError(
                f"Equipo visitante no encontrado: {away}"
            )

        home_lambda = float(
            self.mean_goals
            * params.loc[home, "attack"]
            * params.loc[away, "defense"]
            * self.home_advantage
        )

        away_lambda = float(
            self.mean_goals
            * params.loc[away, "attack"]
            * params.loc[home, "defense"]
            / self.home_advantage
        )

        goals = self._get_goal_range(
            home_lambda,
            away_lambda,
        )

        home_probs = poisson.pmf(
            goals,
            home_lambda,
        )

        away_probs = poisson.pmf(
            goals,
            away_lambda,
        )

        matrix = np.outer(
            home_probs,
            away_probs,
        )

        # Masa de probabilidad cubierta por la matriz.
        covered_mass = float(
            matrix.sum()
        )

        # Probabilidad omitida por el truncamiento.
        omitted_mass = max(
            0.0,
            1.0 - covered_mass,
        )

        # Probabilidades 1X2 antes de normalizar.
        p_home_raw = float(
            np.tril(matrix, -1).sum()
        )

        p_draw_raw = float(
            np.trace(matrix)
        )

        p_away_raw = float(
            np.triu(matrix, 1).sum()
        )

        probabilities = np.array(
            [
                p_home_raw,
                p_draw_raw,
                p_away_raw,
            ],
            dtype=float,
        )

        probability_sum = float(
            probabilities.sum()
        )

        if (
            not np.isfinite(probability_sum)
            or probability_sum <= 0
        ):
            raise ValueError(
                "No fue posible calcular probabilidades "
                "1X2 válidas."
            )

        # Normalización para asegurar que las tres
        # probabilidades sumen exactamente 1.
        probabilities /= probability_sum

        p_home = float(probabilities[0])
        p_draw = float(probabilities[1])
        p_away = float(probabilities[2])

        return {
            "home": home,
            "away": away,
            "home_lambda": home_lambda,
            "away_lambda": away_lambda,
            "prob_home": p_home,
            "prob_draw": p_draw,
            "prob_away": p_away,
            "probability_sum": float(
                probabilities.sum()
            ),
            "covered_mass": covered_mass,
            "omitted_mass": omitted_mass,
            "goal_range_max": int(goals[-1]),
            "fair_odds_home": (
                1 / p_home
                if p_home > 0
                else np.inf
            ),
            "fair_odds_draw": (
                1 / p_draw
                if p_draw > 0
                else np.inf
            ),
            "fair_odds_away": (
                1 / p_away
                if p_away > 0
                else np.inf
            ),
        }