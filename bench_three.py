#!/usr/bin/env python3
"""三版本对比基准测试"""
import time, random, sys
from timsort import timsort as timsort_orig
from timsort_cc import timsort as timsort_cc
from timsort_qwen import timsort as timsort_qwen

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
    return min(times) * 1000

print(f'\n{"=" * 85}')
print(f'三版本对比 (n={N}, 最佳 {RUNS} 次)')
print(f'{"=" * 85}')
print(f'{"场景":25s} {"orig(ms)":>10s} {"cc(ms)":>10s} {"qwen(ms)":>10s} {"最快":>8s}')
print('-' * 66)

for name, gen in SCENARIOS:
    t1 = bench(timsort_orig, gen, N)
    t2 = bench(timsort_cc, gen, N)
    t3 = bench(timsort_qwen, gen, N)
    best = min(t1, t2, t3)
    winner = 'orig' if best == t1 else ('cc' if best == t2 else 'qwen')
    print(f'{name:25s} {t1:10.2f} {t2:10.2f} {t3:10.2f} {winner:>8s}')

print()
