"""CLI-интерфейс симулятора популяции на базе Typer."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

# legacy_windows=False — использовать ANSI вместо устаревшего Win32 API

from population.distributions import parse_distribution
from population.model import PopulationModel, SimulationParams
from population.mortality import parse_mortality
from population.reporting import print_summary_table, print_state_info

app = typer.Typer(
    name="population",
    help="Симулятор динамики населения — когортно-компонентная модель.",
    add_completion=False,
    context_settings={"help_option_names": ["--help", "-h"]},
)

console = Console(legacy_windows=False)


def _load_yaml_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve(cli_value, config: dict, key: str, default):
    """Возвращает CLI-значение если задано, иначе из конфига, иначе default."""
    if cli_value is not None:
        return cli_value
    return config.get(key, default)


def _parse_sex_ratio(spec: str) -> tuple[float, tuple[float, float] | None]:
    """Разбирает спецификацию соотношения полов.

    Форматы:
      '0.512'        — фиксированное значение
      '0.510-0.516'  — равномерный диапазон, каждый год семплируется случайно
    """
    spec = spec.strip()
    if "-" in spec:
        parts = spec.split("-", 1)
        lo, hi = float(parts[0]), float(parts[1])
        if lo > hi:
            lo, hi = hi, lo
        if not (0.0 < lo < 1.0 and 0.0 < hi < 1.0):
            raise ValueError(f"Значения sex-ratio должны быть в диапазоне (0, 1): {spec}")
        return lo, (lo, hi)   # фиксированное = середина диапазона не нужна, возвращаем lo как заглушку
    else:
        val = float(spec)
        if not (0.0 < val < 1.0):
            raise ValueError(f"sex-ratio должен быть в диапазоне (0, 1): {val}")
        return val, None


@app.command("simulate", help=(
    "Запускает симуляцию популяции и выводит половозрастные пирамиды.\n\n"
    "Значения по умолчанию указаны в скобках. Все параметры можно задать через\n"
    "YAML-файл (--config), а флаги командной строки переопределяют его значения.\n\n"
    "Примеры:\n\n"
    "  uv run population simulate --men 50000 --women 50000 --years 50\n\n"
    "  uv run population simulate --age-dist normal:35:12 --birth-rate 0.09 --animate\n\n"
    "  uv run population simulate --config configs/default.yaml --output both"
))
def simulate(
    # --- Население ---
    men: Annotated[Optional[int], typer.Option(
        "--men", "-m", help="Начальное число мужчин. [по умолч.: 50000]"
    )] = None,
    women: Annotated[Optional[int], typer.Option(
        "--women", "-w", help="Начальное число женщин. [по умолч.: 50000]"
    )] = None,
    age_dist: Annotated[Optional[str], typer.Option(
        "--age-dist", "-a",
        help=(
            "Начальное возрастное распределение. [по умолч.: pyramid]\n\n"
            "  pyramid          — убывающая пирамида (молодое население)\n"
            "  pyramid:0.04     — пирамида с заданным коэф. убывания\n"
            "  uniform:20-60    — равномерно от 20 до 60 лет\n"
            "  normal:35:12     — нормальное (среднее 35, std 12)\n"
            "  single:30        — все одного возраста (30 лет)\n"
            "  config:FILE      — из YAML-файла (age: count)"
        )
    )] = None,

    # --- Демографические параметры ---
    birth_rate: Annotated[Optional[float], typer.Option(
        "--birth-rate", "-b",
        help=(
            "Рождений на фертильную женщину в год. [по умолч.: 0.066]\n\n"
            "TFR = birth-rate × (fertility-end - fertility-start + 1)\n"
            "Примеры: 0.066 ≈ TFR 2.3 (мировой), 0.09 ≈ TFR 3.2, 0.04 ≈ TFR 1.4"
        )
    )] = None,
    fertility_start: Annotated[Optional[int], typer.Option(
        "--fertility-start", "-S", help="Возраст начала фертильности. [по умолч.: 15]"
    )] = None,
    fertility_end: Annotated[Optional[int], typer.Option(
        "--fertility-end", "-E", help="Возраст конца фертильности. [по умолч.: 49]"
    )] = None,
    mortality: Annotated[Optional[str], typer.Option(
        "--mortality", "-M",
        help=(
            "Коэффициент смертности по возрасту. [по умолч.: gompertz]\n\n"
            "  gompertz         — таблица Гомперца (реалистичная, рекомендуется)\n"
            "  gompertz:0.015   — Гомперц с заданным уровнем (якорь в 55 лет)\n"
            "  0.012            — плоский коэффициент для всех возрастов\n"
            "  config:FILE      — из YAML-файла (age: rate)"
        )
    )] = None,
    sex_ratio: Annotated[Optional[str], typer.Option(
        "--sex-ratio", "-r",
        help=(
            "Доля мальчиков среди новорождённых. [по умолч.: 0.510-0.516]\n\n"
            "  0.512            — фиксированное значение\n"
            "  0.510-0.516      — диапазон, каждый год семплируется случайно\n\n"
            "Биологическая норма: ~0.512 (105 мальчиков на 100 девочек)"
        )
    )] = None,
    male_multiplier: Annotated[Optional[float], typer.Option(
        "--male-multiplier", "-x",
        help="Множитель смертности мужчин относительно женщин. [по умолч.: 1.08]"
    )] = None,

    # --- Симуляция ---
    start_year: Annotated[Optional[int], typer.Option(
        "--start-year", "-Y", help="Начальный год (0 = показывает сколько лет прошло). [по умолч.: 0]"
    )] = None,
    years: Annotated[Optional[int], typer.Option(
        "--years", "-y", help="Число лет симуляции. [по умолч.: 50]"
    )] = None,

    # --- Вывод ---
    output: Annotated[Optional[str], typer.Option(
        "--output", "-o",
        help=(
            "Режим вывода пирамид. [по умолч.: show]\n\n"
            "  none   — только таблица в терминале, без графиков\n"
            "  show   — открыть в просмотрщике (не сохранять)\n"
            "  save   — сохранить файлы на диск (не открывать)\n"
            "  both   — сохранить и открыть"
        )
    )] = None,
    output_dir: Annotated[Optional[str], typer.Option(
        "--output-dir", "-d", help="Папка для сохранения изображений. [по умолч.: ./output]"
    )] = None,
    fmt: Annotated[Optional[str], typer.Option(
        "--format", "-f", help="Формат изображений: png | svg. [по умолч.: png]"
    )] = None,
    animate: Annotated[Optional[bool], typer.Option(
        "--animate/--no-animate", "-A/-nA",
        help="Создать анимированный GIF (дополнительно к PNG-снимкам)."
    )] = None,
    interval: Annotated[Optional[int], typer.Option(
        "--interval", "-i", help="Интервал между снимками пирамиды в годах. [по умолч.: 5]"
    )] = None,
    no_table: Annotated[bool, typer.Option(
        "--no-table", "-T", help="Не выводить сводную таблицу по годам в терминал."
    )] = False,

    # --- Конфиг ---
    config: Annotated[Optional[str], typer.Option(
        "--config", "-c",
        help=(
            "YAML-файл конфигурации. Флаги командной строки переопределяют его.\n\n"
            "Пример: uv run population simulate --config configs/default.yaml"
        )
    )] = None,
):

    # Загружаем конфиг (если задан)
    cfg: dict = {}
    if config:
        cfg = _load_yaml_config(config)

    # Разрешаем параметры: CLI > конфиг > умолчание
    r_men            = int(_resolve(men, cfg, "men", 50_000))
    r_women          = int(_resolve(women, cfg, "women", 50_000))
    r_age_dist       = str(_resolve(age_dist, cfg, "age_dist", "pyramid"))
    r_birth_rate     = float(_resolve(birth_rate, cfg, "birth_rate", 0.066))
    r_fertility_start = int(_resolve(fertility_start, cfg, "fertility_start", 15))
    r_fertility_end  = int(_resolve(fertility_end, cfg, "fertility_end", 49))
    r_mortality      = str(_resolve(mortality, cfg, "mortality", "gompertz"))
    r_sex_ratio_spec = str(_resolve(sex_ratio, cfg, "sex_ratio", "0.510-0.516"))
    r_male_mult      = float(_resolve(male_multiplier, cfg, "male_multiplier", 1.08))
    r_start_year     = int(_resolve(start_year, cfg, "start_year", 0))
    r_years          = int(_resolve(years, cfg, "years", 50))
    r_output         = str(_resolve(output, cfg, "output", "show"))
    r_output_dir     = str(_resolve(output_dir, cfg, "output_dir", "./output"))
    r_fmt            = str(_resolve(fmt, cfg, "format", "png"))
    r_animate        = bool(_resolve(animate, cfg, "animate", False))
    r_interval       = int(_resolve(interval, cfg, "interval", 5))

    # Парсинг соотношения полов
    try:
        r_sex_ratio, r_sex_ratio_range = _parse_sex_ratio(r_sex_ratio_spec)
    except ValueError as e:
        console.print(f"[red]Ошибка sex-ratio:[/red] {e}")
        raise typer.Exit(1)

    # Валидация
    if r_fertility_start >= r_fertility_end:
        console.print("[red]Ошибка:[/red] fertility-start должен быть меньше fertility-end")
        raise typer.Exit(1)
    if r_output not in ("none", "show", "save", "both"):
        console.print(f"[red]Ошибка:[/red] --output должен быть: none | show | save | both")
        raise typer.Exit(1)
    if r_fmt not in ("png", "svg"):
        console.print(f"[red]Ошибка:[/red] --format должен быть: png | svg")
        raise typer.Exit(1)

    # Печатаем параметры
    if r_sex_ratio_range:
        sex_ratio_display = f"{r_sex_ratio_range[0]}–{r_sex_ratio_range[1]} (случайно каждый год)"
    else:
        sex_ratio_display = str(r_sex_ratio)
    console.rule("[bold]Параметры симуляции[/bold]")
    console.print(f"  Начальная популяция: мужчины={r_men:,}, женщины={r_women:,}")
    console.print(f"  Возрастное распределение: {r_age_dist}")
    console.print(f"  Рождаемость: {r_birth_rate}/год на фертильную женщину")
    console.print(f"  Возраст фертильности: {r_fertility_start}–{r_fertility_end} лет")
    console.print(f"  Смертность: {r_mortality}  (множитель мужчин: {r_male_mult})")
    console.print(f"  Доля мальчиков при рождении: {sex_ratio_display}")
    console.print(f"  Период: {r_start_year}–{r_start_year + r_years} ({r_years} лет)")
    console.rule()

    # Строим начальное распределение
    try:
        males_init, females_init = parse_distribution(r_age_dist, r_men, r_women)
    except Exception as e:
        console.print(f"[red]Ошибка распределения:[/red] {e}")
        raise typer.Exit(1)

    # Строим таблицы смертности
    try:
        mortality_male, mortality_female = parse_mortality(r_mortality, male_multiplier=r_male_mult)
    except Exception as e:
        console.print(f"[red]Ошибка смертности:[/red] {e}")
        raise typer.Exit(1)

    params = SimulationParams(
        mortality_male=mortality_male,
        mortality_female=mortality_female,
        birth_rate=r_birth_rate,
        fertility_start=r_fertility_start,
        fertility_end=r_fertility_end,
        sex_ratio_at_birth=r_sex_ratio,
        sex_ratio_range=r_sex_ratio_range,
    )

    model = PopulationModel(males_init, females_init, params, start_year=r_start_year)

    # Запускаем симуляцию с прогресс-баром
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} лет"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Симуляция...", total=r_years)
        for _ in range(r_years):
            model.step()
            progress.advance(task)

    history = model.history

    # Таблица в терминале
    if not no_table:
        print_summary_table(history, interval=r_interval)

    # Итоговая сводка
    print_state_info(history[-1])

    # Визуализация
    do_save = r_output in ("save", "both")
    do_show = r_output in ("show", "both")

    if r_output == "none":
        return

    from population.visualization import save_pyramid, show_pyramid
    snapshots = [s for i, s in enumerate(history) if i % r_interval == 0]
    if history[-1] not in snapshots:
        snapshots.append(history[-1])

    # Сохранение PNG-снимков (всегда, независимо от --animate)
    if do_save:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task("Сохранение пирамид...", total=len(snapshots))
            for state in snapshots:
                save_pyramid(state, r_output_dir, fmt=r_fmt)
                progress.advance(task)
        console.print(f"[green]Пирамиды сохранены в:[/green] {r_output_dir}")

    # Анимация
    if r_animate:
        from population.visualization import save_animation, show_animation
        gif_path: str | None = None
        if do_save:
            with console.status("Создание анимации..."):
                gif_path = save_animation(history, r_output_dir, interval_years=r_interval)
            console.print(f"[green]Анимация сохранена:[/green] {gif_path}")
        if do_show:
            console.print("Открываю анимацию в системном просмотрщике...")
            show_animation(history, interval_years=r_interval, saved_path=gif_path)
    else:
        if do_show:
            for state in snapshots:
                show_pyramid(state)


@app.command("validate-config")
def validate_config(
    config_path: Annotated[str, typer.Argument(help="Путь к YAML-файлу конфигурации")],
):
    """Проверяет YAML-файл конфигурации без запуска симуляции."""
    path = Path(config_path)
    if not path.exists():
        console.print(f"[red]Файл не найден:[/red] {config_path}")
        raise typer.Exit(1)

    try:
        cfg = _load_yaml_config(config_path)
    except Exception as e:
        console.print(f"[red]Ошибка чтения YAML:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"[green]Файл корректен:[/green] {config_path}")
    console.print("\nПараметры:")
    for k, v in cfg.items():
        console.print(f"  {k}: {v}")

    # Проверяем смертность если задана
    mortality_spec = cfg.get("mortality", "gompertz")
    try:
        parse_mortality(str(mortality_spec))
        console.print(f"\n[green]Таблица смертности[/green] '{mortality_spec}' — ОК")
    except Exception as e:
        console.print(f"\n[red]Ошибка таблицы смертности:[/red] {e}")
        raise typer.Exit(1)

    # Проверяем распределение если задано
    age_dist_spec = cfg.get("age_dist", "pyramid")
    men = int(cfg.get("men", 50_000))
    women = int(cfg.get("women", 50_000))
    try:
        males, females = parse_distribution(str(age_dist_spec), men, women)
        console.print(f"[green]Возрастное распределение[/green] '{age_dist_spec}' — ОК "
                      f"(мужчин: {males.sum():,.0f}, женщин: {females.sum():,.0f})")
    except Exception as e:
        console.print(f"[red]Ошибка распределения:[/red] {e}")
        raise typer.Exit(1)

    console.print("\n[bold green]Конфиг прошёл валидацию.[/bold green]")
