"""Когортно-компонентная демографическая модель."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class PopulationState:
    """Снимок состояния населения в конкретный год."""
    year: int
    males: np.ndarray    # shape (101,), возраст 0..100
    females: np.ndarray  # shape (101,)

    @property
    def total_males(self) -> float:
        return float(self.males.sum())

    @property
    def total_females(self) -> float:
        return float(self.females.sum())

    @property
    def total(self) -> float:
        return self.total_males + self.total_females

    @property
    def sex_ratio(self) -> float:
        """Мужчин на 100 женщин."""
        tf = self.total_females
        if tf == 0:
            return 0.0
        return self.total_males / tf * 100

    def median_age(self, sex: str = "both") -> float:
        """Медианный возраст (both / male / female)."""
        if sex == "male":
            counts = self.males
        elif sex == "female":
            counts = self.females
        else:
            counts = self.males + self.females

        total = counts.sum()
        if total == 0:
            return 0.0
        cumsum = np.cumsum(counts)
        idx = np.searchsorted(cumsum, total / 2)
        return float(min(idx, 100))

    def dependency_ratio(self) -> dict[str, float]:
        """Коэффициенты демографической нагрузки."""
        combined = self.males + self.females
        young = combined[:15].sum()
        working = combined[15:65].sum()
        old = combined[65:].sum()
        total_dep = young + old
        if working == 0:
            return {"young": 0.0, "old": 0.0, "total": 0.0}
        return {
            "young": young / working * 100,
            "old": old / working * 100,
            "total": total_dep / working * 100,
        }

    def age_groups_pct(self) -> dict[str, float]:
        """Доля возрастных групп (%)."""
        combined = self.males + self.females
        total = combined.sum()
        if total == 0:
            return {"0-14": 0.0, "15-64": 0.0, "65+": 0.0}
        return {
            "0-14":  combined[:15].sum() / total * 100,
            "15-64": combined[15:65].sum() / total * 100,
            "65+":   combined[65:].sum() / total * 100,
        }


@dataclass
class SimulationParams:
    """Параметры симуляции."""
    mortality_male: np.ndarray    # (101,) коэффициенты смертности мужчин
    mortality_female: np.ndarray  # (101,) коэффициенты смертности женщин
    birth_rate: float             # рождений на фертильную женщину в год
    fertility_start: int          # возраст начала фертильности
    fertility_end: int            # возраст конца фертильности
    sex_ratio_at_birth: float = 0.512              # фиксированная доля мальчиков
    sex_ratio_range: tuple[float, float] | None = None  # диапазон [min, max];
                                                        # если задан — каждый год
                                                        # семплируется случайно


class PopulationModel:
    """Когортно-компонентная модель населения."""

    def __init__(
        self,
        initial_males: np.ndarray,
        initial_females: np.ndarray,
        params: SimulationParams,
        start_year: int = 0,
    ):
        self.params = params
        self.start_year = start_year
        self._history: list[PopulationState] = []

        # Начальное состояние
        initial = PopulationState(
            year=start_year,
            males=initial_males.copy().astype(float),
            females=initial_females.copy().astype(float),
        )
        self._history.append(initial)

    @property
    def history(self) -> list[PopulationState]:
        return self._history

    @property
    def current(self) -> PopulationState:
        return self._history[-1]

    def step(self) -> PopulationState:
        """Симулирует один год и добавляет состояние в историю."""
        p = self.params
        prev = self.current

        # 1. Применяем смертность
        survivors_m = prev.males * (1.0 - p.mortality_male)
        survivors_f = prev.females * (1.0 - p.mortality_female)

        # 2. Стареем когорты (сдвиг на 1)
        new_m = np.zeros(101)
        new_f = np.zeros(101)

        new_m[1:101] = survivors_m[0:100]
        new_m[100] += survivors_m[100]   # терминальный когорт накапливается

        new_f[1:101] = survivors_f[0:100]
        new_f[100] += survivors_f[100]

        # 3. Рождения (из выживших женщин, а не из исходной популяции)
        fertile_women = survivors_f[p.fertility_start:p.fertility_end + 1].sum()
        total_births = fertile_women * p.birth_rate

        if p.sex_ratio_range is not None:
            ratio = np.random.uniform(p.sex_ratio_range[0], p.sex_ratio_range[1])
        else:
            ratio = p.sex_ratio_at_birth

        new_m[0] = total_births * ratio
        new_f[0] = total_births * (1.0 - ratio)

        state = PopulationState(
            year=prev.year + 1,
            males=new_m,
            females=new_f,
        )
        self._history.append(state)
        return state

    def simulate(self, years: int) -> list[PopulationState]:
        """Запускает симуляцию на заданное число лет."""
        for _ in range(years):
            self.step()
        return self._history
