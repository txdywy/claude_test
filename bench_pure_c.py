"""Final benchmark: pure C vs Python with minimal overhead."""
import array
import ctypes
import random
import timeit

lib = ctypes.CDLL('./libsort_c.dylib')
lib.timsort_int64.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.c_size_t]
lib.timsort_int64.restype = ctypes.c_int
lib.timsort_double.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_size_t]
lib.timsort_double.restype = ctypes.c_int

TIMES = 10


def _get_ptr(arr):
    """Get pointer to array.array buffer."""
    buf = (ctypes.c_char * (len(arr) * arr.itemsize)).from_buffer(arr)
    return ctypes.cast(buf, ctypes.c_void_p).value


def bench_scenario(name, typecode, data_gen, c_func, sizes):
    print(f"\n{'='*70}")
    print(f"  {name}")
    print(f"{'='*70}")
    print(f"{'Size':>10}  {'C sort (ms)':>12}  {'Python (ms)':>12}  {'C Speedup':>10}")
    print(f"{'-'*50}")

    for n in sizes:
        random.seed(42)
        data = data_gen(n)
        arr = array.array(typecode, data)

        # Pre-create mutable copy for C
        arr_c = array.array(typecode, data)

        # Time only the C sort (data already in array)
        def sort_c():
            # Reset: copy from original
            arr_c[:] = arr[:]
            c_func(arr_c)

        t_c = timeit.timeit(sort_c, number=TIMES) / TIMES * 1000

        # Python sort
        def sort_py():
            sorted(data[:])

        t_py = timeit.timeit(sort_py, number=TIMES) / TIMES * 1000

        speedup = t_py / t_c if t_c > 0 else 0
        print(f"{n:>10}  {t_c:>12.4f}  {t_py:>12.4f}  {speedup:>9.2f}x")


from sort_wrapper import c_sort_array

bench_scenario("Random int64", 'q',
    lambda n: [random.randint(-10**9, 10**9) for _ in range(n)],
    c_sort_array, [1_000, 10_000, 100_000, 1_000_000])

bench_scenario("Already sorted", 'q',
    lambda n: list(range(n)),
    c_sort_array, [1_000, 10_000, 100_000, 1_000_000])

bench_scenario("Reverse sorted", 'q',
    lambda n: list(range(n - 1, -1, -1)),
    c_sort_array, [1_000, 10_000, 100_000, 1_000_000])

bench_scenario("All equal", 'q',
    lambda n: [42] * n,
    c_sort_array, [1_000, 10_000, 100_000, 1_000_000])

bench_scenario("Few unique (0-9)", 'q',
    lambda n: [random.randint(0, 9) for _ in range(n)],
    c_sort_array, [1_000, 10_000, 100_000, 1_000_000])

bench_scenario("Random double", 'd',
    lambda n: [random.uniform(-1e9, 1e9) for _ in range(n)],
    c_sort_array, [1_000, 10_000, 100_000, 1_000_000])
