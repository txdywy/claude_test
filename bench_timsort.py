#!/usr/bin/env python3
"""Benchmark: timsort.py vs timsort_cc.py"""

import time
import random
import statistics
import sys

sys.path.insert(0, '.')

from timsort import timsort as timsort_orig
from timsort_cc import timsort as timsort_cc

WARMUP = 3
RUNS = 5
SIZES = [1000, 10000, 100000]

def make_data(size, pattern):
    random.seed(42)
    if pattern == "random":
        return [random.random() for _ in range(size)]
    elif pattern == "sorted":
        return list(range(size))
    elif pattern == "reverse":
        return list(range(size, 0, -1))
    elif pattern == "nearly_sorted":
        data = list(range(size))
        swaps = max(size // 100, 10)
        for _ in range(swaps):
            i, j = random.randint(0, size - 1), random.randint(0, size - 1)
            data[i], data[j] = data[j], data[i]
        return data
    elif pattern == "many_runs":
        data = []
        run_len = max(size // 500, 4)
        for i in range(0, size, run_len):
            chunk = list(range(i, min(i + run_len, size)))
            random.shuffle(chunk)
            data.extend(chunk)
        return data[:size]
    elif pattern == "few_unique":
        return [random.randint(0, 10) for _ in range(size)]
    return [random.random() for _ in range(size)]

def bench(fn, data, name):
    arr = list(data)
    start = time.perf_counter()
    fn(arr)
    elapsed = time.perf_counter() - start
    assert all(arr[i] <= arr[i + 1] for i in range(len(arr) - 1)), f"{name}: not sorted!"
    return elapsed

patterns = ["random", "sorted", "reverse", "nearly_sorted", "many_runs", "few_unique"]

print(f"{'Pattern':<16} {'Size':>8} {'Original (ms)':>14} {'CC (ms)':>10} {'Speedup':>10}")
print("-" * 64)

for pattern in patterns:
    for size in SIZES:
        data = make_data(size, pattern)

        for _ in range(WARMUP):
            bench(timsort_orig, list(data), "warmup")
            bench(timsort_cc, list(data), "warmup")

        orig_times = []
        cc_times = []
        for _ in range(RUNS):
            orig_times.append(bench(timsort_orig, list(data), "orig") * 1000)
            cc_times.append(bench(timsort_cc, list(data), "cc") * 1000)

        orig_avg = statistics.mean(orig_times)
        cc_avg = statistics.mean(cc_times)
        speedup = orig_avg / cc_avg if cc_avg > 0 else float('inf')

        print(f"{pattern:<16} {size:>8} {orig_avg:>14.3f} {cc_avg:>10.3f} {speedup:>9.2f}x")
