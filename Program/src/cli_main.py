import math
import os
import sys
import time
import matplotlib.pyplot as plt

# Правильное определение папки для PyInstaller (--onefile)
if getattr(sys, 'frozen', False):
    # Если запущено как скомпилированный .exe
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Если запущено как обычный скрипт .py
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from process import (
    create_implicants,
    simulate_annealing,
    to_string,
)


def read_cooling():
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

    # 1. Валидация булева вектора
    while True:
        vector = input("1. Булев вектор: ").strip()
        if not vector:
            print("Ошибка: вектор не может быть пустым.")
            continue
        if not all(c in '01' for c in vector):
            print("Ошибка: вектор должен состоять только из символов '0' и '1'.")
            continue
        length = len(vector)
        if length < 2 or (length & (length - 1)) != 0:
            print("Ошибка: длина вектора должна быть степенью двойки (2, 4, 8, 16, 32, 64...).")
            continue
        break

    # 2. Валидация весового коэффициента 1
    while True:
        try:
            w1 = float(input("2. Весовой коэффициент 1: "))
            if w1 < 0:
                print("Ошибка: коэффициент не может быть отрицательным.")
                continue
            break
        except ValueError:
            print("Ошибка: введите корректное число.")

    # 3. Валидация весового коэффициента 2
    while True:
        try:
            w2 = float(input("3. Весовой коэффициент 2: "))
            if w2 < 0:
                print("Ошибка: коэффициент не может быть отрицательным.")
                continue
            break
        except ValueError:
            print("Ошибка: введите корректное число.")

    # 4. Валидация начальной температуры
    while True:
        try:
            temp = float(input("4. Начальная температура: "))
            if temp <= 0:
                print("Ошибка: начальная температура должна быть больше 0.")
                continue
            break
        except ValueError:
            print("Ошибка: введите корректное число.")

    # 5. Валидация конечной температуры
    while True:
        try:
            temp_end = float(input("5. Конечная температура: "))
            if temp_end <= 0:
                print("Ошибка: конечная температура должна быть больше 0.")
                continue
            if temp_end >= temp:
                print(f"Ошибка: конечная температура должна быть строго меньше начальной ({temp}).")
                continue
            break
        except ValueError:
            print("Ошибка: введите корректное число.")

    # 6. Валидация коэффициента альфа
    while True:
        try:
            alpha = float(input("6. Коэффициент альфа (0 < alpha < 1): "))
            if not (0 < alpha < 1):
                print("Ошибка: коэффициент альфа должен находиться в диапазоне (0, 1) для корректного затухания.")
                continue
            break
        except ValueError:
            print("Ошибка: введите корректное число.")

    # 7. Валидация количества итераций
    while True:
        try:
            iterations = int(input("7. Количество итераций: "))
            if iterations <= 0:
                print("Ошибка: количество итераций должно быть целым числом больше 0.")
                continue
            break
        except ValueError:
            print("Ошибка: введите целое число.")

    # 8. Выбор закона охлаждения
    cooling = read_cooling()

    # Подготовка данных для алгоритма
    n = int(math.log2(len(vector)))
    cubes, ones = create_implicants(vector)

    print("\nЗапуск алгоритма имитации отжига...")
    start_time = time.perf_counter()

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
    print("РЕЗУЛЬТАТЫ ВЫЧИСЛЕНИЙ")
    print("=" * 60)
    print(to_string(result))
    print(f"Время выполнения: {elapsed:.4f} сек.")
    print(f"Лог сохранен в: {log_path}")
    print(f"График сохранен в: {graph_path}")
    print("=" * 60)

    # Ожидание ввода перед закрытием окна (исправление для .exe)
    input("\nНажмите Enter, чтобы выйти...")


if __name__ == "__main__":
    main()