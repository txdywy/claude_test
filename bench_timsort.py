#!/usr/bin/env python3
"""Benchmark harness for timsort — compare against built-in, test MIN_MERGE values."""
import time, random, sys
from timsort import timsort

N = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
RUNS = 5

SCENARIOS = [
    ('random',        lambda n: [random.randint(0, n) for _ in range(n)]),
    ('sorted',        lambda n: list(range(n))),
    ('reverse',       lambda n: list(range(n, 0, -1))),
    ('mostly sorted', lambda n: list(range(n)) + [random.randint(0, n) for _ in range(n // 10)]),
    ('few unique',    lambda n: [random.randint(0, 10) for _ in range(n)]),
    ('all equal',     lambda n: [42] * n),
    ('sawtooth',      lambda n: [i % 100 for i in range(n)]),
    ('pipe organ',    lambda n: list(range(n // 2)) + list(range(n // 2, 0, -1))),
]

def bench(sort_fn, gen, n, runs=RUNS):
    times = []
    for _ in range(runs):
        random.seed(42)
        a = gen(n)
        t0 = time.perf_counter()
        sort_fn(a)
        times.append(time.perf_counter() - t0)
    return min(times) * 1000  # best-of for less noise

def section(title):
    print(f'\n{"=" * 70}\n{title}\n{"=" * 70}')

# --- 1. Main comparison ---
section(f'Timsort vs built-in (n={N}, best of {RUNS})')
print(f'{"Scenario":25s} {"Ours (ms)":>10s} {"Built-in":>10s} {"Ratio":>8s}')
print('-' * 56)
for name, gen in SCENARIOS:
    ours = bench(timsort, gen, N)
    builtin = bench(list.sort, gen, N)
    ratio = ours / builtin if builtin > 0.001 else 0
    print(f'{name:25s} {ours:10.2f} {builtin:10.2f} {ratio:7.1f}x')

# --- 2. MIN_MERGE tuning ---
section(f'MIN_MERGE tuning (n={N})')
test_scenarios = [
    ('random',   lambda n: [random.randint(0, n) for _ in range(n)]),
    ('few unique', lambda n: [random.randint(0, 10) for _ in range(n)]),
    ('mostly sorted', lambda n: list(range(n)) + [random.randint(0, n) for _ in range(n // 10)]),
]
mm_values = [16, 32, 48, 64, 96, 128]

print(f'{"Scenario":25s}', ''.join(f'{"mm=" + str(m):>10s}' for m in mm_values))
print('-' * (25 + 10 * len(mm_values)))
for name, gen in test_scenarios:
    row = f'{name:25s}'
    for mm in mm_values:
        t = bench(lambda a: timsort(a, min_merge=mm), gen, N)
        row += f'{t:10.2f}'
    print(row)

# --- 3. key path ---
section(f'key/reverse overhead (n={N // 2})')
n2 = N // 2
gen = lambda n: [random.randint(0, n) for _ in range(n)]
t_plain = bench(timsort, gen, n2)
t_key = bench(lambda a: timsort(a, key=lambda x: -x), gen, n2)
t_rev = bench(lambda a: timsort(a, reverse=True), gen, n2)
print(f'  plain:   {t_plain:.2f} ms')
print(f'  key=-x:  {t_key:.2f} ms  ({t_key/t_plain:.2f}x vs plain)')
print(f'  reverse: {t_rev:.2f} ms  ({t_rev/t_plain:.2f}x vs plain)')
