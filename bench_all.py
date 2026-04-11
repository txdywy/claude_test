#!/usr/bin/env python3
"""Benchmark: timsort.py vs timsort_cc.py vs timsort_qwen.py"""
import time, random, statistics, sys
sys.path.insert(0, '.')

from timsort import timsort as ts_orig
from timsort_cc import timsort as ts_cc
from timsort_qwen import timsort as ts_qwen

WARMUP, RUNS = 3, 7
SIZES = [1_000, 10_000, 100_000]

def make_data(size, pattern):
    random.seed(42)
    if pattern == "random":
        return [random.random() for _ in range(size)]
    if pattern == "sorted":
        return list(range(size))
    if pattern == "reverse":
        return list(range(size, 0, -1))
    if pattern == "nearly_sorted":
        d = list(range(size))
        for _ in range(max(size // 100, 10)):
            i, j = random.randint(0, size-1), random.randint(0, size-1)
            d[i], d[j] = d[j], d[i]
        return d
    if pattern == "few_unique":
        return [random.randint(0, 10) for _ in range(size)]
    if pattern == "pipe_organ":
        half = size // 2
        return list(range(half)) + list(range(half, 0, -1))
    return [random.random() for _ in range(size)]

def bench(fn, data):
    a = list(data)
    t = time.perf_counter()
    fn(a)
    return (time.perf_counter() - t) * 1000

patterns = ["random", "sorted", "reverse", "nearly_sorted", "few_unique", "pipe_organ"]
impls = [("orig", ts_orig), ("cc", ts_cc), ("qwen", ts_qwen)]

print(f"{'Pattern':<16} {'Size':>7}  {'orig(ms)':>9} {'cc(ms)':>9} {'qwen(ms)':>9}  {'best':>6} {'cc/orig':>8} {'qwen/orig':>10}")
print("-" * 95)

for pat in patterns:
    for size in SIZES:
        data = make_data(size, pat)
        # warmup
        for _ in range(WARMUP):
            for _, fn in impls:
                bench(fn, data)
        # measure
        results = {}
        for name, fn in impls:
            times = [bench(fn, data) for _ in range(RUNS)]
            results[name] = statistics.median(times)
        best = min(results, key=results.get)
        r_cc = results['cc'] / results['orig'] if results['orig'] > 0 else 0
        r_qw = results['qwen'] / results['orig'] if results['orig'] > 0 else 0
        print(f"{pat:<16} {size:>7}  {results['orig']:>9.3f} {results['cc']:>9.3f} {results['qwen']:>9.3f}  {best:>6} {r_cc:>8.3f} {r_qw:>10.3f}")
    print()
