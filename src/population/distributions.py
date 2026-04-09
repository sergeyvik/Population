"""Построители начального возрастного распределения населения."""

from __future__ import annotations

import numpy as np
import yaml


def build_pyramid(total: int, decay: float = 0.03) -> np.ndarray:
    """Молодёжная пирамида: вес убывает экспоненциально с возрастом."""
    ages = np.arange(101, dtype=float)
    weights = np.exp(-decay * ages)
    weights /= weights.sum()
    return (weights * total).round().astype(float)


def build_uniform(total: int, age_min: int, age_max: int) -> np.ndarray:
    """Равномерное распределение в диапазоне [age_min, age_max]."""
    arr = np.zeros(101)
    age_min = max(0, min(age_min, 100))
    age_max = max(0, min(age_max, 100))
    if age_min > age_max:
        age_min, age_max = age_max, age_min
    n = age_max - age_min + 1
    base = total // n
    remainder = total - base * n
    arr[age_min:age_max + 1] = float(base)
    arr[age_min:age_min + remainder] += 1.0
    return arr


def build_normal_no_scipy(total: int, mean: float, std: float) -> np.ndarray:
    """Нормальное распределение без scipy (через numpy)."""
    ages = np.arange(101, dtype=float)
    weights = np.exp(-0.5 * ((ages - mean) / std) ** 2)
    weights /= weights.sum()
    return (weights * total).round().astype(float)


def build_single(total: int, age: int) -> np.ndarray:
    """Все люди одного возраста."""
    arr = np.zeros(101)
    age = max(0, min(age, 100))
    arr[age] = float(total)
    return arr


def load_from_yaml(path: str, sex: str) -> np.ndarray:
    """Загружает явное распределение из YAML-файла.

    Формат YAML (пример):
      male:
        0: 850
        1: 840
        5: 800
      female:
        0: 820
        1: 815
    """
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    dist_data = data.get(sex, {})
    arr = np.zeros(101)
    for age, count in dist_data.items():
        age = int(age)
        if 0 <= age <= 100:
            arr[age] = float(count)
    return arr


def parse_distribution(spec: str, total_men: int, total_women: int) -> tuple[np.ndarray, np.ndarray]:
    """Разбирает спецификацию возрастного распределения.

    Форматы:
      'pyramid'              — убывающая пирамида (по умолчанию)
      'pyramid:0.05'         — пирамида с заданным decay
      'uniform:20-60'        — равномерно от 20 до 60 лет
      'normal:35:12'         — нормальное с mean=35, std=12
      'single:30'            — все в возрасте 30 лет
      'config:путь.yaml'     — из YAML-файла
    """
    spec = spec.strip()

    if spec == "pyramid" or spec.startswith("pyramid:"):
        decay = 0.03
        if ":" in spec:
            try:
                decay = float(spec.split(":", 1)[1])
            except ValueError:
                pass
        males = build_pyramid(total_men, decay)
        females = build_pyramid(total_women, decay)

    elif spec.startswith("uniform:"):
        rest = spec[len("uniform:"):]
        parts = rest.split("-")
        if len(parts) != 2:
            raise ValueError(f"Формат: uniform:<min>-<max>, получено: '{spec}'")
        age_min, age_max = int(parts[0]), int(parts[1])
        males = build_uniform(total_men, age_min, age_max)
        females = build_uniform(total_women, age_min, age_max)

    elif spec.startswith("normal:"):
        rest = spec[len("normal:"):]
        parts = rest.split(":")
        if len(parts) != 2:
            raise ValueError(f"Формат: normal:<mean>:<std>, получено: '{spec}'")
        mean, std = float(parts[0]), float(parts[1])
        males = build_normal_no_scipy(total_men, mean, std)
        females = build_normal_no_scipy(total_women, mean, std)

    elif spec.startswith("single:"):
        age = int(spec[len("single:"):])
        males = build_single(total_men, age)
        females = build_single(total_women, age)

    elif spec.startswith("config:"):
        path = spec[len("config:"):]
        males = load_from_yaml(path, "male")
        females = load_from_yaml(path, "female")
        # Масштабируем до заданной численности
        if males.sum() > 0:
            males = males / males.sum() * total_men
        if females.sum() > 0:
            females = females / females.sum() * total_women

    else:
        raise ValueError(f"Неизвестная спецификация распределения: '{spec}'")

    return males.astype(float), females.astype(float)
