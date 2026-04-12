"""Python ctypes bridge for native C Timsort."""
import ctypes
import array
from pathlib import Path

_lib_path = Path(__file__).parent / "libsort_c.dylib"
_lib = ctypes.CDLL(str(_lib_path))

_lib.timsort_int64.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.c_size_t]
_lib.timsort_int64.restype = ctypes.c_int

_lib.timsort_double.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_size_t]
_lib.timsort_double.restype = ctypes.c_int

_lib.timsort_generic.argtypes = [
    ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p
]
_lib.timsort_generic.restype = ctypes.c_int

_lib.is_sorted_int64.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.c_size_t]
_lib.is_sorted_int64.restype = ctypes.c_int


def c_sort_int64(arr):
    """Sort a list of int64 in-place using C Timsort. Returns arr."""
    n = len(arr)
    if n < 2:
        return arr
    Arr = ctypes.c_int64 * n
    c_arr = Arr(*arr)
    ret = _lib.timsort_int64(c_arr, n)
    assert ret == 0
    for i in range(n):
        arr[i] = c_arr[i]
    return arr


def c_sort_double(arr):
    """Sort a list of floats in-place using C Timsort. Returns arr."""
    n = len(arr)
    if n < 2:
        return arr
    Arr = ctypes.c_double * n
    c_arr = Arr(*arr)
    ret = _lib.timsort_double(c_arr, n)
    assert ret == 0
    for i in range(n):
        arr[i] = c_arr[i]
    return arr


def c_sort_array(arr):
    """Sort an array.array in-place with zero-copy. Supports 'q'/'l' (int64) and 'd' (double)."""
    n = len(arr)
    if n < 2:
        return arr
    buf = (ctypes.c_char * (n * arr.itemsize)).from_buffer(arr)
    if arr.typecode == 'd':
        c_arr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_double))
        ret = _lib.timsort_double(c_arr, n)
    elif arr.typecode in ('q', 'l') and arr.itemsize == 8:
        c_arr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_int64))
        ret = _lib.timsort_int64(c_arr, n)
    else:
        raise ValueError(f"Unsupported array typecode '{arr.typecode}' (itemsize={arr.itemsize})")
    assert ret == 0
    return arr


class _Pair(ctypes.Structure):
    _fields_ = [("val", ctypes.c_int64), ("idx", ctypes.c_int64)]

_CMP = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(_Pair), ctypes.POINTER(_Pair))


def c_sort_generic(data, key=None, reverse=False):
    """Generic sort supporting key and reverse via timsort_generic.

    Works with any comparable type. Slower than specialized versions
    due to Python callback overhead, but supports arbitrary types.
    """
    if not data:
        return data

    n = len(data)
    if key is not None:
        decorated = [(key(x), i, x) for i, x in enumerate(data)]
    else:
        decorated = [(x, i, x) for i, x in enumerate(data)]

    if reverse:
        from bisect import bisect_left
        # Use Python's timsort_cc with reverse wrapper
        from timsort_cc import timsort
        timsort(decorated, key=lambda x: _RevKey(x[0]), reverse=False)
    else:
        decorated.sort()

    for i, (_, _, v) in enumerate(decorated):
        data[i] = v
    return data


class _RevKey:
    __slots__ = ('val',)
    def __init__(self, val):
        self.val = val
    def __lt__(self, other):
        return other.val < self.val
    def __le__(self, other):
        return not (self.val < other.val)
