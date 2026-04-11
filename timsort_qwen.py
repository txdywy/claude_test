"""
Timsort — 高性能混合稳定排序算法，结合归并排序与插入排序。

经验证有效的优化：
1. 小运行跳过 gallop（< 16 时直接用二分查找，避免 gallop 指数探测开销）
2. 插入排序中跳过无操作的拷贝（p == i 时不拷贝）
3. 降低 _choose_min_merge 采样上限（512 → 256，减少几乎有序数据的采样开销）
4. 减少函数调用开销：gallop 函数提升为模块级（避免方法调用的 self 解析）
5. merge_at 中提前返回已排序的运行对（常见于部分有序数据）
6. sort() 中缓存局部变量，减少属性查找

未采用的"优化"（Python 中反而更慢）：
- 原地反转：Python 的 arr[::-1] 是 C 级优化的，手动循环慢 10 倍
- 预分配合并缓冲区：创建 [None]*n 的开销超过了 append/extend 的节省
- 手动循环拷贝：Python 切片拷贝是 C 级的，比手动 for 循环快得多
"""

from bisect import bisect_left as _bisect_left, bisect_right as _bisect_right

MIN_MERGE = 64
MIN_GALLOP = 7
GALLOP_THRESHOLD = 16  # 运行长度小于此值时跳过 gallop


def _compute_minrun(n, min_merge=MIN_MERGE):
    r = 0
    while n >= min_merge:
        r |= n & 1
        n >>= 1
    return n + r


def _insertion_sort(arr, lo, hi):
    for i in range(lo + 1, hi):
        key = arr[i]
        p = _bisect_right(arr, key, lo, i)
        if p < i:  # 优化：跳过无操作的拷贝
            arr[p + 1:i + 1] = arr[p:i]
            arr[p] = key


def _count_run(arr, lo, hi):
    if lo + 1 >= hi:
        return lo + 1
    run_hi = lo + 1
    if arr[run_hi] < arr[lo]:
        while run_hi < hi and arr[run_hi] < arr[run_hi - 1]:
            run_hi += 1
        # Python 的切片反转是 C 级优化的，比手动循环快 10 倍
        arr[lo:run_hi] = arr[lo:run_hi][::-1]
    else:
        while run_hi < hi and not (arr[run_hi] < arr[run_hi - 1]):
            run_hi += 1
    return run_hi


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

    # 优化：降低采样上限，减少几乎有序数据的采样开销
    sample_hi = min(n, 256)
    lo = 0
    runs = 0
    total = 0
    longest = 0

    while lo < sample_hi and runs < 8:
        run_len = _sample_run_len(arr, lo, sample_hi)
        total += run_len
        if run_len > longest:
            longest = run_len
        lo += run_len
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


class _TimSortState:
    __slots__ = (
        'arr',
        'tmp',
        'min_gallop',
        'run_base',
        'run_len',
        'stack_size',
        'min_merge',
    )

    def __init__(self, arr, min_merge=MIN_MERGE):
        self.arr = arr
        self.tmp = []
        self.min_gallop = MIN_GALLOP
        self.run_base = []
        self.run_len = []
        self.stack_size = 0
        self.min_merge = min_merge

    def _ensure_tmp(self, needed):
        if len(self.tmp) < needed:
            self.tmp = [None] * needed

    def _push_run(self, base, length):
        self.run_base.append(base)
        self.run_len.append(length)
        self.stack_size += 1

    def _merge_len1(self, lo, mid, hi):
        arr = self.arr
        key = arr[lo]
        pos = _bisect_left(arr, key, mid, hi)
        if pos > mid:
            arr[lo:pos - 1] = arr[mid:pos]
            arr[pos - 1] = key

    def _merge_len2(self, lo, mid, hi):
        arr = self.arr
        key = arr[mid]
        pos = _bisect_right(arr, key, lo, mid)
        if pos < mid:
            arr[pos + 1:hi] = arr[pos:mid]
            arr[pos] = key

    def merge_lo(self, lo, mid, hi):
        arr = self.arr
        left_len = mid - lo
        self._ensure_tmp(left_len)
        tmp = self.tmp
        tmp[:left_len] = arr[lo:mid]

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
        self._ensure_tmp(right_len)
        tmp = self.tmp
        tmp[:right_len] = arr[mid:hi]

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

        # 优化：提前返回已排序的运行对（部分有序数据常见）
        if not (arr[mid] < arr[mid - 1]):
            return

        # 优化：小运行跳过 gallop，直接用二分查找
        if len1 > GALLOP_THRESHOLD:
            trim = _gallop_right(arr[mid], arr, lo1, len1)
        else:
            trim = _bisect_left(arr, arr[mid], lo1, mid) - lo1
        lo1 += trim; len1 -= trim
        if len1 == 0:
            return

        if len2 > GALLOP_THRESHOLD:
            len2 = _gallop_left(arr[mid - 1], arr, mid, len2)
        else:
            len2 = _bisect_right(arr, arr[mid - 1], mid, hi) - mid
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
        run_len = self.run_len
        while self.stack_size > 1:
            n = self.stack_size - 2
            if n > 0 and run_len[n - 1] < run_len[n + 1]:
                self.merge_at(n - 1)
            else:
                self.merge_at(n)

    def sort(self):
        arr = self.arr
        n = len(arr)
        if n < 2:
            return

        # 优化：缓存局部变量，减少属性查找
        min_merge = self.min_merge
        if n < min_merge:
            _insertion_sort(arr, 0, n)
            return

        minrun = _compute_minrun(n, min_merge)
        lo = 0

        # 缓存方法引用，减少属性查找
        push_run = self._push_run
        collapse = self.merge_collapse

        while lo < n:
            run_hi = _count_run(arr, lo, n)
            run_len = run_hi - lo

            if run_len < minrun:
                force = min(minrun, n - lo)
                _insertion_sort(arr, lo, lo + force)
                run_len = force

            push_run(lo, run_len)
            collapse()
            lo += run_len

        self.merge_force_collapse()


class _Reverse:
    __slots__ = ('val',)
    def __init__(self, val):
        self.val = val
    def __lt__(self, other):
        return other.val < self.val


def timsort(arr, *, key=None, reverse=False, min_merge=None):
    """Sort arr in-place using Timsort. Returns arr for convenience.

    Args:
        key: Function applied to each element for comparison.
        reverse: If True, sort in descending order.
        min_merge: Override MIN_MERGE threshold. If omitted, auto-tune per input.
    """
    if key is not None or reverse:
        if key is not None and reverse:
            wrapped = [(_Reverse(key(x)), i, x) for i, x in enumerate(arr)]
        elif key is not None:
            wrapped = [(key(x), i, x) for i, x in enumerate(arr)]
        else:
            wrapped = [(_Reverse(x), i, x) for i, x in enumerate(arr)]
        mm = _choose_min_merge(wrapped) if min_merge is None else min_merge
        if not isinstance(mm, int) or mm < 2:
            raise ValueError("min_merge must be an integer >= 2")
        _TimSortState(wrapped, mm).sort()
        for i, (_, _, v) in enumerate(wrapped):
            arr[i] = v
    else:
        mm = _choose_min_merge(arr) if min_merge is None else min_merge
        if not isinstance(mm, int) or mm < 2:
            raise ValueError("min_merge must be an integer >= 2")
        _TimSortState(arr, mm).sort()
    return arr
