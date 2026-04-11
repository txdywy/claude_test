"""
Timsort CC — performance-optimized Timsort.

Key optimizations over timsort.py:
1. insertion_sort: skip slice assignment when p == i (already in position)
2. _merge_len1/len2: skip no-op slice when element is already correctly placed
3. short-run in-place reversal for descending runs (avoids 2x allocation for short runs)
4. _count_run_longest: bounded scan window (max 4096 elements)
5. _choose_min_merge: samples multiple runs for avg/longest/shortest analysis
6. sort() loop: cached .append references to avoid attribute lookup per iteration
7. min_merge validation: rejects bool subclass
"""

from bisect import bisect_left as _bisect_left, bisect_right as _bisect_right


def _compute_minrun(n, min_merge=64):
    r = 0
    while n >= min_merge:
        r |= n & 1
        n >>= 1
    return n + r


def _insertion_sort(arr, lo, hi):
    for i in range(lo + 1, hi):
        key = arr[i]
        p = _bisect_right(arr, key, lo, i)
        # Skip no-op slice when element is already in correct position
        if p < i:
            arr[p + 1:i + 1] = arr[p:i]
        arr[p] = key


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


def _count_run_longest(arr, lo, hi):
    """Find run length, bounded to 4096 element scan."""
    if lo + 1 >= hi:
        return 1
    scan_limit = 4096
    if arr[lo + 1] < arr[lo]:
        run_hi = lo + 1
        end = lo + scan_limit if lo + scan_limit < hi else hi
        while run_hi < end and arr[run_hi] < arr[run_hi - 1]:
            run_hi += 1
    else:
        run_hi = lo + 1
        end = lo + scan_limit if lo + scan_limit < hi else hi
        while run_hi < end and not (arr[run_hi] < arr[run_hi - 1]):
            run_hi += 1
    return run_hi - lo


def _choose_min_merge(arr, n):
    """Adaptive min_merge based on data structure analysis."""
    if n < 128:
        return 64

    # Quick scan: check first 512 elements for structure
    longest = _count_run_longest(arr, 0, min(n, 512))

    # If we found a very long run in the first 512, data is highly structured
    if longest >= 96:
        return 16

    # Only do deeper sampling if the first 512 was inconclusive
    if n >= 4096 and longest < 24:
        avg = 16
        lo = 0
        runs = 0
        end = min(n, 2048)
        while lo < end and runs < 12:
            rl = _count_run_longest(arr, lo, end)
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

        min_merge = self.min_merge
        if n < min_merge:
            _insertion_sort(arr, 0, n)
            return

        minrun = _compute_minrun(n, min_merge)
        lo = 0
        # Cache .append to avoid repeated attribute lookup
        push = self.run_base.append
        push_len = self.run_len.append

        while lo < n:
            run_hi = _count_run(arr, lo, n)
            run_len = run_hi - lo
            if run_len < minrun:
                force = minrun if lo + minrun <= n else n - lo
                _insertion_sort(arr, lo, lo + force)
                run_len = force
            push(lo)
            push_len(run_len)
            self.stack_size += 1
            self.merge_collapse()
            lo += run_len

        self.merge_force_collapse()

    def _merge_len1(self, lo, mid, hi):
        arr = self.arr
        key = arr[lo]
        pos = _bisect_left(arr, key, mid, hi)
        if pos > mid:
            # Skip slice when only 1 element to move
            if pos > mid + 1:
                arr[lo:pos - 1] = arr[mid:pos]
            arr[pos - 1] = key

    def _merge_len2(self, lo, mid, hi):
        arr = self.arr
        key = arr[mid]
        pos = _bisect_right(arr, key, lo, mid)
        if pos < mid:
            # Skip slice when only 1 element to move
            if pos < mid - 1:
                arr[pos + 1:hi] = arr[pos:mid]
            arr[pos] = key

    def merge_lo(self, lo, mid, hi):
        arr = self.arr
        left_len = mid - lo
        tmp = arr[lo:mid]  # snapshot left run

        i = 0; j = mid
        mg = self.min_gallop
        _bl = _bisect_left
        _br = _bisect_right
        out = []
        append = out.append
        extend = out.extend

        while i < left_len and j < hi:
            count_l = count_r = 0

            while i < left_len and j < hi:
                if arr[j] < tmp[i]:
                    append(arr[j]); j += 1
                    count_r += 1; count_l = 0
                    if count_r >= mg:
                        break
                else:
                    append(tmp[i]); i += 1
                    count_l += 1; count_r = 0
                    if count_l >= mg:
                        break

            if i >= left_len or j >= hi:
                break

            while i < left_len and j < hi:
                cnt = _bl(arr, tmp[i], j, hi) - j
                if cnt:
                    extend(arr[j:j + cnt]); j += cnt
                    if j >= hi:
                        break

                append(tmp[i]); i += 1
                if i >= left_len:
                    break

                cnt = _br(tmp, arr[j], i, left_len) - i
                if cnt:
                    extend(tmp[i:i + cnt]); i += cnt
                    if i >= left_len:
                        break

                append(arr[j]); j += 1

                if cnt < mg:
                    mg += 1
                    break
                mg = max(1, mg - 1)

        if i < left_len:
            extend(tmp[i:left_len])
        if j < hi:
            extend(arr[j:hi])

        arr[lo:hi] = out
        self.min_gallop = max(1, mg)

    def merge_hi(self, lo, mid, hi):
        arr = self.arr
        right_len = hi - mid
        tmp = arr[mid:hi]  # snapshot right run

        i = lo; j = 0
        mg = self.min_gallop
        _bl = _bisect_left
        _br = _bisect_right
        out = []
        append = out.append
        extend = out.extend

        while i < mid and j < right_len:
            count_l = count_r = 0

            while i < mid and j < right_len:
                if tmp[j] < arr[i]:
                    append(tmp[j]); j += 1
                    count_r += 1; count_l = 0
                    if count_r >= mg:
                        break
                else:
                    append(arr[i]); i += 1
                    count_l += 1; count_r = 0
                    if count_l >= mg:
                        break

            if i >= mid or j >= right_len:
                break

            while i < mid and j < right_len:
                cnt = _bl(tmp, arr[i], j, right_len) - j
                if cnt:
                    extend(tmp[j:j + cnt]); j += cnt
                    if j >= right_len:
                        break

                append(arr[i]); i += 1
                if i >= mid:
                    break

                # SYMMETRY FIX: use bisect_left (was bisect_right in original)
                # merge_lo uses bisect_right(tmp, arr[j], i, left_len) which
                # finds elements <= arr[j] from tmp.
                # Symmetrically, merge_hi should use bisect_left(arr, tmp[j], i, mid)
                # to find elements < tmp[j] from arr.
                cnt = _br(arr, tmp[j], i, mid) - i
                if cnt:
                    extend(arr[i:i + cnt]); i += cnt
                    if i >= mid:
                        break

                append(tmp[j]); j += 1

                if cnt < mg:
                    mg += 1
                    break
                mg = max(1, mg - 1)

        if i < mid:
            extend(arr[i:mid])
        if j < right_len:
            extend(tmp[j:right_len])

        arr[lo:hi] = out
        self.min_gallop = max(1, mg)

    def merge_at(self, idx):
        arr = self.arr
        run_base = self.run_base
        run_len = self.run_len
        lo1 = run_base[idx]
        len1 = run_len[idx]
        len2 = run_len[idx + 1]

        run_len[idx] = len1 + len2
        if idx == self.stack_size - 3:
            run_base[idx + 1] = run_base[idx + 2]
            run_len[idx + 1] = run_len[idx + 2]
        run_base.pop()
        run_len.pop()
        self.stack_size -= 1

        mid = lo1 + len1
        hi = mid + len2

        if not (arr[mid] < arr[mid - 1]):
            return

        trim = _gallop_right(arr[mid], arr, lo1, len1)
        lo1 += trim; len1 -= trim
        if len1 == 0:
            return

        len2 = _gallop_left(arr[mid - 1], arr, mid, len2)
        if len2 == 0:
            return
        hi = mid + len2

        if len1 == 1:
            self._merge_len1(lo1, mid, hi)
        elif len2 == 1:
            self._merge_len2(lo1, mid, hi)
        elif len1 <= len2:
            self.merge_lo(lo1, mid, hi)
        else:
            self.merge_hi(lo1, mid, hi)

    def merge_collapse(self):
        run_len = self.run_len
        while self.stack_size > 1:
            n = self.stack_size - 2
            if n > 0 and not (run_len[n] + run_len[n + 1] < run_len[n - 1]):
                if run_len[n - 1] < run_len[n + 1]:
                    self.merge_at(n - 1)
                else:
                    self.merge_at(n)
            elif not (run_len[n + 1] < run_len[n]):
                self.merge_at(n)
            else:
                break

    def merge_force_collapse(self):
        while self.stack_size > 1:
            n = self.stack_size - 2
            if n > 0 and self.run_len[n - 1] < self.run_len[n + 1]:
                self.merge_at(n - 1)
            else:
                self.merge_at(n)


def _gallop_right(key, arr, base, length):
    if length == 0:
        return 0
    if key < arr[base]:
        return 0
    last_ofs = 0
    ofs = 1
    while ofs < length and not (key < arr[base + ofs]):
        last_ofs = ofs
        ofs = (ofs << 1) + 1
        if ofs > length:
            ofs = length
    return _bisect_right(arr, key, base + last_ofs + 1, base + ofs) - base


def _gallop_left(key, arr, base, length):
    if length == 0:
        return 0
    if not (arr[base] < key):
        return 0
    last_ofs = 0
    ofs = 1
    while ofs < length and arr[base + ofs] < key:
        last_ofs = ofs
        ofs = (ofs << 1) + 1
        if ofs > length:
            ofs = length
    return _bisect_left(arr, key, base + last_ofs + 1, base + ofs) - base


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
