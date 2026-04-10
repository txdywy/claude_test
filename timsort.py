"""
Timsort — a hybrid stable sorting algorithm combining merge sort and insertion sort.
All comparisons use only the < operator for __lt__ compatibility.
Supports key and reverse parameters matching Python's sorted() interface.
"""

MIN_MERGE = 32
MIN_GALLOP = 7


def _compute_minrun(n):
    r = 0
    while n >= MIN_MERGE:
        r |= n & 1
        n >>= 1
    return n + r


def _insertion_sort(arr, lo, hi):
    for i in range(lo + 1, hi):
        key = arr[i]
        left, right = lo, i
        while left < right:
            mid = (left + right) >> 1
            if key < arr[mid]:
                right = mid
            else:
                left = mid + 1
        # Slice assignment: shifts in C layer, faster than Python loop
        arr[left + 1:i + 1] = arr[left:i]
        arr[left] = key


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


def _gallop_right(key, arr, base, length):
    """bisect_right: all arr[base..base+k-1] <= key."""
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
    last_ofs += 1
    while last_ofs < ofs:
        mid = last_ofs + ((ofs - last_ofs) >> 1)
        if key < arr[base + mid]:
            ofs = mid
        else:
            last_ofs = mid + 1
    return ofs


def _gallop_left(key, arr, base, length):
    """bisect_left: all arr[base..base+k-1] < key."""
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
    last_ofs += 1
    while last_ofs < ofs:
        mid = last_ofs + ((ofs - last_ofs) >> 1)
        if arr[base + mid] < key:
            last_ofs = mid + 1
        else:
            ofs = mid
    return ofs


class _TimSortState:
    """Holds persistent state across merges: reusable temp buffer and min_gallop."""

    __slots__ = ('arr', 'tmp', 'min_gallop', 'stack')

    def __init__(self, arr):
        self.arr = arr
        self.tmp = []
        self.min_gallop = MIN_GALLOP
        self.stack = []

    def _ensure_tmp(self, needed):
        if len(self.tmp) < needed:
            self.tmp = [None] * needed

    def merge_lo(self, lo, mid, hi):
        arr = self.arr
        left_len = mid - lo
        self._ensure_tmp(left_len)
        tmp = self.tmp
        tmp[:left_len] = arr[lo:mid]

        i, j, k = 0, mid, lo
        mg = self.min_gallop

        while i < left_len and j < hi:
            count_l = count_r = 0

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

            # Galloping mode
            while i < left_len and j < hi:
                cnt = _gallop_left(tmp[i], arr, j, hi - j)
                if cnt:
                    arr[k:k + cnt] = arr[j:j + cnt]
                    k += cnt; j += cnt
                    if j >= hi:
                        break

                arr[k] = tmp[i]; k += 1; i += 1
                if i >= left_len:
                    break

                cnt = _gallop_right(arr[j], tmp, i, left_len - i)
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

        i, j, k = mid - 1, right_len - 1, hi - 1
        mg = self.min_gallop

        while i >= lo and j >= 0:
            count_l = count_r = 0

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

            # Galloping mode (right to left)
            while i >= lo and j >= 0:
                left_len_now = i - lo + 1
                gallop_k = _gallop_right(tmp[j], arr, lo, left_len_now)
                cnt = left_len_now - gallop_k
                if cnt:
                    arr[k - cnt + 1:k + 1] = arr[i - cnt + 1:i + 1]
                    k -= cnt; i -= cnt
                    if i < lo:
                        break

                arr[k] = tmp[j]; k -= 1; j -= 1
                if j < 0:
                    break

                right_len_now = j + 1
                gallop_k = _gallop_left(arr[i], tmp, 0, right_len_now)
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

        # Update stack
        stack[idx] = (lo1, len1 + len2)
        if idx == len(stack) - 3:
            stack[idx + 1] = stack[idx + 2]
        stack.pop()

        mid = lo1 + len1
        hi = lo2 + len2

        # --- Run trimming ---
        # Skip left-run prefix that's already in place
        trim = _gallop_right(arr[mid], arr, lo1, len1)
        lo1 += trim
        len1 -= trim
        if len1 == 0:
            return

        # Skip right-run suffix that's already in place
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

        if n < MIN_MERGE:
            _insertion_sort(arr, 0, n)
            return

        minrun = _compute_minrun(n)
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


def timsort(arr, *, key=None, reverse=False):
    """Sort arr in-place using Timsort. Returns arr for convenience.

    Args:
        key: Function applied to each element for comparison (like sorted()).
        reverse: If True, sort in descending order.
    """
    if key is not None or reverse:
        if key is not None and reverse:
            wrapped = [(_Reverse(key(x)), i, x) for i, x in enumerate(arr)]
        elif key is not None:
            wrapped = [(key(x), i, x) for i, x in enumerate(arr)]
        else:
            wrapped = [(_Reverse(x), i, x) for i, x in enumerate(arr)]
        _TimSortState(wrapped).sort()
        for i, (_, _, v) in enumerate(wrapped):
            arr[i] = v
    else:
        _TimSortState(arr).sort()
    return arr


class _Reverse:
    """Wrapper that reverses < comparison for reverse=True support."""
    __slots__ = ('val',)

    def __init__(self, val):
        self.val = val

    def __lt__(self, other):
        return other.val < self.val
