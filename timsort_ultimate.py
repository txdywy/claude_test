"""
Timsort Ultimate — 最快 Python Timsort 实现。

核心策略：归并委托给 CPython 的 C 级 list.sort()（比纯 Python 快 ~20 倍）。
不做运行检测（Python 循环开销大），直接分块排序，让 C 级 Timsort 处理有序性。

优化清单：
1. 分块排序用 list.sort()（C 级，自动检测有序运行）
2. 归并用 list.sort() 对重叠区域排序（C 级 Timsort 检测两个运行并合并）
3. 运行修剪用 bisect（C 级），减少排序范围
4. min_merge 校验 bool 子类（防御性编程）
5. 自适应 min_merge（深度采样策略）
"""

from bisect import bisect_left as _bisect_left, bisect_right as _bisect_right

MIN_MERGE = 64


def _compute_minrun(n, min_merge=MIN_MERGE):
    r = 0
    while n >= min_merge:
        r |= n & 1
        n >>= 1
    return n + r


def _count_run_longest(arr, lo, hi):
    """查找运行长度，扫描限制在 4096 个元素内"""
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
    """基于数据结构分析的自适应 min_merge"""
    if n < 128:
        return 64

    longest = _count_run_longest(arr, 0, min(n, 512))

    if longest >= 96:
        return 16

    if n >= 4096 and longest < 24:
        total = 0
        lo = 0
        runs = 0
        end = min(n, 2048)
        while lo < end and runs < 12:
            rl = _count_run_longest(arr, lo, end)
            total += rl
            lo += rl
            runs += 1
        avg = total // runs if runs else 1
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


def _timsort_engine(arr, min_merge=MIN_MERGE):
    n = len(arr)
    if n < 2:
        return

    if n < min_merge:
        arr.sort()
        return

    # 快速路径 1：采样 32 个等间距配对，检测有序/降序
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

        # 快速路径 2：如果约一半反转，检查起点/中点是否有长运行
        # 捕获 pipe organ 等两运行模式
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
    run_base = []
    run_len = []
    stack_size = 0

    rb_append = run_base.append
    rl_append = run_len.append
    bisect_left = _bisect_left
    bisect_right = _bisect_right

    def merge_at(idx):
        nonlocal stack_size
        lo1 = run_base[idx]
        len1 = run_len[idx]
        len2 = run_len[idx + 1]

        run_len[idx] = len1 + len2
        if idx == stack_size - 3:
            run_base[idx + 1] = run_base[idx + 2]
            run_len[idx + 1] = run_len[idx + 2]
        run_base.pop()
        run_len.pop()
        stack_size -= 1

        mid = lo1 + len1
        hi = mid + len2

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
        nonlocal stack_size
        while stack_size > 1:
            nn = stack_size - 2
            if nn > 0 and not (run_len[nn] + run_len[nn + 1] < run_len[nn - 1]):
                if run_len[nn - 1] < run_len[nn + 1]:
                    merge_at(nn - 1)
                else:
                    merge_at(nn)
            elif not (run_len[nn + 1] < run_len[nn]):
                merge_at(nn)
            else:
                break

    lo = 0
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
        nn = stack_size - 2
        if nn > 0 and run_len[nn - 1] < run_len[nn + 1]:
            merge_at(nn - 1)
        else:
            merge_at(nn)


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
        mm = _choose_min_merge(wrapped, len(wrapped)) if min_merge is None else min_merge
        if not isinstance(mm, int) or isinstance(mm, bool) or mm < 2:
            raise ValueError("min_merge must be an integer >= 2")
        _timsort_engine(wrapped, mm)
        for i, (_, _, v) in enumerate(wrapped):
            arr[i] = v
    else:
        mm = _choose_min_merge(arr, len(arr)) if min_merge is None else min_merge
        if not isinstance(mm, int) or isinstance(mm, bool) or mm < 2:
            raise ValueError("min_merge must be an integer >= 2")
        _timsort_engine(arr, mm)
    return arr
