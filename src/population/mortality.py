"""Таблицы коэффициентов смертности по возрасту."""

from __future__ import annotations

import numpy as np
import yaml


def build_gompertz_table(base_rate: float = 0.01, male_multiplier: float = 1.08) -> tuple[np.ndarray, np.ndarray]:
    """Строит таблицы смертности по формуле Мейкхема-Гомперца.

    mu(x) = A + B * exp(C * x)

    Ключевой принцип: C (крутизна) фиксирован и НЕ масштабируется.
    base_rate задаёт уровень смертности в якорном возрасте (55 лет),
    а B вычисляется из него. Это сохраняет резкое падение численности
    на возрастах 80-100+, как в реальных данных.

    Результат при base_rate=0.01 (примерно мировые данные):
      возраст 30: ~0.2%   60: ~2.5%   80: ~8%   90: ~20%   100: ~46%

    Возвращает (mortality_male, mortality_female) — массивы формы (101,).
    """
    ages = np.arange(101, dtype=float)

    A = 0.0001   # фоновая смертность (несчастные случаи, не зависит от возраста)
    C = 0.090    # крутизна экспоненты — НЕ меняется при масштабировании.
                 # Подобрано по реальным данным:
                 #   выживших 65→95 лет: ~1.2% (реальность ~1.3%)
                 #   смертность в 80 лет: ~9%  в 90 лет: ~23%  в 95 лет: ~36%
                 # C=0.085 давало ~2.5% (мало умирало), C=0.10 давало ~0.14% (много).

    # Калибруем B так, чтобы mu(55) ≈ base_rate
    # B = (base_rate - A) / exp(C * 55)
    B = max(base_rate - A, 1e-9) / np.exp(C * 55)

    mu = A + B * np.exp(C * ages)

    # Повышенная младенческая смертность (возраст 0):
    # реалистично ~0.3% для развитых стран, выше для развивающихся
    mu[0] = max(mu[0], base_rate * 0.3)

    mu = np.clip(mu, 0.0, 0.95)

    mortality_female = mu.copy()
    mortality_male = np.clip(mu * male_multiplier, 0.0, 0.95)

    return mortality_male, mortality_female


def build_flat_table(rate: float, male_multiplier: float = 1.08) -> tuple[np.ndarray, np.ndarray]:
    """Одинаковый коэффициент смертности для всех возрастов."""
    rate = float(rate)
    male_rate = min(rate * male_multiplier, 0.95)
    female_rate = min(rate, 0.95)
    return np.full(101, male_rate), np.full(101, female_rate)


def load_from_yaml(path: str, male_multiplier: float = 1.08) -> tuple[np.ndarray, np.ndarray]:
    """Загружает таблицу смертности из YAML-файла.

    Формат YAML:
      # Единый список для обоих полов:
      rates:
        0: 0.005
        1: 0.001
        ...
        100: 0.50
      male_multiplier: 1.08   # опционально

      # Или раздельно по полам:
      male:
        0: 0.006
        ...
      female:
        0: 0.004
        ...
    """
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    multiplier = data.get("male_multiplier", male_multiplier)

    if "male" in data and "female" in data:
        mortality_male = _dict_to_array(data["male"])
        mortality_female = _dict_to_array(data["female"])
    elif "rates" in data:
        base = _dict_to_array(data["rates"])
        mortality_female = base.copy()
        mortality_male = np.clip(base * multiplier, 0.0, 0.95)
    else:
        raise ValueError(f"Неверный формат файла смертности: {path}")

    return mortality_male, mortality_female


def _dict_to_array(d: dict) -> np.ndarray:
    arr = np.zeros(101)
    for age, rate in d.items():
        age = int(age)
        if 0 <= age <= 100:
            arr[age] = float(rate)
    return np.clip(arr, 0.0, 0.95)


def parse_mortality(spec: str, male_multiplier: float = 1.08) -> tuple[np.ndarray, np.ndarray]:
    """Разбирает спецификацию смертности из CLI.

    Форматы:
      'gompertz'        — таблица Гомперца (по умолчанию)
      '0.012'           — плоский коэффициент
      'config:path.yaml' — из YAML-файла
    """
    spec = spec.strip()
    if spec == "gompertz":
        return build_gompertz_table(male_multiplier=male_multiplier)
    elif spec.startswith("gompertz:"):
        # Формат: gompertz:0.015 — задать уровень смертности в возрасте 55 лет
        try:
            rate = float(spec[len("gompertz:"):])
        except ValueError:
            raise ValueError(f"Формат: gompertz:<число>, например gompertz:0.015")
        return build_gompertz_table(base_rate=rate, male_multiplier=male_multiplier)
    elif spec.startswith("config:"):
        path = spec[len("config:"):]
        return load_from_yaml(path, male_multiplier=male_multiplier)
    else:
        try:
            rate = float(spec)
        except ValueError:
            raise ValueError(f"Неверная спецификация смертности: '{spec}'. Ожидается 'gompertz', число или 'config:путь'")
        if rate <= 0:
            raise ValueError(f"Плоский коэффициент смертности должен быть > 0, получено: {rate}")
        return build_flat_table(rate, male_multiplier=male_multiplier)
