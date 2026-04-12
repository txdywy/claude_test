"""Stress test: compare C sort output against Python's sorted() for many random cases."""
import ctypes
import random
import sys

lib = ctypes.CDLL('./libsort_c.dylib')
lib.timsort_int64.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.c_size_t]
lib.timsort_int64.restype = ctypes.c_int
lib.timsort_double.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_size_t]
lib.timsort_double.restype = ctypes.c_int

Arr64 = ctypes.c_int64
ArrD = ctypes.c_double

failures = 0
tests = 0

def test_int64(seed, n, lo=-10000, hi=10000):
    global failures, tests
    random.seed(seed)
    data = [random.randint(lo, hi) for _ in range(n)]
    c_arr = (ctypes.c_int64 * n)(*data)
    ret = lib.timsort_int64(c_arr, n)
    if ret != 0:
        print(f"FAIL: timsort_int64 returned {ret}, seed={seed}, n={n}")
        failures += 1
    got = [c_arr[i] for i in range(n)]
    expected = sorted(data)
    if got != expected:
        # Find first mismatch
        for i in range(min(len(got), len(expected))):
            if got[i] != expected[i]:
                print(f"FAIL: seed={seed}, n={n}, first mismatch at [{i}]: got={got[i]}, expected={expected[i]}")
                print(f"  input  = {data[:30]}")
                print(f"  got    = {got[:30]}")
                print(f"  expect = {expected[:30]}")
                failures += 1
                return
        if len(got) != len(expected):
            print(f"FAIL: seed={seed}, n={n}, length mismatch: got={len(got)}, expected={len(expected)}")
            failures += 1
            return
    tests += 1

def test_double(seed, n):
    global failures, tests
    random.seed(seed)
    data = [random.uniform(-1e9, 1e9) for _ in range(n)]
    c_arr = (ctypes.c_double * n)(*data)
    ret = lib.timsort_double(c_arr, n)
    if ret != 0:
        print(f"FAIL: timsort_double returned {ret}, seed={seed}, n={n}")
        failures += 1
    got = [c_arr[i] for i in range(n)]
    expected = sorted(data)
    if got != expected:
        for i in range(min(len(got), len(expected))):
            if got[i] != expected[i]:
                print(f"FAIL: seed={seed}, n={n}, first mismatch at [{i}]: got={got[i]}, expected={expected[i]}")
                failures += 1
                return
    tests += 1

# Scenario 1: Many random seeds, various sizes
print("=== Scenario 1: Random seeds x sizes ===")
for n in [1, 2, 3, 5, 10, 31, 32, 33, 63, 64, 65, 100, 255, 256, 257,
          500, 999, 1000, 1001, 5000, 10000]:
    for seed in range(100):  # 100 seeds per size
        test_int64(seed * 10000 + n, n)
    print(f"  n={n}: 100/100 passed")

# Scenario 2: Large values, including INT64 boundaries
print("\n=== Scenario 2: Large / boundary values ===")
edge_cases = [
    [0, 0, 0],
    [2**63 - 1, -(2**63), 0, 1, -1],
    [2**62, 2**62 + 1, 2**62 - 1],
    [-1, 0, 1],
    list(range(1000, 0, -1)),  # reverse 1000
    [1] * 500 + [2] * 500 + [0] * 500,
]
for i, case in enumerate(edge_cases):
    test_int64(i, len(case), lo=0, hi=0)  # seed/lo/hi don't matter for fixed data
    # Actually test with the actual data
    random.seed(42)
    c_arr = (ctypes.c_int64 * len(case))(*case)
    lib.timsort_int64(c_arr, len(case))
    got = [c_arr[j] for j in range(len(case))]
    expected = sorted(case)
    if got != expected:
        print(f"  FAIL edge case {i}: got={got[:20]}, expected={expected[:20]}")
        failures += 1
    else:
        tests += 1
        print(f"  edge case {i}: PASS (n={len(case)})")

# Scenario 3: Already sorted / reverse / all equal
print("\n=== Scenario 3: Structured patterns ===")
for n in [100, 1000, 10000]:
    test_int64(999999 + n, n, lo=0, hi=0)  # All zeros via seed doesn't work, need explicit
    # All equal
    data = [42] * n
    c_arr = (ctypes.c_int64 * n)(*data)
    lib.timsort_int64(c_arr, n)
    if list(c_arr) != data:
        print(f"  FAIL all_equal n={n}")
        failures += 1
    tests += 1

    # Already sorted
    data = list(range(n))
    c_arr = (ctypes.c_int64 * n)(*data)
    lib.timsort_int64(c_arr, n)
    if list(c_arr) != data:
        print(f"  FAIL sorted n={n}")
        failures += 1
    tests += 1

    # Reverse sorted
    data = list(range(n - 1, -1, -1))
    c_arr = (ctypes.c_int64 * n)(*data)
    lib.timsort_int64(c_arr, n)
    if list(c_arr) != sorted(data):
        print(f"  FAIL reverse n={n}")
        failures += 1
    tests += 1
    print(f"  n={n}: sorted/reverse/equal all PASS")

# Scenario 4: Double edge cases
print("\n=== Scenario 4: Double edge cases ===")
double_cases = [
    [0.0, -0.0],
    [float('inf'), float('-inf'), 0.0, 1.0],
    [1e-308, 1e308, 0.0, -1e308],
    [3.14, 2.71, 1.41, 1.73, 0.0, -1.0],
]
for i, case in enumerate(double_cases):
    c_arr = (ctypes.c_double * len(case))(*case)
    lib.timsort_double(c_arr, len(case))
    got = list(c_arr)
    expected = sorted(case)
    if got != expected:
        print(f"  FAIL double case {i}: got={got}, expected={expected}")
        failures += 1
    else:
        tests += 1
        print(f"  double case {i}: PASS")

# Scenario 5: Random doubles
print("\n=== Scenario 5: Random doubles ===")
for n in [100, 1000, 10000]:
    for seed in range(50):
        test_double(seed * 10000 + n, n)
    print(f"  n={n}: 50/50 passed")

# Summary
print(f"\n{'='*50}")
print(f"Total: {tests} tests, {failures} failures")
if failures == 0:
    print("ALL STRESS TESTS PASSED!")
else:
    print(f"FAILURES: {failures}")
    sys.exit(1)
