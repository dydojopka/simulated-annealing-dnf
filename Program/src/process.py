import random
import math
import json

def create_implicants(n, vec):
    
    ones = {i for i, ch in enumerate(vec) if ch == '1'}

    all_cubes = set()

    for idx in ones:
        bits = format(idx, f'0{n}b')
        cube = tuple(bits)
        all_cubes.add(cube)

    return all_cubes

def energy(c, ones, S1, S2, n):
    p1 = 0
    for el in c:
        for ch in el:
            if ch != '-':
                p1 += 1

    check = set()        
    for el in c:
        k = ['0']
        for i in range(n):
            # print(el[i])
            if el[i] == '1':
                for j in range(len(k)):
                    k[j] = str(int(k[j]) + pow(2, n-i-1))
            if el[i] == '-':
                l = len(k)
                for j in range(l):
                    k.append(str(int(k[j]) + pow(2, n-i-1)))
        for kk in k:
            check.add(kk)

    check1 = check & ones
    check2 = check | ones
    p2 = len(check2) - len(check1)

    return p1*S1 + p2*S2

def to_string(cubes):
    arr = []
    for el in cubes:
        arr.append(list(el))
    arr = sorted(arr)
    ans = ""
    for el in arr:
        for i in range(len(el)):
            if el[i] == "-":
                continue
            if el[i] == '0':
                ans += "~"
            ans += chr(ord('a') + i)
        ans += " | "
    else:
        ans = ans[:-2]
    return ans

def simulate_annealing(cubes, ones, n, S1, S2, T0, T1, a, N, cooling, history_interval=1):
    def cube_values(cube):
        values = [0]
        for index, bit in enumerate(cube):
            value = 1 << (n - index - 1)
            if bit == '1':
                values = [item + value for item in values]
            elif bit == '-':
                values += [item + value for item in values]
        return values

    def literal_count(cube):
        return sum(bit != '-' for bit in cube)

    cubes = set(cubes)
    cube_list = list(cubes)
    cube_indices = {cube: index for index, cube in enumerate(cube_list)}
    all_dash = tuple(['-'] * n)
    symbols = ['0', '1', '-']
    target = bytearray(1 << n)
    for value in ones:
        target[int(value)] = 1

    coverage_counts = [0] * (1 << n)
    literals = 0
    for cube in cubes:
        literals += literal_count(cube)
        for value in cube_values(cube):
            coverage_counts[value] += 1
    mismatches = sum((count > 0) != bool(target[index]) for index, count in enumerate(coverage_counts))

    def candidate_energy():
        position = random.randint(0, len(cube_list))
        bit_index = random.randint(0, n - 1)
        symbol = symbols[random.randint(0, 2)]

        removed = None
        if position == len(cube_list):
            changed = list(all_dash)
        else:
            removed = cube_list[position]
            changed = list(removed)
        changed[bit_index] = symbol
        added = tuple(changed)

        if added == removed:
            return literals * S1 + mismatches * S2, None, None
        if added == all_dash or added in cubes:
            added = None

        literal_delta = 0
        coverage_delta = {}
        if removed is not None:
            literal_delta -= literal_count(removed)
            for value in cube_values(removed):
                coverage_delta[value] = coverage_delta.get(value, 0) - 1
        if added is not None:
            literal_delta += literal_count(added)
            for value in cube_values(added):
                coverage_delta[value] = coverage_delta.get(value, 0) + 1

        mismatch_delta = 0
        for value, count_delta in coverage_delta.items():
            was_mismatch = (coverage_counts[value] > 0) != bool(target[value])
            is_mismatch = (coverage_counts[value] + count_delta > 0) != bool(target[value])
            mismatch_delta += int(is_mismatch) - int(was_mismatch)

        candidate = (literals + literal_delta) * S1 + (mismatches + mismatch_delta) * S2
        return candidate, removed, added

    def apply_change(removed, added):
        nonlocal literals, mismatches
        changed_values = {}
        if removed is not None:
            cubes.remove(removed)
            removed_index = cube_indices.pop(removed)
            last_cube = cube_list.pop()
            if removed_index < len(cube_list):
                cube_list[removed_index] = last_cube
                cube_indices[last_cube] = removed_index
            literals -= literal_count(removed)
            for value in cube_values(removed):
                changed_values[value] = changed_values.get(value, 0) - 1
        if added is not None:
            cubes.add(added)
            cube_indices[added] = len(cube_list)
            cube_list.append(added)
            literals += literal_count(added)
            for value in cube_values(added):
                changed_values[value] = changed_values.get(value, 0) + 1
        for value, count_delta in changed_values.items():
            was_mismatch = (coverage_counts[value] > 0) != bool(target[value])
            coverage_counts[value] += count_delta
            is_mismatch = (coverage_counts[value] > 0) != bool(target[value])
            mismatches += int(is_mismatch) - int(was_mismatch)

    lines = []
    graph = [[], []]
    T = T0
    current_energy = literals * S1 + mismatches * S2

    i = 1
    while T > T1:
        graph[0].append(T0 - T)
        graph[1].append(current_energy)
        mini = 1000 * 1000 * 1000
        best_removed = None
        best_added = None
        for _ in range(N):
            candidate, removed, added = candidate_energy()
            if mini > candidate:
                mini = candidate
                best_removed = removed
                best_added = added
        delta = mini - current_energy
        if delta <= 0 or random.random() < math.exp(-delta / T):
            apply_change(best_removed, best_added)
            current_energy = mini

        if i % history_interval == 0:
            lines.append(to_string(cubes))
        match cooling:
            case "linear":
                T = T0 - a * i
            case "boltzmann":
                T = T0 / math.log(1 + i, math.e)
            case "cauchy":
                T = T0 / i
        i += 1

    if (i - 1) % history_interval != 0:
        lines.append(to_string(cubes))

    graph[0].append(T0 - T)
    graph[1].append(current_energy)

    return cubes, lines, graph
        
        
def main():
    n = int(input())
    vec = input()
    S1 = float(input())
    S2 = float(input())
    T0 = float(input())
    T1 = float(input())
    cooling = input()
    a = float(input())
    N = int(input())

    ones = {str(i) for i, ch in enumerate(vec) if ch == '1'}

    cubes = create_implicants(n, vec)
    lines = []
    graph = []

    result, lines, graph = simulate_annealing(cubes, ones, n, S1, S2, T0, T1, a, N, cooling)

    with open("lines.txt", "w", encoding="utf-8") as file:
        file.writelines(lines)
        file.close()

    with open("graph.json", "w") as file:
        json.dump(graph, file)
        file.close()

    print(to_string(result))


if __name__ == "__main__":
    main()
