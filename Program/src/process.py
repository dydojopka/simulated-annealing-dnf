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

def simulate_annealing(cubes, ones, n, S1, S2, T0, T1, a, N, cooling):
    
    def new_cubes():
        c = list(cubes)
        t = random.randint(0, len(c))
        k = random.randint(0, n-1)
        r = random.randint(0, 2)
        p = ['0', '1', '-']
        if t == len(c):
            c.append(tuple(['-']*n))
        u = list(c[t])
        u[k] = p[r]
        c[t] = tuple(u)
        c = set(c)
        c.discard(tuple(['-']*n))
        return c

    lines = []
    graph = [[], []]

    T = T0

    i = 1
    while T > T1:
        graph[0].append(T0-T)
        graph[1].append(energy(cubes, ones, S1, S2, n))
        mini = 1000*1000*1000
        best = set()
        for _ in range(N):
            c = new_cubes()
            e = energy(c, ones, S1, S2, n)
            if mini > e:
                mini = e
                best = c
        delta = mini - energy(cubes, ones, S1, S2, n)
        if delta <= 0:
            cubes = best
        elif random.random() < math.exp(-delta/T):
            cubes = best
        
        lines.append(to_string(cubes))
        match cooling:
            case "linear":
                T = T0 - a*i
            case "boltzmann":
                T = T0 / math.log(1+i, math.e)
            case "cauchy":
                T = T0 / i
        i += 1
        
    graph[0].append(T0-T)
    graph[1].append(energy(cubes, ones, S1, S2, n))

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
