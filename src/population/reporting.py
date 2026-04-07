"""Вывод статистики в терминал через Rich."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from population.model import PopulationState

console = Console(legacy_windows=False)


def print_summary_table(history: list[PopulationState], interval: int = 1) -> None:
    """Выводит сводную таблицу по годам симуляции."""
    table = Table(
        title="Динамика населения",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )

    table.add_column("Год", justify="right", style="bold")
    table.add_column("Всего", justify="right")
    table.add_column("Мужчин", justify="right")
    table.add_column("Женщин", justify="right")
    table.add_column("Соотн. полов\n(м/100ж)", justify="right")
    table.add_column("Медиан. возраст", justify="right")
    table.add_column("Рост, %", justify="right")
    table.add_column("0-14 / 15-64 / 65+", justify="center")

    prev_total: float | None = None

    for i, state in enumerate(history):
        if i % interval != 0 and i != len(history) - 1:
            continue

        total = state.total
        growth = ""
        if prev_total is not None and prev_total > 0:
            pct = (total - prev_total) / prev_total * 100
            sign = "+" if pct >= 0 else ""
            growth = f"{sign}{pct:.1f}%"
        prev_total = total

        age_g = state.age_groups_pct()
        age_str = f"{age_g['0-14']:.0f}% / {age_g['15-64']:.0f}% / {age_g['65+']:.0f}%"

        table.add_row(
            str(state.year),
            f"{total:,.0f}",
            f"{state.total_males:,.0f}",
            f"{state.total_females:,.0f}",
            f"{state.sex_ratio:.1f}",
            f"{state.median_age():.1f}",
            growth,
            age_str,
        )

    console.print(table)


def print_state_info(state: PopulationState) -> None:
    """Выводит краткую сводку по одному состоянию."""
    dep = state.dependency_ratio()
    age_g = state.age_groups_pct()

    console.print(f"\n[bold cyan]Год {state.year}[/bold cyan]")
    console.print(f"  Всего: [bold]{state.total:,.0f}[/bold]  "
                  f"(мужчин: {state.total_males:,.0f}, женщин: {state.total_females:,.0f})")
    console.print(f"  Соотношение полов: {state.sex_ratio:.1f} мужчин на 100 женщин")
    console.print(f"  Медианный возраст: {state.median_age():.1f} лет "
                  f"(м: {state.median_age('male'):.1f}, ж: {state.median_age('female'):.1f})")
    console.print(f"  Возрастные группы: "
                  f"0-14: {age_g['0-14']:.1f}%  "
                  f"15-64: {age_g['15-64']:.1f}%  "
                  f"65+: {age_g['65+']:.1f}%")
    console.print(f"  Демографическая нагрузка: "
                  f"дети: {dep['young']:.1f}  "
                  f"пожилые: {dep['old']:.1f}  "
                  f"итого: {dep['total']:.1f} на 100 работающих")
