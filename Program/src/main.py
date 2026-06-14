import asyncio
import math
import random
import darkdetect

from dataclasses import dataclass
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Button, Label, RadioSet, RadioButton, RichLog
from textual_plotext import PlotextPlot
from textual.theme import Theme
from textual import on

from process import (
    create_implicants,
    simulate_annealing,
    to_string
)


@dataclass
class AlgorithmConfig:
    vector: str
    w1: float
    w2: float
    temp: float
    alpha: float
    iterations: int
    n: int
    ones: set[str]
    cubes: set[tuple[str, ...]]


class ConfigValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


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
            yield RadioButton("Больцмана", id="rb-boltzmann")
            yield RadioButton("Линейный", value=True, id="rb-linear")
            yield RadioButton("Коши", id="rb-cauchy")
            yield RadioButton("Квадратичный", id="rb-quadratic")

    def on_mount(self) -> None:
        self.border_title = "Закон изменения температуры:"
        self.border_subtitle = "плейсхолдер!"

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
    
    def show_placeholder(self) -> None:
        """Отображает пустой график при запуске программы"""
        self.plt.clear_figure()
        self.plt.title("График энергии")
        self.plt.plot([], [])
        self.plt.xlabel("Итерации алгоритма")
        self.plt.ylabel("Энергия системы (E)")
        self.refresh()

    def plot_real_data(self, energies: list[float], temperatures: list[float]) -> None:
        """Строит график по реальным данным после выполнения алгоритма"""
        self.plt.clear_figure()
        self.plt.title("Снижение энергии системы (Минимизация ДНФ)")
        
        # Ось X - порядковые номера шагов
        iterations = list(range(1, len(energies) + 1))
        
        # Линию энергии
        self.plt.plot(iterations, energies, marker="braille", label="Энергия")
        
        # Линии температуры
        self.plt.plot(iterations, temperatures, marker="braille", label="Температура")
        
        self.plt.xlabel("Количество итераций")
        self.plt.ylabel("Значение")
        self.refresh()
        

# --- ГЛАВНОЕ ПРИЛОЖЕНИЕ ---

class AnnealingTUI(App):
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("space", "run_algorithm", "Запустить", priority=True),
        Binding("ctrl+l", "copy_log", "Копировать лог", priority=True),
    ]

    INPUT_SELECTORS = (
        "#input-vector",
        "#input-w1",
        "#input-w2",
        "#input-temp",
        "#input-alpha",
        "#input-n",
    )

    def __init__(self):
        super().__init__()
        self._is_running = False

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
                yield ConfigInput("0.5", "Коэффициент альфа (a)", "input-alpha")
                yield ConfigInput("100", "Количество итераций (N)", "input-n")
                
                yield RadioGroup(id="law-container")
                
                yield Button("СОХРАНИТЬ И ЗАПУСТИТЬ", variant="primary", id="btn-start")
                yield Label("Статус: Ожидание конфигурации...", id="status-label")
                
            with Vertical(id="right-pane"):
                with Container(id="graph-box"):
                    yield Label("АНАЛИТИКА И ГРАФИКИ", id="title-graph")
                    yield EnergyPlot(id="energy-plot")
                
                with Container(id="log-box"):
                    yield Label("ЛОГ ИСТОРИИ ВЕКТОРОВ", id="title-log")
                    yield HistoryLog(id="vector-log", highlight=True, markup=True)
                    
        yield Footer()


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
        alpha = parse_float("#input-alpha", "Коэффициент альфа", minimum=0)
        iterations = parse_int("#input-n", "Количество итераций", minimum=1)

        if w1 == 0 and w2 == 0:
            mark_invalid("#input-w1", "Весовые коэффициенты: хотя бы один коэффициент должен быть больше 0.")
            self.query_one("#input-w2", Input).add_class("invalid")

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
            alpha=alpha,
            iterations=iterations,
            n=n,
            ones=ones,
            cubes=cubes,
        )

    @on(Button.Pressed, "#btn-start")
    async def start_algorithm(self) -> None:
        await self._run_algorithm()

    async def action_run_algorithm(self) -> None:
        await self._run_algorithm()

    def action_copy_log(self) -> None:
        log = self.query_one(HistoryLog)
        text = log.get_copy_text().strip()

        if not text:
            self._set_status("Лог пуст, копировать нечего.", "error")
            return

        try:
            self.copy_to_clipboard(text)
        except Exception as error:
            self._set_status(f"Не удалось скопировать лог: {error}", "error")
        else:
            self._set_status("Лог скопирован в буфер обмена.", "success")
            self.notify("Лог скопирован в буфер обмена")

    async def _run_algorithm(self) -> None:
        if self._is_running:
            self._set_status("Алгоритм уже выполняется.", "running")
            return

        self._is_running = True
        start_button = self.query_one("#btn-start", Button)
        start_button.disabled = True
        log = self.query_one(HistoryLog)

        try:
            self._set_status("Проверяю параметры...", "running")
            config = self._read_config()

            log.reset()
            log.write_entry(
                "[bold]Параметры приняты. Запускаю алгоритм...[/bold]",
                "Параметры приняты. Запускаю алгоритм...",
            )
            self._set_status("Алгоритм выполняется...", "running")

            await asyncio.sleep(0)
            result, history = await asyncio.to_thread(
                simulate_annealing,
                config.cubes,
                config.ones,
                config.n,
                config.w1,
                config.w2,
                config.temp,
                config.alpha,
                config.iterations,
            )

            log.reset()
            for i, state in enumerate(history, start=1):
                log.write_entry(f"[{i}] {state}")

            log.write_entry("")
            log.write_entry("[bold green]Итог:[/bold green]", "Итог:")
            log.write_entry(to_string(result))
            self._set_status(f"Готово. Шагов в истории: {len(history)}.", "success")

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
            start_button.disabled = False
            self._is_running = False

if __name__ == "__main__":
    app = AnnealingTUI()
    app.run()
