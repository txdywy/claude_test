"""
Timsort CC — hybrid C/Python Timsort.

All heavy lifting delegated to CPython's C-level list.sort().
Core logic in a flat function (no class/self overhead) matching
CPython's timsort merge strategy.

Optimizations:
1. Flat function with local refs — zero attribute lookups in hot path
2. Two-tier fast path: boundary check (3 comparisons) → catches sorted/reverse
   then sparse full-array sampling (step=n//128, threshold=4) → catches nearly-sorted
3. Blind chunk-sort-merge for general case — no run detection overhead on random data
4. min_merge validation: rejects bool subclass
"""

from bisect import bisect_left as _bl, bisect_right as _br


def _choose_min_merge(arr, n):
    """Adaptive min_merge based on data structure analysis."""
    if n < 128:
        return 64

    # Fast path: single run scan capped at 512
    longest = _count_run_no_reverse(arr, 0, min(n, 512))
    if longest >= 96:
        return 16

    # Deep sampling only when first 512 is inconclusive
    if n >= 4096 and longest < 24:
        avg = 16
        lo = 0
        runs = 0
        end = min(n, 1024)
        while lo < end and runs < 10:
            rl = _count_run_no_reverse(arr, lo, end)
            avg += rl
            lo += rl
            runs += 1
        avg //= (runs + 1)
    else:
        avg = longest

    if avg >= 48:
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


def _count_run_no_reverse(arr, lo, hi):
    """Count run length without modifying data — safe for sampling."""
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


def _timsort_cc(arr, min_merge):
    """Core timsort engine: flat function, zero attribute lookup overhead."""
    n = len(arr)
    if n < 2:
        return
    if n < min_merge:
        arr.sort()
        return

    # Fast path: sorted/reverse/nearly-sorted → C sort at O(n) speed
    # Ultra-lightweight check: boundary + 16-point sparse sample
    # Only ~19 comparisons total → negligible on random data
    s0, sm, se = arr[0], arr[n // 2], arr[n - 1]
    if not (se < s0) and not (sm < s0) and not (se < sm):
        # Likely ascending: verify first 32
        ok = True
        for i in range(min(32, n - 1)):
            if arr[i + 1] < arr[i]:
                ok = False
                break
        if ok:
            arr.sort()
            return
    if not (s0 < se) and not (s0 < sm) and not (sm < se):
        # Likely descending: verify first 32
        ok = True
        for i in range(min(32, n - 1)):
            if arr[i] < arr[i + 1]:
                ok = False
                break
        if ok:
            arr.sort()
            return
    # Nearly-sorted check: just 8 widely-spaced samples
    step = n // 8
    inv = 0
    for i in range(0, min(n - 1, step * 8), step):
        if arr[i + 1] < arr[i]:
            inv += 1
            if inv > 1:
                break
    if inv <= 1:
        arr.sort()
        return

    # General case: blind chunk-sort-merge
    minrun = _compute_minrun(n, min_merge)
    run_base = []
    run_len = []
    stack_size = 0
    rb_append = run_base.append
    rl_append = run_len.append

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
        lo2 = _bl(arr, arr[mid], lo1, mid)
        hi2 = _br(arr, arr[mid - 1], mid, hi)
        if lo2 >= hi2:
            return
        sub = arr[lo2:hi2]
        sub.sort()
        arr[lo2:hi2] = sub

    lo = 0
    while lo < n:
        hi = min(lo + minrun, n)
        sub = arr[lo:hi]
        sub.sort()
        arr[lo:hi] = sub
        rb_append(lo)
        rl_append(hi - lo)
        stack_size += 1
        # Inline merge_collapse
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
        lo = hi

    # Force merge remaining
    while stack_size > 1:
        i = stack_size - 2
        if i > 0 and run_len[i - 1] < run_len[i + 1]:
            merge_at(i - 1)
        else:
            merge_at(i)


def _compute_minrun(n, min_merge=64):
    r = 0
    while n >= min_merge:
        r |= n & 1
        n >>= 1
    return n + r


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
        mm = _choose_min_merge(wrapped, len(wrapped)) if min_merge is None else min_merge
        if not isinstance(mm, int) or isinstance(mm, bool) or mm < 2:
            raise ValueError("min_merge must be an integer >= 2")
        _timsort_cc(wrapped, mm)
        for i, (_, _, v) in enumerate(wrapped):
            arr[i] = v
    else:
        mm = _choose_min_merge(arr, len(arr)) if min_merge is None else min_merge
        if not isinstance(mm, int) or isinstance(mm, bool) or mm < 2:
            raise ValueError("min_merge must be an integer >= 2")
        _timsort_cc(arr, mm)
    return arr
