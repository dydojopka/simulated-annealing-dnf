import math
import random
import darkdetect

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Button, Label, RadioSet, RadioButton, RichLog
from textual_plotext import PlotextPlot
from textual.theme import Theme

# --- КАСТОМ ВИДЖЕТЫ ---

class ConfigInput(Input):
    """Поле ввода с заголовком"""
    def __init__(self, placeholder: str, border_title: str, id: str):
        super().__init__(placeholder=placeholder, id=id)
        self.border_title = border_title

class RadioGroup(Vertical):
    """Обертка для радио-кнопок"""
    def compose(self) -> ComposeResult:
        
        with RadioSet(id="law-radioset"):
            yield RadioButton("Больцмана", id="rb-boltzmann")
            yield RadioButton("Линейный", value=True, id="rb-linear")
            yield RadioButton("Коши", id="rb-cauchy")
            yield RadioButton("Квадратичный", id="rb-quadratic")

    def on_mount(self) -> None:
        self.border_title = "Закон изменения температуры:"

class HistoryLog(RichLog):
    """Виджет лога"""
    def init_log(self):
        self.write("[bold green]>[/bold green] Система TUI успешно инициализирована.")
        self.write("[bold yellow]>[/bold yellow] Ожидание сохранения параметров...")

    def log_iteration(self, i, t, e):
        self.write(f"> [Итерация {i:02d}] T={t:.1f}, E={e}, Вектор: 101100101...")

class EnergyPlot(PlotextPlot):
    """Виджет графика"""
    def update_plot(self):
        iterations = list(range(1, 101))
        energy = [
            40 * math.exp(-i / 25) + random.uniform(0, 15 * math.exp(-i / 40)) 
            for i in iterations
        ]
        
        self.plt.clear_figure()
        self.plt.title("Снижение энергии (минимизация ДНФ)")
        self.plt.plot(iterations, energy, marker="braille")
        self.plt.xlabel("Количество итераций")
        self.plt.ylabel("Энергия системы (E)")
        self.refresh()
        

# --- ГЛАВНОЕ ПРИЛОЖЕНИЕ ---

class AnnealingTUI(App):
    CSS_PATH = "app.tcss"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Horizontal():
            with Vertical(id="left-pane"):
                yield Label("НАСТРОЙКИ АЛГОРИТМА (АИО)", id="title-left")
                
                yield ConfigInput("1011010011001", "Булев вектор", "input-vector")
                
                with Horizontal(id="weights-row"):
                    with Vertical(id="w1-box"):
                        yield ConfigInput("1.5", "Весовой коэф. 1", "input-w1")
                    with Vertical(id="w2-box"):
                        yield ConfigInput("0.8", "Весовой коэф. 2", "input-w2")
                
                yield ConfigInput("100.0", "Нач. температура (T)", "input-temp")
                yield ConfigInput("0.95", "Коэффициент альфа (α)", "input-alpha")
                yield ConfigInput("1000", "Количество итераций (n)", "input-n")
                
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
        """Регистрирует светлую и тёмную темы."""
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

            # Инициализация логов и графика (твой исходный код)
            self.query_one(HistoryLog).init_log()
            for i in range(1, 21):
                self.query_one(HistoryLog).log_iteration(i, 100.0 - i*4.5, 45 - i)
                
            self.query_one(EnergyPlot).update_plot()

if __name__ == "__main__":
    app = AnnealingTUI()
    app.run()