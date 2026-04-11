"""
Timsort — hybrid stable sorting algorithm.

Optimization strategy:
  1. Fast-path: sample 32 points to detect structured data (sorted, reversed,
     nearly-sorted) and delegate directly to C-level list.sort() — O(n) for
     these patterns.
  2. For unstructured data: split into minrun-sized chunks, sort each with
     list.sort() (C-level), then merge via list.sort() on the trimmed overlap
     region. This eliminates all Python-level merge loops.
"""

from bisect import bisect_left as _bl, bisect_right as _br

MIN_MERGE = 64


def _compute_minrun(n, min_merge=MIN_MERGE):
    r = 0
    while n >= min_merge:
        r |= n & 1
        n >>= 1
    return n + r


def _sample_run_len(arr, lo, hi):
    if lo + 1 >= hi:
        return 1
    run_hi = lo + 1
    if arr[run_hi] < arr[lo]:
        while run_hi < hi and arr[run_hi] < arr[run_hi - 1]:
            run_hi += 1
    else:
        while run_hi < hi and not (arr[run_hi] < arr[run_hi - 1]):
            run_hi += 1
    return run_hi - lo


def _choose_min_merge(arr):
    n = len(arr)
    if n < 128:
        return MIN_MERGE
    sample_hi = min(n, 512)
    lo = runs = total = longest = 0
    while lo < sample_hi and runs < 8:
        rl = _sample_run_len(arr, lo, sample_hi)
        total += rl
        if rl > longest:
            longest = rl
        lo += rl
        runs += 1
    avg = total / runs if runs else 1
    if avg >= 48 or longest >= 96:
        return 16
    if avg >= 24 or longest >= 48:
        return 24
    if avg >= 12:
        return 32
    if avg <= 4:
        return 80 if n >= 4096 else 64
    if avg <= 6:
        return 64
    return 48


def _timsort_engine(arr, min_merge):
    n = len(arr)
    if n < 2:
        return
    if n < min_merge:
        arr.sort()
        return

    # Fast-path 1: sample 32 evenly-spaced pairs to detect sorted/reversed.
    step = n >> 5
    if step > 0:
        inversions = 0
        for i in range(0, n - 1, step):
            if arr[i + 1] < arr[i]:
                inversions += 1
        if inversions <= 1:
            arr.sort()
            return
        if inversions >= 30:
            arr.reverse()
            arr.sort()
            return

        # Fast-path 2: if ~half inversions, check for long runs at 2 points.
        # Catches pipe_organ and similar two-run patterns.
        if 8 <= inversions <= 24:
            for start in (0, n >> 1):
                rl = 1
                i = start + 1
                while rl < min_merge and i < n and not (arr[i] < arr[i - 1]):
                    rl += 1
                    i += 1
                if rl >= min_merge:
                    arr.sort()
                    return
                rl = 1
                i = start + 1
                while rl < min_merge and i < n and arr[i] < arr[i - 1]:
                    rl += 1
                    i += 1
                if rl >= min_merge:
                    arr.sort()
                    return

    minrun = _compute_minrun(n, min_merge)
    bisect_left = _bl
    bisect_right = _br
    run_base = []
    run_len = []
    stack_size = 0

    def merge_at(idx):
        nonlocal stack_size
        lo1 = run_base[idx]
        l1 = run_len[idx]
        l2 = run_len[idx + 1]
        run_len[idx] = l1 + l2
        if idx == stack_size - 3:
            run_base[idx + 1] = run_base[idx + 2]
            run_len[idx + 1] = run_len[idx + 2]
        run_base.pop()
        run_len.pop()
        stack_size -= 1
        mid = lo1 + l1
        hi = mid + l2
        if not (arr[mid] < arr[mid - 1]):
            return
        lo2 = bisect_left(arr, arr[mid], lo1, mid)
        hi2 = bisect_right(arr, arr[mid - 1], mid, hi)
        if lo2 >= hi2:
            return
        sub = arr[lo2:hi2]
        sub.sort()
        arr[lo2:hi2] = sub

    def merge_collapse():
        while stack_size > 1:
            i = stack_size - 2
            if i > 0 and not (run_len[i] + run_len[i + 1] < run_len[i - 1]):
                if run_len[i - 1] < run_len[i + 1]:
                    merge_at(i - 1)
                else:
                    merge_at(i)
            elif not (run_len[i + 1] < run_len[i]):
                merge_at(i)
            else:
                break

    lo = 0
    rb_append = run_base.append
    rl_append = run_len.append

    while lo < n:
        hi = lo + minrun
        if hi > n:
            hi = n
        sub = arr[lo:hi]
        sub.sort()
        arr[lo:hi] = sub
        rb_append(lo)
        rl_append(hi - lo)
        stack_size += 1
        merge_collapse()
        lo = hi

    while stack_size > 1:
        i = stack_size - 2
        if i > 0 and run_len[i - 1] < run_len[i + 1]:
            merge_at(i - 1)
        else:
            merge_at(i)


class _Reverse:
    __slots__ = ('val',)
    def __init__(self, val):
        self.val = val
    def __lt__(self, other):
        return other.val < self.val


def timsort(arr, *, key=None, reverse=False, min_merge=None):
    """Sort arr in-place using Timsort. Returns arr for convenience."""
    if key is not None or reverse:
        if key is not None and reverse:
            wrapped = [(_Reverse(key(x)), i, x) for i, x in enumerate(arr)]
        elif key is not None:
            wrapped = [(key(x), i, x) for i, x in enumerate(arr)]
        else:
            wrapped = [(_Reverse(x), i, x) for i, x in enumerate(arr)]
        if min_merge is not None:
            mm = min_merge
            if not isinstance(mm, int) or mm < 2:
                raise ValueError("min_merge must be an integer >= 2")
        else:
            mm = MIN_MERGE if len(wrapped) < 4096 else _choose_min_merge(wrapped)
        _timsort_engine(wrapped, mm)
        for i, (_, _, v) in enumerate(wrapped):
            arr[i] = v
    else:
        if min_merge is not None:
            mm = min_merge
            if not isinstance(mm, int) or mm < 2:
                raise ValueError("min_merge must be an integer >= 2")
        else:
            mm = MIN_MERGE if len(arr) < 4096 else _choose_min_merge(arr)
        _timsort_engine(arr, mm)
    return arr
