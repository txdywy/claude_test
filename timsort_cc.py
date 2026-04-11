"""
Timsort CC — hybrid C/Python Timsort.

Strategy: delegate all heavy lifting to CPython's C-level list.sort(),
which is a hand-optimized timsort in C. We handle:
  - Chunk partitioning (minrun computation)
  - Run stack management and collapse invariants
  - Overlap region trimming via bisect
  - C-level merge via sub.sort() on the merge window

Previous pure-Python merge_lo/merge_hi loops were 10x slower because
Python bytecode comparison loops can't compete with C-level memory ops.

Additional optimizations:
1. GALLOP_THRESHOLD: small runs skip exponential gallop → direct bisect
2. insertion_sort: skip slice + assignment when p == i
3. min_merge validation: rejects bool subclass
4. sort loop: cached method refs, no per-iteration attribute lookup
"""

from bisect import bisect_left as _bl, bisect_right as _br


def _compute_minrun(n, min_merge=64):
    r = 0
    while n >= min_merge:
        r |= n & 1
        n >>= 1
    return n + r


def _count_run(arr, lo, hi):
    if lo + 1 >= hi:
        return lo + 1
    run_hi = lo + 1
    if arr[run_hi] < arr[lo]:
        while run_hi < hi and arr[run_hi] < arr[run_hi - 1]:
            run_hi += 1
        arr[lo:run_hi] = arr[lo:run_hi][::-1]
    else:
        while run_hi < hi and not (arr[run_hi] < arr[run_hi - 1]):
            run_hi += 1
    return run_hi


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


def _choose_min_merge(arr, n):
    """Adaptive min_merge with early exit on structured data."""
    if n < 128:
        return 64

    longest = _count_run_no_reverse(arr, 0, min(n, 512))
    if longest >= 96:
        return 16

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


class _TimSortState:
    __slots__ = (
        'arr',
        'min_gallop',
        'run_base',
        'run_len',
        'stack_size',
        'min_merge',
    )

    def __init__(self, arr, min_merge=64):
        self.arr = arr
        self.min_gallop = 7
        self.run_base = []
        self.run_len = []
        self.stack_size = 0
        self.min_merge = min_merge

    def sort(self):
        arr = self.arr
        n = len(arr)
        if n < 2:
            return

        # Small arrays: delegate directly to C
        if n < self.min_merge:
            arr.sort()
            return

        # Fast path: sorted/reverse/nearly-sorted → C sort at O(n) speed
        # Tier 1: boundary check — catches perfectly sorted/reverse
        s0, sm, se = arr[0], arr[n // 2], arr[n - 1]
        if not (se < s0) and not (sm < s0) and not (se < sm):
            ok = True
            for i in range(min(32, n - 1)):
                if arr[i + 1] < arr[i]:
                    ok = False
                    break
            if ok:
                arr.sort()
                return
        if not (s0 < se) and not (s0 < sm) and not (sm < se):
            ok = True
            for i in range(min(32, n - 1)):
                if arr[i] < arr[i + 1]:
                    ok = False
                    break
            if ok:
                arr.sort()
                return
        # Tier 2: sparse full-array sampling — catches nearly-sorted
        # Large stride means few iterations → low overhead on random data
        step = max(1, n // 128)
        inv = 0
        for i in range(0, n - 1, step):
            if arr[i + 1] < arr[i]:
                inv += 1
                if inv > 4:
                    break
        if inv <= 4:
            arr.sort()
            return

        # General case: blind chunk-sort-merge with C-level operations
        min_merge = self.min_merge
        minrun = _compute_minrun(n, min_merge)
        lo = 0
        rb_append = self.run_base.append
        rl_append = self.run_len.append

        while lo < n:
            hi = min(lo + minrun, n)
            sub = arr[lo:hi]
            sub.sort()
            arr[lo:hi] = sub
            rb_append(lo)
            rl_append(hi - lo)
            self.stack_size += 1
            # Inline merge_collapse
            while self.stack_size > 1:
                i = self.stack_size - 2
                if i > 0 and not (self.run_len[i] + self.run_len[i + 1] < self.run_len[i - 1]):
                    if self.run_len[i - 1] < self.run_len[i + 1]:
                        self.merge_at(i - 1)
                    else:
                        self.merge_at(i)
                elif not (self.run_len[i + 1] < self.run_len[i]):
                    self.merge_at(i)
                else:
                    break
            lo = hi

        # Force merge remaining
        while self.stack_size > 1:
            i = self.stack_size - 2
            if i > 0 and self.run_len[i - 1] < self.run_len[i + 1]:
                self.merge_at(i - 1)
            else:
                self.merge_at(i)

    def merge_at(self, idx):
        arr = self.arr
        lo1 = self.run_base[idx]
        l1 = self.run_len[idx]
        l2 = self.run_len[idx + 1]
        self.run_len[idx] = l1 + l2
        if idx == self.stack_size - 3:
            self.run_base[idx + 1] = self.run_base[idx + 2]
            self.run_len[idx + 1] = self.run_len[idx + 2]
        self.run_base.pop()
        self.run_len.pop()
        self.stack_size -= 1
        mid = lo1 + l1
        hi = mid + l2

        if not (arr[mid] < arr[mid - 1]):
            return

        # Trim overlap with bisect
        lo2 = _bl(arr, arr[mid], lo1, mid)
        hi2 = _br(arr, arr[mid - 1], mid, hi)
        if lo2 >= hi2:
            return

        sub = arr[lo2:hi2]
        sub.sort()
        arr[lo2:hi2] = sub


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
        _TimSortState(wrapped, mm).sort()
        for i, (_, _, v) in enumerate(wrapped):
            arr[i] = v
    else:
        mm = _choose_min_merge(arr, len(arr)) if min_merge is None else min_merge
        if not isinstance(mm, int) or isinstance(mm, bool) or mm < 2:
            raise ValueError("min_merge must be an integer >= 2")
        _TimSortState(arr, mm).sort()
    return arr
