import asyncio
import math
import multiprocessing
import time
import traceback
import darkdetect
import sys
import os

from dataclasses import dataclass
from queue import Empty
from textual import on, events, errors
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Button, Label, RadioSet, RadioButton, RichLog
from textual.widget import Widget
from textual.theme import Theme
from textual.screen import Screen
from textual_plotext import PlotextPlot
from rich.style import Style
import matplotlib.pyplot as pyplt

from process import (
    create_implicants,
    simulate_annealing,
    to_string
)

# Правильное определение папки для PyInstaller (--onefile)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@dataclass
class AlgorithmConfig:
    vector: str
    w1: float
    w2: float
    temp: float
    temp_end: float
    alpha: float
    iterations: int
    cooling: str
    n: int
    ones: set[str]
    cubes: set[tuple[str, ...]]


class ConfigValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors

def _get_multiprocessing_context():
    if sys.platform == "win32":
        # На Windows доступен только spawn
        return multiprocessing.get_context("spawn")
    try:
        return multiprocessing.get_context("fork")
    except ValueError:
        return multiprocessing.get_context("spawn")

def _run_simulation_worker(
    result_queue,
    cubes,
    ones,
    n,
    w1,
    w2,
    temp,
    temp_end,
    alpha,
    iterations,
    cooling,
) -> None:
    # ЗАЩИТА TUI: Отключаем вывод в консоль у дочернего процесса,
    # чтобы он не сбросил настройки терминала Textual при своем завершении
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

    try:
        result, history, graph = simulate_annealing(
            cubes,
            ones,
            n,
            w1,
            w2,
            temp,
            temp_end,
            alpha,
            iterations,
            cooling,
        )
    except Exception:
        result_queue.put(("error", traceback.format_exc()))
    else:
        result_queue.put(("success", result, history, graph))


def _get_multiprocessing_context():
    try:
        return multiprocessing.get_context("fork")
    except ValueError:
        return multiprocessing.get_context()


# --- КАСТОМ ВИДЖЕТЫ ---

class ConfigInput(Input):
    """Поле ввода с заголовком"""
    def __init__(self, placeholder: str, border_title: str, id: str):
        super().__init__(placeholder=placeholder, id=id)
        self.border_title = border_title

class RadioGroup(Vertical):
    """Обертка для радио-кнопок"""
    can_focus = False
    def compose(self) -> ComposeResult:
        
        with RadioSet(id="law-radioset"):
            yield RadioButton("Линейный", value=True, id="rb-linear")
            yield RadioButton("Больцмана", id="rb-boltzmann")
            yield RadioButton("Коши", id="rb-cauchy")

    def on_mount(self) -> None:
        self.border_title = "Закон изменения температуры:"

class HistoryLog(RichLog):
    """Виджет лога"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._copy_lines: list[str] = []

    def init_log(self):
        self.reset()
        self.write_entry("Ожидание сохранения параметров...")

    def reset(self) -> None:
        self.clear()
        self._copy_lines.clear()

    def write_entry(self, message: str, copy_text: str | None = None) -> None:
        self.write(message)
        self._copy_lines.append(message if copy_text is None else copy_text)

    def get_copy_text(self) -> str:
        return "\n".join(self._copy_lines)

class EnergyPlot(PlotextPlot):
    """Виджет графика"""
    can_focus = False
    can_focus_children = False

    def on_mount(self) -> None:
        # Отключаем обработку мыши на уровне виджета
        self.disable_messages(events.MouseMove, events.Enter, events.Leave)

    def show_placeholder(self) -> None:
        """Отображает пустой график при запуске программы"""
        self.plt.clear_figure()
        self.plt.title("Снижение энергии системы (Минимизация ДНФ)")
        self.plt.plot([], [])
        self.plt.xlabel("Изменение температуры (T0 - T)")
        self.plt.ylabel("Энергия системы (E)")
        self.refresh()

    def plot_graph_data(self, graph: list[list[float]]) -> None:
        """Строит график по данным, которые возвращает simulate_annealing"""
        if len(graph) != 2:
            raise ValueError("Данные графика должны содержать две последовательности.")

        x_values, energy_values = graph

        if len(x_values) != len(energy_values):
            raise ValueError("Количество значений по осям X и Y не совпадает.")

        if not x_values:
            self.show_placeholder()
            return

        self.plt.clear_figure()
        self.plt.title("Снижение энергии системы (Минимизация ДНФ)")
        self.plt.plot(x_values, energy_values, marker="braille")
        self.plt.xlabel("Изменение температуры (T0 - T)")
        self.plt.ylabel("Энергия системы (E)")
        self.refresh()

class PerformanceScreen(Screen):
    """Экран с облегчённой обработкой мыши для плотных графиков (braille)."""
    MOUSE_STYLE_BYPASS_CLASS = "mouse-passive-art"

    def get_style_at(self, x: int, y: int) -> Style:
        try:
            widget, _ = self.get_widget_at(x, y)
        except errors.NoWidget:
            return Style.null()

        # Если виджет или его родитель имеет класс bypass, игнорируем стили
        for node in widget.ancestors_with_self:
            if isinstance(node, Widget) and node.has_class(self.MOUSE_STYLE_BYPASS_CLASS):
                return Style.null()

        return super().get_style_at(x, y)


# --- ГЛАВНОЕ ПРИЛОЖЕНИЕ ---

class AnnealingTUI(App):
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("space", "run_algorithm", "Запустить", priority=True),
        Binding("escape", "stop_algorithm", "Остановить", priority=True),
        Binding("ctrl+g", "save_graph", "Сохранить график", priority=True),
        Binding("ctrl+l", "save_log", "Сохранить лог", priority=True),
        Binding("ctrl+u", "clear_focused_input", "Очистить поле", priority=True),
    ]

    # Подключаем наш оптимизированный
    def get_default_screen(self) -> Screen:
        return PerformanceScreen(id="_default")


    INPUT_SELECTORS = (
        "#input-vector",
        "#input-w1",
        "#input-w2",
        "#input-temp",
        "#input-temp-end",
        "#input-alpha",
        "#input-n",
    )

    COOLING_LAWS = {
        "#rb-linear": "linear",
        "#rb-boltzmann": "boltzmann",
        "#rb-cauchy": "cauchy",
    }

    COOLING_NAMES = {
        "linear": "линейного",
        "boltzmann": "Больцмана",
        "cauchy": "Коши",
    }

    COOLING_TEMP_END_DEFAULTS = {
        "linear": "0",
        "boltzmann": "2",
        "cauchy": "0.01",
    }

    COOLING_TEMP_END_MINIMUMS = {
        "linear": 0.0,
        "boltzmann": 2.0,
        "cauchy": 0.01,
    }

    def __init__(self):
        super().__init__()
        self._is_running = False
        self._stop_requested = False
        self._worker_process: multiprocessing.Process | None = None
        self._mp_context = _get_multiprocessing_context()
        self._last_cooling = "linear"
        self._last_graph: list[list[float]] | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Horizontal():
            with Vertical(id="left-pane"):
                yield Label("НАСТРОЙКИ АЛГОРИТМА (АИО)", id="title-left")
                
                yield ConfigInput("01011101", "Булев вектор", "input-vector")
                
                with Horizontal(id="weights-row"):
                    with Vertical(id="w1-box"):
                        yield ConfigInput("1", "Весовой коэф. 1", "input-w1")
                    with Vertical(id="w2-box"):
                        yield ConfigInput("10", "Весовой коэф. 2", "input-w2")
                
                yield ConfigInput("20", "Нач. температура (T)", "input-temp")
                yield ConfigInput("0", "Конеч. температура", "input-temp-end")
                yield ConfigInput("100", "Количество итераций (N)", "input-n")
                
                yield RadioGroup(id="law-container")

                yield ConfigInput("0.5", "Коэффициент альфа (a)", "input-alpha")
                
                with Horizontal(id="actions-row"):
                    yield Button("ЗАПУСТИТЬ", variant="primary", id="btn-start")
                    yield Button("СТОП", variant="error", id="btn-stop", disabled=True)
                yield Label("Статус: Ожидание конфигурации...", id="status-label")
            
            # ОТСТУП СДЕЛАН НА ОДИН УРОВЕНЬ С left-pane !!!
            with Vertical(id="right-pane"):
                with Container(id="graph-box"):
                    yield Label("ГРАФИК", id="title-graph")
                    yield EnergyPlot(id="energy-plot", classes="mouse-passive-art")
                
                with Container(id="log-box"):
                    yield Label("ЛОГ ИСТОРИИ ВЕКТОРОВ", id="title-log")
                    yield HistoryLog(id="vector-log", highlight=True, markup=True)
                    
        yield Footer(show_command_palette=False)


    def _register_themes(self) -> None:
        """Регистрирует светлую и тёмную темы"""
        light_theme = Theme(
            name="my_light_theme",
            primary="#4ecca3",
            secondary="#d0d5dd",
            background="#f5f7fa",
            surface="#ffffff",
            foreground="#2c3e50",
            warning="#e68a00",
            error="#c62828",
            success="#2e7d32",
            accent="#8e24aa",
            dark=False,
        )
        dark_theme = Theme(
            name="my_dark_theme",
            primary="#4ecca3",
            secondary="#393e46",
            background="#232931",
            surface="#1e1e1e",
            foreground="#eeeeee",
            warning="#ffaa00",
            error="#d32f2f",
            success="#4caf50",
            accent="#ffc2f8",
            dark=True
        )
        self.register_theme(light_theme)
        self.register_theme(dark_theme)


    def on_mount(self) -> None:
            # Регистрируем кастомные темы
            self._register_themes()
            # Определение темы ОС(я понятия не имею зачем, но мне почему то очень захотелось это сделать)
            system_theme = darkdetect.theme()
            
            if system_theme == "Light":
                self.theme = "my_light_theme"
            else:
                self.theme = "my_dark_theme"

            self.query_one(HistoryLog).init_log()
            self._apply_cooling_ui(update_temp_end=False)
            self._set_status("Ожидание конфигурации...", "idle")

            # Вызываем плейсхолдер вместо случайных данных
            self.query_one(EnergyPlot).show_placeholder()

    def _set_status(self, message: str, state: str = "idle") -> None:
        label = self.query_one("#status-label", Label)
        label.update(f"Статус: {message}")
        for status_class in ("idle", "running", "success", "error"):
            label.remove_class(status_class)
        label.add_class(state)

    def _clear_input_errors(self) -> None:
        for selector in self.INPUT_SELECTORS:
            self.query_one(selector, Input).remove_class("invalid")

    def _get_selected_cooling(self) -> str | None:
        return next(
            (
                law
                for selector, law in self.COOLING_LAWS.items()
                if self.query_one(selector, RadioButton).value
            ),
            None,
        )

    def _apply_cooling_ui(self, *, update_temp_end: bool) -> None:
        cooling = self._get_selected_cooling() or "linear"
        alpha_input = self.query_one("#input-alpha", Input)
        temp_end_input = self.query_one("#input-temp-end", Input)

        alpha_input.display = cooling == "linear"
        temp_end_input.placeholder = self.COOLING_TEMP_END_DEFAULTS[cooling]

        if update_temp_end:
            normalized_value = temp_end_input.value.strip().replace(",", ".")
            previous_default = self.COOLING_TEMP_END_DEFAULTS.get(self._last_cooling)
            if not normalized_value or normalized_value == previous_default:
                temp_end_input.value = self.COOLING_TEMP_END_DEFAULTS[cooling]

        self._last_cooling = cooling

    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.1f} с"

        total_seconds = int(round(seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return f"{hours} ч {minutes:02d} мин {seconds:02d} с"

        return f"{minutes} мин {seconds:02d} с"

    def _terminate_worker(self) -> None:
        process = self._worker_process
        if process is None or not process.is_alive():
            return

        process.terminate()
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)

    def _read_config(self) -> AlgorithmConfig:
        self._clear_input_errors()
        errors: list[str] = []

        def mark_invalid(selector: str, message: str) -> None:
            self.query_one(selector, Input).add_class("invalid")
            errors.append(message)

        def parse_float(selector: str, title: str, *, minimum: float | None = None,
                        inclusive: bool = False) -> float | None:
            field = self.query_one(selector, Input)
            raw_value = field.value.strip().replace(",", ".")

            if not raw_value:
                mark_invalid(selector, f"{title}: поле не заполнено.")
                return None

            try:
                value = float(raw_value)
            except ValueError:
                mark_invalid(selector, f"{title}: нужно ввести число.")
                return None

            if not math.isfinite(value):
                mark_invalid(selector, f"{title}: значение должно быть конечным числом.")
                return None

            if minimum is not None:
                if inclusive and value < minimum:
                    mark_invalid(selector, f"{title}: значение должно быть не меньше {minimum}.")
                    return None
                if not inclusive and value <= minimum:
                    mark_invalid(selector, f"{title}: значение должно быть больше {minimum}.")
                    return None

            return value

        def parse_int(selector: str, title: str, *, minimum: int) -> int | None:
            field = self.query_one(selector, Input)
            raw_value = field.value.strip()

            if not raw_value:
                mark_invalid(selector, f"{title}: поле не заполнено.")
                return None

            try:
                value = int(raw_value)
            except ValueError:
                mark_invalid(selector, f"{title}: нужно ввести целое число.")
                return None

            if value < minimum:
                mark_invalid(selector, f"{title}: значение должно быть не меньше {minimum}.")
                return None

            return value

        vector_field = self.query_one("#input-vector", Input)
        vector = vector_field.value.strip()

        if not vector:
            mark_invalid("#input-vector", "Булев вектор: поле не заполнено.")
        else:
            if any(ch not in "01" for ch in vector):
                mark_invalid("#input-vector", "Булев вектор: допускаются только символы 0 и 1.")
            if len(vector) < 2:
                mark_invalid("#input-vector", "Булев вектор: длина должна быть не меньше 2.")
            elif len(vector) & (len(vector) - 1):
                mark_invalid("#input-vector", "Булев вектор: длина должна быть степенью двойки.")
            if "1" not in vector:
                mark_invalid("#input-vector", "Булев вектор: должна быть хотя бы одна единица.")

        w1 = parse_float("#input-w1", "Весовой коэффициент 1", minimum=0, inclusive=True)
        w2 = parse_float("#input-w2", "Весовой коэффициент 2", minimum=0, inclusive=True)
        temp = parse_float("#input-temp", "Начальная температура", minimum=0)
        temp_end = parse_float("#input-temp-end", "Конечная температура", minimum=0, inclusive=True)
        iterations = parse_int("#input-n", "Количество итераций", minimum=1)
        cooling = self._get_selected_cooling()
        alpha = (
            parse_float("#input-alpha", "Коэффициент альфа", minimum=0)
            if cooling == "linear"
            else 0.0
        )

        if w1 == 0 and w2 == 0:
            mark_invalid("#input-w1", "Весовые коэффициенты: хотя бы один коэффициент должен быть больше 0.")
            self.query_one("#input-w2", Input).add_class("invalid")

        if temp is not None and temp_end is not None:
            if temp_end >= temp:
                mark_invalid(
                    "#input-temp-end",
                    "Конечная температура: значение должно быть меньше начальной температуры.",
                )

            minimum_temp_end = self.COOLING_TEMP_END_MINIMUMS.get(cooling)
            if minimum_temp_end is not None and temp_end < minimum_temp_end:
                mark_invalid(
                    "#input-temp-end",
                    "Конечная температура: для закона "
                    f"{self.COOLING_NAMES[cooling]} значение должно быть не меньше {minimum_temp_end:g}.",
                )

        if cooling is None:
            errors.append("Закон изменения температуры: выберите один вариант.")

        if errors:
            raise ConfigValidationError(errors)

        n = int(math.log2(len(vector)))
        ones = {
            str(i)
            for i, ch in enumerate(vector)
            if ch == "1"
        }
        cubes = create_implicants(n, vector)

        return AlgorithmConfig(
            vector=vector,
            w1=w1,
            w2=w2,
            temp=temp,
            temp_end=temp_end,
            alpha=alpha,
            iterations=iterations,
            cooling=cooling,
            n=n,
            ones=ones,
            cubes=cubes,
        )

    @on(Button.Pressed, "#btn-start")
    def start_algorithm(self) -> None:
        # Запускаем алгоритм как независимую фоновую задачу
        asyncio.create_task(self._run_algorithm())

    @on(Button.Pressed, "#btn-stop")
    def stop_algorithm(self) -> None:
        self.action_stop_algorithm()

    def action_run_algorithm(self) -> None:
        asyncio.create_task(self._run_algorithm())

    @on(RadioSet.Changed, "#law-radioset")
    def cooling_law_changed(self) -> None:
        self._apply_cooling_ui(update_temp_end=True)

    async def action_run_algorithm(self) -> None:
        await self._run_algorithm()

    def action_stop_algorithm(self) -> None:
        if not self._is_running:
            self._set_status("Нет активного расчёта.", "idle")
            return

        self._stop_requested = True
        self.query_one("#btn-stop", Button).disabled = True
        self._set_status("Останавливаю расчёт...", "running")
        self._terminate_worker()

    def action_clear_focused_input(self) -> None:
        focused = self.focused
        if not isinstance(focused, Input):
            self._set_status("Активное поле ввода не выбрано.", "idle")
            return

        focused.clear()
        focused.remove_class("invalid")
        self._set_status("Активное поле очищено.", "idle")

    def action_save_graph(self) -> None:
        if self._last_graph is None:
            self._set_status("Нет данных для сохранения. Сначала запустите алгоритм.", "error")
            self.notify("Сначала запустите алгоритм", severity="warning")
            return

        graph_path = os.path.join(BASE_DIR, "annealing_graph.png")
        x_values, y_values = self._last_graph

        try:
            pyplt.figure(figsize=(10, 6))
            pyplt.plot(x_values, y_values)
            pyplt.title("Снижение энергии системы")
            pyplt.xlabel("Изменение температуры (T0 - T)")
            pyplt.ylabel("Энергия системы (E)")
            pyplt.grid(True)
            pyplt.savefig(graph_path, dpi=300, bbox_inches="tight")
            pyplt.close()
        except Exception as error:
            self._set_status(f"Не удалось сохранить график: {error}", "error")
            self.notify(f"Ошибка сохранения: {error}", severity="error")
        else:
            self._set_status(f"График сохранён: {graph_path}", "success")
            self.notify(f"График сохранён:\n{graph_path}", timeout=5)


    def action_save_log(self) -> None:
        log = self.query_one(HistoryLog)
        text = log.get_copy_text().strip()

        if not text:
            self._set_status("Лог пуст, нечего сохранять.", "error")
            return

        log_path = os.path.join(BASE_DIR, "annealing_log.txt")
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as error:
            self._set_status(f"Не удалось сохранить лог: {error}", "error")
            self.notify(f"Ошибка сохранения лога: {error}", severity="error")
        else:
            self._set_status(f"Лог сохранён: {log_path}", "success")
            self.notify(f"Лог сохранён:\n{log_path}", timeout=5)

    async def _run_algorithm(self) -> None:
            if self._is_running:
                self._set_status("Алгоритм уже выполняется.", "running")
                return

            self._is_running = True
            self._stop_requested = False
            start_button = self.query_one("#btn-start", Button)
            stop_button = self.query_one("#btn-stop", Button)
            start_button.disabled = True
            stop_button.disabled = True
            log = self.query_one(HistoryLog)
            result_queue = None

            try:
                self._set_status("Проверяю параметры...", "running")
                config = self._read_config()

                log.reset()
                log.write_entry(
                    "[bold]Параметры приняты. Запускаю алгоритм...[/bold]",
                    "Параметры приняты. Запускаю алгоритм...",
                )
                self._set_status("Алгоритм выполняется...", "running")
                stop_button.disabled = False

                result_queue = self._mp_context.Queue()
                process = self._mp_context.Process(
                    target=_run_simulation_worker,
                    args=(
                        result_queue,
                        config.cubes,
                        config.ones,
                        config.n,
                        config.w1,
                        config.w2,
                        config.temp,
                        config.temp_end,
                        config.alpha,
                        config.iterations,
                        config.cooling,
                    ),
                    daemon=True,
                )
                self._worker_process = process

                started_at = time.monotonic()
                process.start()

                message = None
                # Асинхронный цикл опроса, который не блокирует UI
                while True:
                    elapsed = time.monotonic() - started_at
                    self._set_status(f"Алгоритм выполняется... {self._format_elapsed(elapsed)}", "running")

                    # Мгновенная реакция на нажатие кнопки СТОП
                    if self._stop_requested:
                        log.reset()
                        log.write_entry("[bold yellow]Расчёт остановлен пользователем.[/bold yellow]")
                        log.write_entry(f"Время до остановки: {self._format_elapsed(elapsed)}")
                        self._set_status(f"Остановлено. Время: {self._format_elapsed(elapsed)}.", "error")
                        return

                    # Забираем результат из очереди до join(), чтобы избежать переполнения буфера ОС
                    try:
                        message = result_queue.get_nowait()
                        break 
                    except Empty:
                        pass

                    # Если процесс завершился, делаем последнюю попытку считать данные
                    if not process.is_alive():
                        try:
                            message = result_queue.get_nowait()
                        except Empty:
                            pass
                        break

                    # Отдаем управление Textual для отрисовки и приема кликов
                    await asyncio.sleep(0.1)

                process.join()
                elapsed = time.monotonic() - started_at
                elapsed_text = self._format_elapsed(elapsed)

                if message is None:
                    exit_code = process.exitcode
                    if exit_code:
                        raise RuntimeError(f"Расчёт завершился с кодом {exit_code}.")
                    raise RuntimeError("Расчёт завершился без результата.")

                status = message[0]
                if status == "error":
                    raise RuntimeError(message[1])

                _, result, history, graph = message
                self._last_graph = graph
                self.query_one(EnergyPlot).plot_graph_data(graph)

                log.reset()
                
                # Вывод ВСЕЙ истории (может вызвать кратковременный фриз при больших объемах)
                for i, state in enumerate(history, start=1):
                    log.write_entry(f"[{i}] {state}")

                log.write_entry("")
                log.write_entry("[bold green]Итог:[/bold green]", "Итог:")
                log.write_entry(to_string(result))
                log.write_entry(f"Время выполнения: {elapsed_text}")
                self._set_status(f"Готово за {elapsed_text}. Шагов в истории: {len(history)}.", "success")

            except ConfigValidationError as error:
                log.reset()
                log.write_entry("[bold red]Ошибки в параметрах:[/bold red]", "Ошибки в параметрах:")
                for message in error.errors:
                    log.write_entry(f"- {message}", message)
                self._set_status("Исправьте параметры и запустите снова.", "error")

            except Exception as error:
                log.reset()
                log.write_entry("[bold red]Ошибка выполнения:[/bold red]", "Ошибка выполнения:")
                log.write_entry(str(error))
                self._set_status(f"Ошибка выполнения: {error}", "error")

            finally:
                self._terminate_worker()
                if result_queue is not None:
                    result_queue.close()
                self._worker_process = None
                start_button.disabled = False
                stop_button.disabled = True
                self._is_running = False


if __name__ == "__main__":
    # ОБЯЗАТЕЛЬНО для multiprocessing + PyInstaller на Windows
    multiprocessing.freeze_support() 
    
    app = AnnealingTUI()
    app.run()