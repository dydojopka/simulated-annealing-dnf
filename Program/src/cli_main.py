import math
import os
import time

import matplotlib.pyplot as plt

# Получаем путь к папке, в которой лежит текущий скрипт
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

    vector = input("1. Булев вектор: ").strip()

    w1 = float(input("2. Весовой коэффициент 1: "))
    w2 = float(input("3. Весовой коэффициент 2: "))

    temp = float(input("4. Начальная температура: "))
    temp_end = float(input("5. Конечная температура: "))

    iterations = int(input("6. Количество итераций: "))

    cooling = read_cooling()

    alpha = 0.0

    if cooling == "linear":
        alpha = float(input("8. Коэффициент alpha: "))

    n = int(math.log2(len(vector)))

    ones = {
        str(i)
        for i, bit in enumerate(vector)
        if bit == "1"
    }

    cubes = create_implicants(n, vector)

    print("\nЗапуск алгоритма...\n")

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
    print("РЕЗУЛЬТАТ")
    print("=" * 60)

    print("\nМинимизированная ДНФ:")
    print(to_string(result))

    print(f"\nВремя выполнения: {elapsed:.4f} сек")

    print("\nФайлы сохранены:")

    print(f"Лог:    {log_path}")
    print(f"График: {graph_path}")


if __name__ == "__main__":
    main()