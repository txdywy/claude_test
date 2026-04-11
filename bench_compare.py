#!/usr/bin/env python3
"""对比原版 timsort 与优化版 timsort_qwen 的性能"""
import time, random, sys
from timsort import timsort as timsort_orig
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

print(f'\n{"=" * 70}')
print(f'Timsort 原版 vs 优化版 (n={N}, 最佳 {RUNS} 次)')
print(f'{"=" * 70}')
print(f'{"场景":25s} {"原版(ms)":>10s} {"优化版(ms)":>10s} {"提升":>8s}')
print('-' * 56)

for name, gen in SCENARIOS:
    t_orig = bench(timsort_orig, gen, N)
    t_qwen = bench(timsort_qwen, gen, N)
    improvement = (t_orig - t_qwen) / t_orig * 100 if t_orig > 0 else 0
    ratio = t_orig / t_qwen if t_qwen > 0.001 else 0
    print(f'{name:25s} {t_orig:10.2f} {t_qwen:10.2f} {improvement:+7.1f}%')

print('\n' + '=' * 70)
