import time, random, statistics, sys
sys.path.insert(0, '.')
from timsort import timsort as orig
from timsort_cc import timsort as cc
from timsort_qwen import timsort as qwen

WARMUP = 3; RUNS = 5
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
        data = list(range(size)); swaps = max(size // 100, 10)
        for _ in range(swaps):
            i, j = random.randint(0, size-1), random.randint(0, size-1)
            data[i], data[j] = data[j], data[i]
        return data
    elif pattern == "few_unique":
        return [random.randint(0, 10) for _ in range(size)]
    return [random.random() for _ in range(size)]

def bench(fn, data):
    arr = list(data)
    s = time.perf_counter(); fn(arr)
    assert all(arr[i] <= arr[i+1] for i in range(len(arr)-1))
    return time.perf_counter() - s

patterns = ["random", "sorted", "reverse", "nearly_sorted", "few_unique"]
print(f"{'Pattern':<16} {'Size':>7} {'orig':>9} {'cc':>9} {'qwen':>9} {'best':>5}")
print("-" * 55)
for pat in patterns:
    for sz in SIZES:
        data = make_data(sz, pat)
        for _ in range(WARMUP):
            bench(orig, list(data)); bench(cc, list(data)); bench(qwen, list(data))
        ot = statistics.mean(bench(orig, list(data))*1000 for _ in range(RUNS))
        ct = statistics.mean(bench(cc, list(data))*1000 for _ in range(RUNS))
        qt = statistics.mean(bench(qwen, list(data))*1000 for _ in range(RUNS))
        best = "orig" if ot <= min(ct, qt) else ("cc" if ct <= qt else "qwen")
        print(f"{pat:<16} {sz:>7} {ot:>9.3f} {ct:>9.3f} {qt:>9.3f} {best:>5}")
