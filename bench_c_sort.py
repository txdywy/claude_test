"""Benchmark C Timsort vs Python's built-in sort."""
import array
import random
import timeit
import sys
from sort_wrapper import c_sort_array

TIMES = 5


def bench_array(name, typecode, data_gen, sizes):
    """Benchmark using array.array zero-copy path."""
    print(f"\n{'='*65}")
    print(f"  {name} (array.array zero-copy)")
    print(f"{'='*65}")
    print(f"{'Size':>8}  {'C array (ms)':>12}  {'Python (ms)':>12}  {'Speedup':>8}")
    print(f"{'-'*46}")

    for n in sizes:
        random.seed(42)
        data = data_gen(n)
        arr = array.array(typecode, data)

        # C sort (zero-copy via array.array)
        def sort_c():
            c = array.array(typecode, data)
            c_sort_array(c)

        t_c = timeit.timeit(sort_c, number=TIMES) / TIMES

        # Python sort
        def sort_py():
            sorted(data[:])

        t_py = timeit.timeit(sort_py, number=TIMES) / TIMES

        speedup = t_py / t_c if t_c > 0 else float('inf')
        print(f"{n:>8}  {t_c*1000:>12.3f}  {t_py*1000:>12.3f}  {speedup:>7.2f}x")


def random_data(n):
    random.seed(42)
    return [random.randint(-10**9, 10**9) for _ in range(n)]


def sorted_data(n):
    return list(range(n))


def reverse_data(n):
    return list(range(n - 1, -1, -1))


def few_unique_data(n):
    random.seed(42)
    return [random.randint(0, 9) for _ in range(n)]


def all_equal_data(n):
    return [42] * n


sizes = [1_000, 10_000, 100_000, 1_000_000]

bench_array("Random int64", 'q', random_data, sizes)
bench_array("Already sorted", 'q', sorted_data, sizes)
bench_array("Reverse sorted", 'q', reverse_data, sizes)
bench_array("Few unique (0-9)", 'q', few_unique_data, sizes)
bench_array("All equal", 'q', all_equal_data, sizes)

# Double benchmarks
print(f"\n{'='*65}")
print(f"  Double benchmarks (array.array zero-copy)")
print(f"{'='*65}")
print(f"{'Size':>8}  {'C array (ms)':>12}  {'Python (ms)':>12}  {'Speedup':>8}")
print(f"{'-'*46}")

for name, gen in [("Random double", lambda n: [random.uniform(-1e9, 1e9) for _ in range(n)]),
                   ("Sorted double", lambda n: [float(i) for i in range(n)])]:
    for n in sizes:
        random.seed(42)
        data = gen(n)
        arr = array.array('d', data)

        def sort_c():
            c = array.array('d', data)
            c_sort_array(c)

        def sort_py():
            sorted(data[:])

        t_c = timeit.timeit(sort_c, number=TIMES) / TIMES
        t_py = timeit.timeit(sort_py, number=TIMES) / TIMES
        speedup = t_py / t_c if t_c > 0 else float('inf')
        print(f"{n:>8}  {t_c*1000:>12.3f}  {t_py*1000:>12.3f}  {speedup:>7.2f}x")
