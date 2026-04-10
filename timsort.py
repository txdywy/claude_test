"""
Timsort — a hybrid stable sorting algorithm combining merge sort and insertion sort.
Performance-optimized pure Python: inlined gallop, bisect for binary search,
append+writeback merge, aggressive local variable caching.
All comparisons use only < for __lt__ compatibility.
"""

from bisect import bisect_left as _bisect_left, bisect_right as _bisect_right

MIN_MERGE = 64
MIN_GALLOP = 7


def _compute_minrun(n, min_merge=MIN_MERGE):
    r = 0
    while n >= min_merge:
        r |= n & 1
        n >>= 1
    return n + r


def _insertion_sort(arr, lo, hi):
    for i in range(lo + 1, hi):
        key = arr[i]
        # bisect_right gives us the insertion point (C-implemented)
        p = _bisect_right(arr, key, lo, i)
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


# Standalone gallop functions — used only in merge_at for run trimming.
# Inside merge_lo/merge_hi, gallop is fully inlined to avoid call overhead.

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
    # Use C bisect for the binary search phase
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


class _TimSortState:
    __slots__ = ('arr', 'tmp', 'min_gallop', 'stack', 'min_merge')

    def __init__(self, arr, min_merge=MIN_MERGE):
        self.arr = arr
        self.tmp = []
        self.min_gallop = MIN_GALLOP
        self.stack = []
        self.min_merge = min_merge

    def _ensure_tmp(self, needed):
        if len(self.tmp) < needed:
            self.tmp = [None] * needed

    def merge_lo(self, lo, mid, hi):
        arr = self.arr
        left_len = mid - lo
        self._ensure_tmp(left_len)
        tmp = self.tmp
        tmp[:left_len] = arr[lo:mid]

        # Cache everything as locals
        i = 0; j = mid; k = lo
        mg = self.min_gallop
        _bl = _bisect_left
        _br = _bisect_right

        while i < left_len and j < hi:
            count_l = count_r = 0

            # --- One-pair-at-a-time ---
            while i < left_len and j < hi:
                if arr[j] < tmp[i]:
                    arr[k] = arr[j]; k += 1; j += 1
                    count_r += 1; count_l = 0
                    if count_r >= mg:
                        break
                else:
                    arr[k] = tmp[i]; k += 1; i += 1
                    count_l += 1; count_r = 0
                    if count_l >= mg:
                        break

            if i >= left_len or j >= hi:
                break

            # --- Inlined galloping ---
            while i < left_len and j < hi:
                # Gallop left[i] into right run: find how many right < left[i]
                # Inline _gallop_left(tmp[i], arr, j, hi-j)
                key = tmp[i]
                if arr[j] < key:
                    ofs = 1; last_ofs = 0; length = hi - j
                    while ofs < length and arr[j + ofs] < key:
                        last_ofs = ofs
                        ofs = (ofs << 1) + 1
                        if ofs > length:
                            ofs = length
                    cnt = _bl(arr, key, j + last_ofs + 1, j + ofs) - j
                else:
                    cnt = 0

                if cnt:
                    arr[k:k + cnt] = arr[j:j + cnt]
                    k += cnt; j += cnt
                    if j >= hi:
                        break

                arr[k] = tmp[i]; k += 1; i += 1
                if i >= left_len:
                    break

                # Gallop right[j] into left run: find how many left <= right[j]
                # Inline _gallop_right(arr[j], tmp, i, left_len-i)
                key = arr[j]
                if not (key < tmp[i]):
                    ofs = 1; last_ofs = 0; length = left_len - i
                    while ofs < length and not (key < tmp[i + ofs]):
                        last_ofs = ofs
                        ofs = (ofs << 1) + 1
                        if ofs > length:
                            ofs = length
                    cnt = _br(tmp, key, i + last_ofs + 1, i + ofs) - i
                else:
                    cnt = 0

                if cnt:
                    arr[k:k + cnt] = tmp[i:i + cnt]
                    k += cnt; i += cnt
                    if i >= left_len:
                        break

                arr[k] = arr[j]; k += 1; j += 1

                if cnt < mg:
                    mg += 1
                    break
                mg = max(1, mg - 1)

        if i < left_len:
            arr[k:k + left_len - i] = tmp[i:left_len]

        self.min_gallop = max(1, mg)

    def merge_hi(self, lo, mid, hi):
        arr = self.arr
        right_len = hi - mid
        self._ensure_tmp(right_len)
        tmp = self.tmp
        tmp[:right_len] = arr[mid:hi]

        i = mid - 1; j = right_len - 1; k = hi - 1
        mg = self.min_gallop
        _bl = _bisect_left
        _br = _bisect_right

        while i >= lo and j >= 0:
            count_l = count_r = 0

            # --- One-pair-at-a-time (right to left) ---
            while i >= lo and j >= 0:
                if tmp[j] < arr[i]:
                    arr[k] = arr[i]; k -= 1; i -= 1
                    count_l += 1; count_r = 0
                    if count_l >= mg:
                        break
                else:
                    arr[k] = tmp[j]; k -= 1; j -= 1
                    count_r += 1; count_l = 0
                    if count_r >= mg:
                        break

            if i < lo or j < 0:
                break

            # --- Inlined galloping (right to left) ---
            while i >= lo and j >= 0:
                # How many left-run elements from right end are > tmp[j]?
                # Inline _gallop_right(tmp[j], arr, lo, i-lo+1) then take tail
                key = tmp[j]
                left_len_now = i - lo + 1
                if not (key < arr[lo]):
                    ofs = 1; last_ofs = 0
                    while ofs < left_len_now and not (key < arr[lo + ofs]):
                        last_ofs = ofs
                        ofs = (ofs << 1) + 1
                        if ofs > left_len_now:
                            ofs = left_len_now
                    gallop_k = _br(arr, key, lo + last_ofs + 1, lo + ofs) - lo
                elif key < arr[lo]:
                    gallop_k = 0
                else:
                    gallop_k = 0

                cnt = left_len_now - gallop_k
                if cnt:
                    arr[k - cnt + 1:k + 1] = arr[i - cnt + 1:i + 1]
                    k -= cnt; i -= cnt
                    if i < lo:
                        break

                arr[k] = tmp[j]; k -= 1; j -= 1
                if j < 0:
                    break

                # How many right-run elements from right end are >= arr[i]?
                # Inline _gallop_left(arr[i], tmp, 0, j+1) then take tail
                key = arr[i]
                right_len_now = j + 1
                if tmp[0] < key:
                    ofs = 1; last_ofs = 0
                    while ofs < right_len_now and tmp[ofs] < key:
                        last_ofs = ofs
                        ofs = (ofs << 1) + 1
                        if ofs > right_len_now:
                            ofs = right_len_now
                    gallop_k = _bl(tmp, key, last_ofs + 1, ofs)
                else:
                    gallop_k = 0

                cnt = right_len_now - gallop_k
                if cnt:
                    arr[k - cnt + 1:k + 1] = tmp[j - cnt + 1:j + 1]
                    k -= cnt; j -= cnt
                    if j < 0:
                        break

                arr[k] = arr[i]; k -= 1; i -= 1

                if cnt < mg:
                    mg += 1
                    break
                mg = max(1, mg - 1)

        if j >= 0:
            arr[lo:lo + j + 1] = tmp[:j + 1]

        self.min_gallop = max(1, mg)

    def merge_at(self, idx):
        stack = self.stack
        arr = self.arr
        lo1, len1 = stack[idx]
        lo2, len2 = stack[idx + 1]

        stack[idx] = (lo1, len1 + len2)
        if idx == len(stack) - 3:
            stack[idx + 1] = stack[idx + 2]
        stack.pop()

        mid = lo1 + len1
        hi = lo2 + len2

        # Cheap early-return: runs already in order, skip all merge work
        if not (arr[mid] < arr[mid - 1]):
            return

        # Run trimming
        trim = _gallop_right(arr[mid], arr, lo1, len1)
        lo1 += trim; len1 -= trim
        if len1 == 0:
            return

        len2 = _gallop_left(arr[mid - 1], arr, mid, len2)
        if len2 == 0:
            return
        hi = mid + len2

        if len1 <= len2:
            self.merge_lo(lo1, mid, hi)
        else:
            self.merge_hi(lo1, mid, hi)

    def merge_collapse(self):
        stack = self.stack
        while len(stack) > 1:
            n = len(stack) - 2
            if n > 0 and not (stack[n][1] + stack[n + 1][1] < stack[n - 1][1]):
                if stack[n - 1][1] < stack[n + 1][1]:
                    self.merge_at(n - 1)
                else:
                    self.merge_at(n)
            elif not (stack[n + 1][1] < stack[n][1]):
                self.merge_at(n)
            else:
                break

    def merge_force_collapse(self):
        stack = self.stack
        while len(stack) > 1:
            n = len(stack) - 2
            if n > 0 and stack[n - 1][1] < stack[n + 1][1]:
                self.merge_at(n - 1)
            else:
                self.merge_at(n)

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

        while lo < n:
            run_hi = _count_run(arr, lo, n)
            run_len = run_hi - lo

            if run_len < minrun:
                force = min(minrun, n - lo)
                _insertion_sort(arr, lo, lo + force)
                run_len = force

            self.stack.append((lo, run_len))
            self.merge_collapse()
            lo += run_len

        self.merge_force_collapse()


def timsort(arr, *, key=None, reverse=False, min_merge=None):
    """Sort arr in-place using Timsort. Returns arr for convenience.

    Args:
        key: Function applied to each element for comparison.
        reverse: If True, sort in descending order.
        min_merge: Override MIN_MERGE threshold (default 64). Must be >= 2.
    """
    mm = MIN_MERGE if min_merge is None else max(2, int(min_merge))
    if key is not None or reverse:
        if key is not None and reverse:
            wrapped = [(_Reverse(key(x)), i, x) for i, x in enumerate(arr)]
        elif key is not None:
            wrapped = [(key(x), i, x) for i, x in enumerate(arr)]
        else:
            wrapped = [(_Reverse(x), i, x) for i, x in enumerate(arr)]
        _TimSortState(wrapped, mm).sort()
        for i, (_, _, v) in enumerate(wrapped):
            arr[i] = v
    else:
        _TimSortState(arr, mm).sort()
    return arr


class _Reverse:
    __slots__ = ('val',)
    def __init__(self, val):
        self.val = val
    def __lt__(self, other):
        return other.val < self.val
