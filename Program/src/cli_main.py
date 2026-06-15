import math
import os
import sys
import time
import matplotlib.pyplot as plt

# Правильное определение папки для PyInstaller (--onefile)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from process import (
    create_implicants,
    simulate_annealing,
    to_string,
)

# Словари из TUI версии для строгой математической валидации
COOLING_NAMES = {
    "linear": "линейного",
    "boltzmann": "Больцмана",
    "cauchy": "Коши",
}

COOLING_TEMP_END_MINIMUMS = {
    "linear": 0.0,
    "boltzmann": 2.0,
    "cauchy": 0.01,
}


def read_float(prompt: str, title: str, *, minimum: float | None = None, inclusive: bool = False) -> float:
    """Интерактивный ввод вещественного числа с валидацией."""
    while True:
        raw_value = input(prompt).strip().replace(",", ".")
        
        if not raw_value:
            print(f"Ошибка: {title}: поле не заполнено.")
            continue
            
        try:
            value = float(raw_value)
        except ValueError:
            print(f"Ошибка: {title}: нужно ввести число.")
            continue
            
        if not math.isfinite(value):
            print(f"Ошибка: {title}: значение должно быть конечным числом.")
            continue
            
        if minimum is not None:
            if inclusive and value < minimum:
                print(f"Ошибка: {title}: значение должно быть не меньше {minimum}.")
                continue
            if not inclusive and value <= minimum:
                print(f"Ошибка: {title}: значение должно быть больше {minimum}.")
                continue
                
        return value


def read_int(prompt: str, title: str, *, minimum: int | None = None) -> int:
    """Интерактивный ввод целого числа с валидацией."""
    while True:
        raw_value = input(prompt).strip()
        
        if not raw_value:
            print(f"Ошибка: {title}: поле не заполнено.")
            continue
            
        try:
            value = int(raw_value)
        except ValueError:
            print(f"Ошибка: {title}: нужно ввести целое число.")
            continue
            
        if minimum is not None and value < minimum:
            print(f"Ошибка: {title}: значение должно быть не меньше {minimum}.")
            continue
            
        return value


def read_vector(prompt: str) -> str:
    """Интерактивный ввод булевого вектора со строгой валидацией."""
    while True:
        vector = input(prompt).strip()
        
        if not vector:
            print("Ошибка: Булев вектор: поле не заполнено.")
            continue
            
        if any(ch not in "01" for ch in vector):
            print("Ошибка: Булев вектор: допускаются только символы 0 и 1.")
            continue
            
        if len(vector) < 2:
            print("Ошибка: Булев вектор: длина должна быть не меньше 2.")
            continue
            
        # Побитовая проверка: является ли длина степенью двойки
        if len(vector) & (len(vector) - 1):
            print("Ошибка: Булев вектор: длина должна быть степенью двойки (2, 4, 8, 16...).")
            continue
            
        if "1" not in vector:
            print("Ошибка: Булев вектор: должна быть хотя бы одна единица.")
            continue
            
        return vector


def read_cooling() -> str:
    print("\nВыберите закон охлаждения:")
    print("1 - Линейный")
    print("2 - Больцмана")
    print("3 - Коши")

    while True:
        choice = input("Ваш выбор: ").strip()
        if choice == "1":
            return "linear"
        elif choice == "2":
            return "boltzmann"
        elif choice == "3":
            return "cauchy"
        print("Ошибка. Введите 1, 2 или 3.")


def main():
    print("=" * 60)
    print("МИНИМИЗАЦИЯ ДНФ МЕТОДОМ ИМИТАЦИИ ОТЖИГА")
    print("=" * 60)
    print("(Для отмены и выхода нажмите Ctrl+C)\n")

    try:
        # 1. Вектор
        vector = read_vector("1. Булев вектор: ")

        # 2. Весовые коэффициенты (с кросс-валидацией)
        w1 = read_float("2. Весовой коэффициент 1: ", "Весовой коэффициент 1", minimum=0, inclusive=True)
        w2 = read_float("3. Весовой коэффициент 2: ", "Весовой коэффициент 2", minimum=0, inclusive=True)
        
        while w1 == 0 and w2 == 0:
            print("Ошибка: Весовые коэффициенты: хотя бы один коэффициент должен быть больше 0.")
            w1 = read_float("2. Весовой коэффициент 1: ", "Весовой коэффициент 1", minimum=0, inclusive=True)
            w2 = read_float("3. Весовой коэффициент 2: ", "Весовой коэффициент 2", minimum=0, inclusive=True)

        # 3. Температуры и итерации
        temp = read_float("4. Начальная температура: ", "Начальная температура", minimum=0) # strict > 0
        iterations = read_int("5. Количество итераций: ", "Количество итераций", minimum=1)

        # 4. Закон охлаждения (СПЕЦИАЛЬНО ПЕРЕНЕСЕН ПЕРЕД КОНЕЧНОЙ ТЕМПЕРАТУРОЙ)
        cooling = read_cooling()

        # 5. Конечная температура (зависит от начальной температуры и закона охлаждения)
        min_temp_end = COOLING_TEMP_END_MINIMUMS[cooling]
        while True:
            temp_end = read_float("6. Конечная температура: ", "Конечная температура", minimum=0, inclusive=True)
            
            if temp_end >= temp:
                print("Ошибка: Конечная температура: значение должно быть меньше начальной температуры.")
                continue
                
            if temp_end < min_temp_end:
                print(f"Ошибка: Конечная температура: для закона {COOLING_NAMES[cooling]} "
                      f"значение должно быть не меньше {min_temp_end:g}.")
                continue
                
            break

        # 6. Альфа (только для линейного)
        alpha = 0.0
        if cooling == "linear":
            alpha = read_float("7. Коэффициент alpha: ", "Коэффициент альфа", minimum=0, inclusive=True)

    except KeyboardInterrupt:
        print("\n\nПрограмма прервана пользователем.")
        return

    # --- ВЫЧИСЛЕНИЯ ---
    
    n = int(math.log2(len(vector)))
    ones = {str(i) for i, bit in enumerate(vector) if bit == "1"}
    cubes = create_implicants(n, vector)

    print("\nЗапуск алгоритма...\n")

    start_time = time.perf_counter()

    result, history, graph = simulate_annealing(
        cubes, ones, n, w1, w2, temp, temp_end, alpha, iterations, cooling,
    )

    elapsed = time.perf_counter() - start_time

    # ------------------------
    # ЛОГ
    # ------------------------
    log_path = os.path.join(BASE_DIR, "annealing_log.txt")

    with open(log_path, "w", encoding="utf-8") as f:
        for i, state in enumerate(history, start=1):
            f.write(f"[{i}] {state}\n")
        f.write("\n")
        f.write("ИТОГ:\n")
        f.write(to_string(result))
        f.write("\n")

    # ------------------------
    # ГРАФИК
    # ------------------------
    graph_path = os.path.join(BASE_DIR, "annealing_graph.png")
    x_values, y_values = graph

    plt.figure(figsize=(10, 6))
    plt.plot(x_values, y_values)
    plt.title("Снижение энергии системы")
    plt.xlabel("Изменение температуры (T0 - T)")
    plt.ylabel("Энергия системы (E)")
    plt.grid(True)
    plt.savefig(graph_path, dpi=300, bbox_inches="tight")
    plt.close()

    # ------------------------
    # РЕЗУЛЬТАТ
    # ------------------------
    print("=" * 60)
    print("РЕЗУЛЬТАТ")
    print("=" * 60)

    print("\nМинимизированная ДНФ:")
    print(to_string(result))

    print(f"\nВремя выполнения: {elapsed:.4f} сек")

    print("\nФайлы сохранены:")
    print(f"Лог:    {log_path}")
    print(f"График: {graph_path}")

    print("\nПрограмма завершена.")
    try:
        input("Нажмите Enter, чтобы выйти...")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()