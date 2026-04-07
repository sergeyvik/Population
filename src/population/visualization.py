"""Визуализация половозрастной пирамиды населения."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np

from population.model import PopulationState


# Возрастные группы (5-летние когорты)
AGE_GROUPS = [
    (0, 4), (5, 9), (10, 14), (15, 19), (20, 24),
    (25, 29), (30, 34), (35, 39), (40, 44), (45, 49),
    (50, 54), (55, 59), (60, 64), (65, 69), (70, 74),
    (75, 79), (80, 84), (85, 89), (90, 94), (95, 100),
]

GROUP_LABELS = [f"{a}-{b}" for a, b in AGE_GROUPS]


def _aggregate_to_groups(arr: np.ndarray) -> np.ndarray:
    """Суммирует по 5-летним когортам."""
    result = np.zeros(len(AGE_GROUPS))
    for i, (a, b) in enumerate(AGE_GROUPS):
        result[i] = arr[a:b + 1].sum()
    return result


def _draw_pyramid(ax, state: PopulationState) -> None:
    """Рисует пирамиду на переданном ax (без создания fig)."""
    import matplotlib.ticker as mticker

    male_groups = _aggregate_to_groups(state.males)
    female_groups = _aggregate_to_groups(state.females)

    y = np.arange(len(AGE_GROUPS))
    ax.clear()

    ax.barh(y, -male_groups, height=0.8, color="#4a90d9", alpha=0.85)
    ax.barh(y, female_groups, height=0.8, color="#e07070", alpha=0.85)

    ax.set_yticks(y)
    ax.set_yticklabels(GROUP_LABELS, fontsize=8)

    max_val = max(male_groups.max(), female_groups.max()) * 1.15 + 1
    ax.set_xlim(-max_val, max_val)

    # Подписи численности после каждой полоски
    label_offset = max_val * 0.01  # отступ в 1% от ширины оси
    for i, (m, f) in enumerate(zip(male_groups, female_groups)):
        if round(m) > 0:
            ax.text(-m - label_offset, i, f"{m:,.0f}",
                    ha="right", va="center", fontsize=6.5, color="#2a60a0")
        if round(f) > 0:
            ax.text(f + label_offset, i, f"{f:,.0f}",
                    ha="left", va="center", fontsize=6.5, color="#b04040")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{abs(x):,.0f}"))
    ax.axvline(0, color="black", linewidth=0.8)

    ax.text(0.02, 0.98, "Мужчины",
            ha="left", va="top", fontsize=10, color="#4a90d9", fontweight="bold",
            transform=ax.transAxes)
    ax.text(0.98, 0.98, "Женщины",
            ha="right", va="top", fontsize=10, color="#e07070", fontweight="bold",
            transform=ax.transAxes)

    ax.set_title(f"Половозрастная пирамида — {state.year} {'год' if state.year >= 1900 else 'лет'}",
                 fontsize=13, fontweight="bold", pad=14)
    ax.set_xlabel("Численность населения", fontsize=9)
    ax.set_ylabel("Возрастная группа", fontsize=9)

    age_g = state.age_groups_pct()
    dep = state.dependency_ratio()
    info = (
        f"Всего: {state.total:,.0f}\n"
        f"Муж: {state.total_males:,.0f}  |  Жен: {state.total_females:,.0f}\n"
        f"Соотн. полов: {state.sex_ratio:.1f} м/100ж\n"
        f"Медиан. возраст: {state.median_age():.1f} лет\n"
        f"0-14: {age_g['0-14']:.1f}%  15-64: {age_g['15-64']:.1f}%  65+: {age_g['65+']:.1f}%\n"
        f"Нагрузка: {dep['total']:.1f} на 100 работающих"
    )
    ax.text(
        0.98, 0.92, info,
        transform=ax.transAxes,
        fontsize=7.5,
        verticalalignment="top",
        horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow", alpha=0.85),
    )
    ax.grid(axis="x", linestyle="--", alpha=0.4, linewidth=0.6)


def _make_figure(state: PopulationState):
    """Создаёт фигуру с пирамидой для одного состояния."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 8))
    _draw_pyramid(ax, state)
    fig.tight_layout()
    return fig, ax


def show_pyramid(state: PopulationState) -> None:
    """Показывает пирамиду в интерактивном окне."""
    import matplotlib.pyplot as plt
    fig, _ = _make_figure(state)
    plt.show()
    plt.close(fig)


def save_pyramid(state: PopulationState, output_dir: str, fmt: str = "png") -> str:
    """Сохраняет пирамиду в файл. Возвращает путь к файлу."""
    import matplotlib.pyplot as plt

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = os.path.join(output_dir, f"pyramid_{state.year}.{fmt}")
    fig, _ = _make_figure(state)
    fig.savefig(path, dpi=120, bbox_inches="tight", backend="agg")
    plt.close(fig)
    return path


def _build_animation(snapshots: list[PopulationState], fps: int):
    """Строит объект FuncAnimation и возвращает (fig, anim)."""
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation

    fig, ax = plt.subplots(figsize=(10, 8))
    _draw_pyramid(ax, snapshots[0])
    fig.tight_layout()

    def update(frame_idx: int):
        _draw_pyramid(ax, snapshots[frame_idx])
        fig.tight_layout()

    anim = animation.FuncAnimation(
        fig,
        update,
        frames=len(snapshots),
        interval=1000 // fps,
        repeat=True,
    )
    return fig, anim


def _select_snapshots(
    history: list[PopulationState], interval_years: int
) -> list[PopulationState]:
    snapshots = [s for i, s in enumerate(history) if i % interval_years == 0]
    if history[-1] not in snapshots:
        snapshots.append(history[-1])
    return snapshots


def save_animation(
    history: list[PopulationState],
    output_dir: str,
    interval_years: int = 1,
    fps: int = 2,
) -> str:
    """Создаёт анимированный GIF. Возвращает путь к файлу."""
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    snapshots = _select_snapshots(history, interval_years)
    if not snapshots:
        raise ValueError("Нет данных для анимации")

    fig, anim = _build_animation(snapshots, fps)

    gif_path = os.path.join(output_dir, "pyramid_animation.gif")
    try:
        writer = animation.PillowWriter(fps=fps)
        anim.save(gif_path, writer=writer, dpi=100)
        plt.close(fig)
        return gif_path
    except Exception:
        plt.close(fig)
        # Попытка MP4
        mp4_path = os.path.join(output_dir, "pyramid_animation.mp4")
        try:
            fig2, anim2 = _build_animation(snapshots, fps)
            writer_mp4 = animation.FFMpegWriter(fps=fps)
            anim2.save(mp4_path, writer=writer_mp4)
            plt.close(fig2)
            return mp4_path
        except Exception as e:
            raise RuntimeError(f"Не удалось сохранить анимацию: {e}") from e


def show_animation(
    history: list[PopulationState],
    interval_years: int = 1,
    fps: int = 2,
    saved_path: str | None = None,
) -> None:
    """Открывает анимацию в системном просмотрщике.

    Если saved_path задан — открывает его.
    Иначе сохраняет во временный файл и открывает его.
    Это надёжнее plt.show() с FuncAnimation, который не работает
    в не-интерактивных или консольных окружениях.
    """
    if saved_path and os.path.exists(saved_path):
        path_to_open = saved_path
    else:
        snapshots = _select_snapshots(history, interval_years)
        tmp = tempfile.NamedTemporaryFile(
            suffix=".gif", prefix="population_", delete=False
        )
        tmp.close()
        import matplotlib.pyplot as plt
        import matplotlib.animation as animation

        fig, anim = _build_animation(snapshots, fps)
        writer = animation.PillowWriter(fps=fps)
        anim.save(tmp.name, writer=writer, dpi=80)
        plt.close(fig)
        path_to_open = tmp.name

    _open_with_system_viewer(path_to_open)


def _open_with_system_viewer(path: str) -> None:
    """Открывает файл системным приложением по умолчанию."""
    import subprocess
    import sys

    try:
        if sys.platform == "win32":
            os.startfile(path)          # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=True)
        else:
            subprocess.run(["xdg-open", path], check=True)
    except Exception as e:
        # Если системный просмотрщик не нашёлся — сообщаем путь
        from rich.console import Console
        Console(legacy_windows=False).print(
            f"[yellow]Не удалось открыть автоматически.[/yellow] "
            f"Откройте вручную: [bold]{path}[/bold]"
        )
