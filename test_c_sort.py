"""Quick correctness test for the C sort library."""
import ctypes
import random
import sys
from pathlib import Path

lib_path = Path(__file__).parent / "libsort_c.dylib"
lib = ctypes.CDLL(str(lib_path))

lib.timsort_int64.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.c_size_t]
lib.timsort_int64.restype = ctypes.c_int

lib.timsort_double.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_size_t]
lib.timsort_double.restype = ctypes.c_int

lib.is_sorted_int64.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.c_size_t]
lib.is_sorted_int64.restype = ctypes.c_int


def sort_int64(arr):
    n = len(arr)
    Arr = ctypes.c_int64 * n
    c_arr = Arr(*arr)
    ret = lib.timsort_int64(c_arr, n)
    assert ret == 0, f"timsort_int64 returned {ret}"
    return [c_arr[i] for i in range(n)]


def sort_double(arr):
    n = len(arr)
    Arr = ctypes.c_double * n
    c_arr = Arr(*arr)
    ret = lib.timsort_double(c_arr, n)
    assert ret == 0, f"timsort_double returned {ret}"
    return [c_arr[i] for i in range(n)]


def test(name, fn, data):
    expected = sorted(data)
    result = fn(data[:])
    if result != expected:
        print(f"FAIL {name}: input={data[:20]}... expected={expected[:20]}... got={result[:20]}...")
        return False
    print(f"  PASS {name}")
    return True


ok = True

# Basic tests
ok &= test("empty", sort_int64, [])
ok &= test("single", sort_int64, [42])
ok &= test("two", sort_int64, [2, 1])
ok &= test("sorted", sort_int64, [1, 2, 3, 4, 5])
ok &= test("reverse", sort_int64, [5, 4, 3, 2, 1])
ok &= test("all_equal", sort_int64, [3, 3, 3, 3, 3])
ok &= test("duplicates", sort_int64, [3, 1, 3, 1, 2, 3, 2, 1])

# Boundary sizes
for sz in [31, 32, 33, 63, 64, 65, 127, 128, 129, 255, 256, 257]:
    random.seed(42)
    data = [random.randint(-1000, 1000) for _ in range(sz)]
    ok &= test(f"random_{sz}", sort_int64, data)

# Already sorted
ok &= test("sorted_1000", sort_int64, list(range(1000)))

# Reverse sorted
ok &= test("reverse_1000", sort_int64, list(range(999, -1, -1)))

# Pipe organ
ok &= test("pipe_organ_1000", sort_int64, list(range(500)) + list(range(500, 0, -1)))

# Few unique
random.seed(99)
ok &= test("few_unique_1000", sort_int64,
           [random.randint(0, 5) for _ in range(1000)])

# Large random
random.seed(123)
ok &= test("random_10000", sort_int64,
           [random.randint(-100000, 100000) for _ in range(10000)])

# Negative numbers
ok &= test("negatives", sort_int64, [-5, -1, -10, -3, -7, -2])

# --- Double tests ---
ok &= test("dbl_basic", sort_double, [3.14, 1.59, 2.65, 0.0, -1.0])
ok &= test("dbl_sorted", sort_double, [0.0, 1.1, 2.2, 3.3])
ok &= test("dbl_reverse", sort_double, [3.3, 2.2, 1.1, 0.0])
ok &= test("dbl_equal", sort_double, [1.5, 1.5, 1.5])

random.seed(77)
ok &= test("dbl_random_1000", sort_double,
           [random.uniform(-1e6, 1e6) for _ in range(1000)])

# Stability test: sort (value, index) pairs using generic sort
lib.timsort_generic.argtypes = [
    ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p
]
lib.timsort_generic.restype = ctypes.c_int

class Pair(ctypes.Structure):
    _fields_ = [("val", ctypes.c_int64), ("idx", ctypes.c_int64)]

CMP_FUNC = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(Pair), ctypes.POINTER(Pair))

@CMP_FUNC
def pair_cmp(a, b):
    if a.contents.val < b.contents.val: return -1
    if a.contents.val > b.contents.val: return 1
    return 0

def sort_pairs(data):
    n = len(data)
    Arr = Pair * n
    c_arr = Arr()
    for i, (v, idx) in enumerate(data):
        c_arr[i].val = v
        c_arr[i].idx = idx
    ret = lib.timsort_generic(ctypes.byref(c_arr), n, ctypes.sizeof(Pair), pair_cmp)
    assert ret == 0
    return [(c_arr[i].val, c_arr[i].idx) for i in range(n)]

# Stability: equal values should preserve original order
pairs = [(3, 0), (1, 1), (3, 2), (1, 3), (2, 4), (3, 5)]
result = sort_pairs(pairs)
expected = [(1, 1), (1, 3), (2, 4), (3, 0), (3, 2), (3, 5)]
if result == expected:
    print("  PASS stability")
else:
    print(f"  FAIL stability: expected={expected} got={result}")
    ok = False

# Stability with many equal keys
random.seed(55)
pairs2 = [(random.randint(0, 3), i) for i in range(200)]
result2 = sort_pairs(pairs2)
# Check stability: for equal values, idx should be increasing
prev_val = None
prev_idx = -1
stable = True
for v, idx in result2:
    if v == prev_val and idx < prev_idx:
        stable = False
        break
    prev_val = v
    prev_idx = idx
if stable:
    print("  PASS stability_large")
else:
    print("  FAIL stability_large")
    ok = False

if ok:
    print("\nAll tests PASSED!")
    sys.exit(0)
else:
    print("\nSome tests FAILED!")
    sys.exit(1)
