"""Profile sorted/reverse to find where CC is slower."""
import time

from timsort import timsort as timsort_orig, _count_run as orig_count_run
from timsort_cc import timsort as timsort_cc, _count_run as cc_count_run, _choose_min_merge as cc_choose

N = 10000

# Test _count_run on sorted data
data = list(range(N))

def bench_count_run(fn, data):
    s = time.perf_counter()
    for _ in range(50):
        fn(data, 0, len(data))
    return time.perf_counter() - s

orig_cr = bench_count_run(orig_count_run, data)
cc_cr = bench_count_run(cc_count_run, data)
print(f"_count_run (sorted {N}): orig={orig_cr*1000:.2f}ms, cc={cc_cr*1000:.2f}ms")

# Test _count_run on reverse data
rev = list(range(N, 0, -1))
orig_cr_rev = bench_count_run(orig_count_run, rev)
cc_cr_rev = bench_count_run(cc_count_run, rev)
print(f"_count_run (reverse {N}): orig={orig_cr_rev*1000:.2f}ms, cc={cc_cr_rev*1000:.2f}ms")

# Full sort comparison
data1 = list(range(N))
data2 = list(data1)
s = time.perf_counter()
timsort_orig(data1)
t1 = time.perf_counter() - s
s = time.perf_counter()
timsort_cc(data2)
t2 = time.perf_counter() - s
print(f"Full sort (sorted {N}): orig={t1*1000:.2f}ms, cc={t2*1000:.2f}ms")

# Check min_merge choices
print(f"\nmin_merge (sorted {N}): orig would use {_choose_min_merge_orig(data) if '_choose_min_merge_orig' in dir() else 'N/A'}")

# Time just the _choose_min_merge call
from timsort import _choose_min_merge as orig_choose
s = time.perf_counter()
for _ in range(100):
    orig_choose(data)
t1 = time.perf_counter() - s
s = time.perf_counter()
for _ in range(100):
    cc_choose(data, len(data))
t2 = time.perf_counter() - s
print(f"_choose_min_merge (sorted {N}): orig={t1*1000:.2f}ms, cc={t2*1000:.2f}ms")
