/*
 * Ultra-high-performance Timsort implementation in C.
 *
 * Strategy: X-macros to generate both int64_t and double versions
 * from the same algorithm template.
 */

#include "sort_c.h"
#include <stdlib.h>
#include <string.h>

#define MIN_MERGE           32
#define MAX_STACK           85
#define INIT_GALLOP_THRESH  7

#define LIKELY(x)   __builtin_expect(!!(x), 1)
#define UNLIKELY(x) __builtin_expect(!!(x), 0)

static inline int ts_compute_minrun(size_t n) {
    int r = 0;
    while (n >= MIN_MERGE) { r |= (int)(n & 1); n >>= 1; }
    return (int)n + r;
}

/* ================================================================== */
/*  TEMPLATE for scalar types                                           */
/* ================================================================== */

#define DEFINE_TIMSORT(TYPE, NAME)                                          \
                                                                            \
static size_t NAME##_count_run(TYPE *arr, size_t lo, size_t hi) {           \
    if (lo + 1 >= hi) return 1;                                             \
    size_t rh = lo + 1;                                                     \
    if (arr[rh] < arr[lo]) {                                                \
        while (rh + 1 < hi && arr[rh + 1] < arr[rh]) rh++;                  \
        size_t a = lo, b = rh;                                              \
        while (a < b) { TYPE t = arr[a]; arr[a] = arr[b]; arr[b] = t; a++; b--; } \
    } else {                                                                \
        while (rh + 1 < hi && !(arr[rh + 1] < arr[rh])) rh++;               \
    }                                                                       \
    return rh + 1 - lo;                                                     \
}                                                                           \
                                                                            \
static void NAME##_bin_insertion_sort(TYPE *arr, size_t lo, size_t hi) {    \
    for (size_t i = lo + 1; i < hi; i++) {                                  \
        TYPE key = arr[i];                                                  \
        size_t l = lo, r = i;                                               \
        while (l < r) {                                                     \
            size_t m = l + ((r - l) >> 1);                                  \
            if (key < arr[m]) r = m; else l = m + 1;                        \
        }                                                                   \
        size_t shift = i - l;                                               \
        if (shift > 0) {                                                    \
            memmove(&arr[l + 1], &arr[l], shift * sizeof(TYPE));            \
            arr[l] = key;                                                   \
        }                                                                   \
    }                                                                       \
}                                                                           \
                                                                            \
typedef struct {                                                            \
    TYPE  *array;                                                           \
    TYPE  *tmp;                                                             \
    size_t run_base[MAX_STACK];                                             \
    size_t run_len[MAX_STACK];                                              \
    int    stack_size;                                                      \
} NAME##_ts;                                                                \
                                                                            \
static size_t NAME##_lb(TYPE *a, size_t lo, size_t hi, TYPE key) {          \
    while (lo < hi) { size_t m = lo + ((hi - lo) >> 1);                     \
        if (a[m] < key) lo = m + 1; else hi = m; } return lo;               \
}                                                                           \
static size_t NAME##_ub(TYPE *a, size_t lo, size_t hi, TYPE key) {          \
    while (lo < hi) { size_t m = lo + ((hi - lo) >> 1);                     \
        if (key < a[m]) hi = m; else lo = m + 1; } return lo;               \
}                                                                           \
                                                                            \
static int NAME##_merge_lo(NAME##_ts *ts,                                   \
                           size_t s1, size_t l1, size_t s2, size_t l2) {    \
    TYPE *a = ts->array, *t = ts->tmp;                                      \
    if (l1 == 0 || l2 == 0) return 0;                                       \
    size_t e1 = s1 + l1, e2 = s2 + l2;                                      \
    size_t k = NAME##_lb(a, s1, e1, a[s2]);                                 \
    s1 = k; l1 = e1 - s1;                                                   \
    if (l1 == 0) return 0;                                                  \
    e2 = NAME##_ub(a, s2, e2, a[s1 + l1 - 1]);                              \
    l2 = e2 - s2;                                                           \
    if (l2 == 0) return 0;                                                  \
    memcpy(t, &a[s1], l1 * sizeof(TYPE));                                   \
    size_t i = 0, j = s2, d = s1;                                           \
    while (i < l1 && j < e2) {                                              \
        if (a[j] < t[i]) a[d++] = a[j++];                                   \
        else a[d++] = t[i++];                                               \
    }                                                                       \
    if (i < l1) memmove(&a[d], &t[i], (l1 - i) * sizeof(TYPE));            \
    return 0;                                                               \
}                                                                           \
                                                                            \
static int NAME##_merge_hi(NAME##_ts *ts,                                   \
                           size_t s1, size_t l1, size_t s2, size_t l2) {    \
    TYPE *a = ts->array, *t = ts->tmp;                                      \
    if (l1 == 0 || l2 == 0) return 0;                                       \
    size_t e1 = s1 + l1, e2 = s2 + l2;                                      \
    size_t k = NAME##_lb(a, s1, e1, a[s2]);                                 \
    l1 = e1 - k; s1 = k;                                                    \
    if (l1 == 0) return 0;                                                  \
    e2 = NAME##_ub(a, s2, e2, a[s1 + l1 - 1]);                              \
    l2 = e2 - s2;                                                           \
    if (l2 == 0) return 0;                                                  \
    e1 = s1 + l1;                                                           \
    /* l1 > l2: right run is smaller. Copy it to tmp and merge backwards.  \
     * Write largest to a[e2-1], then a[e2-2], etc.                        \
     * Read from a[e1-1] (last left) and t[l2-1] (last right).            \
     * Since e2 > e1, writing from the end never overwrites unread data. */ \
    for (size_t x = 0; x < l2; x++) t[x] = a[s2 + x];                      \
    size_t li = e1, ri = l2, dest = e2;                                     \
    while (li > s1 && ri > 0) {                                             \
        if (!(t[ri - 1] < a[li - 1]))                                       \
            a[--dest] = t[--ri];                                            \
        else                                                                \
            a[--dest] = a[--li];                                            \
    }                                                                       \
    /* If left exhausted (li == s1): remaining tmp[0..ri) -> a[s1..s1+ri) */ \
    if (li == s1 && ri > 0)                                                 \
        memmove(&a[s1], t, ri * sizeof(TYPE));                              \
    /* If right exhausted (ri == 0): remaining left[s1..li) already       \
     * in place at a[s1..li). No action needed. */                          \
    return 0;                                                               \
}                                                                           \
                                                                            \
static int NAME##_merge_at(NAME##_ts *ts, int idx) {                        \
    size_t s1 = ts->run_base[idx], l1 = ts->run_len[idx];                   \
    size_t l2 = ts->run_len[idx + 1], s2 = ts->run_base[idx + 1];          \
    ts->run_len[idx] = l1 + l2;                                             \
    if (idx == ts->stack_size - 3) {                                        \
        ts->run_base[idx + 1] = ts->run_base[idx + 2];                      \
        ts->run_len[idx + 1] = ts->run_len[idx + 2];                        \
    }                                                                       \
    ts->stack_size--;                                                       \
    if (l1 <= l2) return NAME##_merge_lo(ts, s1, l1, s2, l2);              \
    else return NAME##_merge_hi(ts, s1, l1, s2, l2);                        \
}                                                                           \
                                                                            \
static int NAME##_collapse(NAME##_ts *ts) {                                 \
    while (ts->stack_size > 1) {                                            \
        int n = ts->stack_size - 2;                                         \
        if (n > 0 && ts->run_len[n - 1] <= ts->run_len[n] + ts->run_len[n + 1]) { \
            if (ts->run_len[n - 1] < ts->run_len[n + 1]) n--;              \
            if (NAME##_merge_at(ts, n) != 0) return -1;                     \
        } else if (ts->run_len[n] <= ts->run_len[n + 1]) {                  \
            if (NAME##_merge_at(ts, n) != 0) return -1;                     \
        } else break;                                                       \
    }                                                                       \
    return 0;                                                               \
}                                                                           \
                                                                            \
static int NAME##_force_collapse(NAME##_ts *ts) {                           \
    while (ts->stack_size > 1) {                                            \
        int n = ts->stack_size - 2;                                         \
        if (n > 0 && ts->run_len[n - 1] < ts->run_len[n + 1]) n--;         \
        if (NAME##_merge_at(ts, n) != 0) return -1;                         \
    }                                                                       \
    return 0;                                                               \
}                                                                           \
                                                                            \
int NAME##_timsort(TYPE *arr, size_t n) {                                   \
    if (n < 2) return 0;                                                    \
    /* Fast path: check if already sorted */                                \
    { size_t i; for (i = 1; i < n; i++) if (arr[i] < arr[i-1]) break;       \
      if (i == n) return 0; }                                               \
    /* Fast path: check if reverse sorted, reverse in-place */              \
    { size_t i; for (i = 1; i < n; i++) if (arr[i-1] < arr[i]) break;       \
      if (i == n) { size_t a = 0, b = n-1; while (a < b) {                  \
        TYPE t = arr[a]; arr[a] = arr[b]; arr[b] = t; a++; b--; }           \
        return 0; } }                                                       \
    int minrun = ts_compute_minrun(n);                                       \
    size_t tmp_sz = n >> 1; if (tmp_sz < 256) tmp_sz = 256;                 \
    TYPE *tmp = (TYPE *)malloc(tmp_sz * sizeof(TYPE));                      \
    if (UNLIKELY(!tmp)) return -1;                                          \
    NAME##_ts ts;                                                           \
    memset(&ts, 0, sizeof(ts));                                             \
    ts.array = arr; ts.tmp = tmp;                                           \
    size_t lo = 0;                                                          \
    while (lo < n) {                                                        \
        size_t rem = n - lo;                                                \
        size_t len = NAME##_count_run(arr, lo, lo + rem);                   \
        if ((int)len < minrun) {                                            \
            size_t force = (size_t)minrun;                                  \
            if (force > rem) force = rem;                                   \
            NAME##_bin_insertion_sort(arr, lo, lo + force);                 \
            len = force;                                                    \
        }                                                                   \
        ts.run_base[ts.stack_size] = lo;                                    \
        ts.run_len[ts.stack_size] = len;                                    \
        ts.stack_size++;                                                    \
        if (NAME##_collapse(&ts) != 0) { free(tmp); return -1; }           \
        lo += len;                                                          \
    }                                                                       \
    int ret = NAME##_force_collapse(&ts);                                   \
    free(tmp);                                                              \
    return ret;                                                             \
}                                                                           \
                                                                            \
int NAME##_is_sorted(const TYPE *arr, size_t n) {                           \
    for (size_t i = 1; i < n; i++) if (arr[i] < arr[i - 1]) return 0;      \
    return 1;                                                               \
}

DEFINE_TIMSORT(int64_t, int64)
DEFINE_TIMSORT(double,   dbl)

int timsort_int64(int64_t *arr, size_t n) { return int64_timsort(arr, n); }
int timsort_double(double *arr, size_t n) { return dbl_timsort(arr, n); }
int is_sorted_int64(const int64_t *arr, size_t n) { return int64_is_sorted(arr, n); }
int is_sorted_double(const double *arr, size_t n) { return dbl_is_sorted(arr, n); }

/* ================================================================== */
/*  Generic Timsort (void* + comparator)                                */
/* ================================================================== */

typedef struct {
    char *arr, *tmp; size_t n, es; cmp_func cmp;
    size_t rb[MAX_STACK], rl[MAX_STACK]; int ss, mg;
} gen_ts;

static void gen_swap(gen_ts *ts, size_t a, size_t b) {
    size_t es = ts->es; char buf[256];
    if (es <= 256) {
        memcpy(buf, &ts->arr[a * es], es);
        memcpy(&ts->arr[a * es], &ts->arr[b * es], es);
        memcpy(&ts->arr[b * es], buf, es);
    } else {
        char *tb = (char *)malloc(es);
        if (!tb) return;
        memcpy(tb, &ts->arr[a * es], es);
        memcpy(&ts->arr[a * es], &ts->arr[b * es], es);
        memcpy(&ts->arr[b * es], tb, es);
        free(tb);
    }
}

static size_t gen_count_run(gen_ts *ts, size_t lo, size_t hi) {
    if (lo + 1 >= hi) return 1;
    size_t rh = lo + 1, es = ts->es;
    if (ts->cmp(&ts->arr[rh * es], &ts->arr[lo * es]) < 0) {
        while (rh + 1 < hi && ts->cmp(&ts->arr[(rh+1)*es], &ts->arr[rh*es]) < 0) rh++;
        size_t a = lo, b = rh;
        while (a < b) { gen_swap(ts, a, b); a++; b--; }
    } else {
        while (rh + 1 < hi && ts->cmp(&ts->arr[(rh+1)*es], &ts->arr[rh*es]) >= 0) rh++;
    }
    return rh + 1 - lo;
}

static void gen_bin_insertion_sort(gen_ts *ts, size_t lo, size_t hi) {
    size_t es = ts->es;
    char kbuf[256]; char *k = (es <= 256) ? kbuf : (char *)malloc(es);
    if (!k) return;
    for (size_t i = lo + 1; i < hi; i++) {
        memcpy(k, &ts->arr[i * es], es);
        size_t l = lo, r = i;
        while (l < r) { size_t m = l + ((r - l) >> 1);
            if (ts->cmp(k, &ts->arr[m * es]) < 0) r = m; else l = m + 1; }
        size_t shift = i - l;
        if (shift > 0) {
            memmove(&ts->arr[(l+1)*es], &ts->arr[l*es], shift * es);
            memcpy(&ts->arr[l * es], k, es);
        }
    }
    if (es > 256) free(k);
}

static size_t gen_lb(gen_ts *ts, size_t lo, size_t hi, char *key) {
    size_t es = ts->es;
    while (lo < hi) { size_t m = lo + ((hi - lo) >> 1);
        if (ts->cmp(&ts->arr[m * es], key) < 0) lo = m + 1; else hi = m; }
    return lo;
}
static size_t gen_ub(gen_ts *ts, size_t lo, size_t hi, char *key) {
    size_t es = ts->es;
    while (lo < hi) { size_t m = lo + ((hi - lo) >> 1);
        if (ts->cmp(key, &ts->arr[m * es]) < 0) hi = m; else lo = m + 1; }
    return lo;
}

static int gen_merge_lo(gen_ts *ts, size_t s1, size_t l1, size_t s2, size_t l2) {
    if (l1 == 0 || l2 == 0) return 0;
    size_t e1 = s1 + l1, e2 = s2 + l2, es = ts->es;
    char *t = ts->tmp;
    size_t k = gen_lb(ts, s1, e1, &ts->arr[s2 * es]);
    s1 = k; l1 = e1 - s1;
    if (l1 == 0) return 0;
    e2 = gen_ub(ts, s2, e2, &ts->arr[(s1 + l1 - 1) * es]);
    l2 = e2 - s2;
    if (l2 == 0) return 0;
    memcpy(t, &ts->arr[s1 * es], l1 * es);
    size_t i = 0, j = s2, d = s1;
    int mg = ts->mg;
    while (i < l1 && j < e2) {
        size_t ac = 0, bc = 0;
        while (i < l1 && j < e2) {
            if (ts->cmp(&ts->arr[j * es], &t[i * es]) < 0) {
                memcpy(&ts->arr[d * es], &ts->arr[j * es], es);
                d++; j++; ac++; bc = 0;
            } else {
                memcpy(&ts->arr[d * es], &t[i * es], es);
                d++; i++; bc++; ac = 0;
            }
            if (ac >= (size_t)mg || bc >= (size_t)mg) break;
        }
        if (i >= l1 || j >= e2) break;
        { size_t cnt = 1;
            while (j + cnt < e2 && ts->cmp(&ts->arr[(j+cnt)*es], &t[i*es]) < 0) cnt <<= 1;
            size_t hi = j + cnt; if (hi > e2) hi = e2; size_t lo = j;
            while (lo < hi) { size_t m = lo + ((hi - lo) >> 1);
                if (ts->cmp(&ts->arr[m * es], &t[i * es]) < 0) lo = m + 1; else hi = m; }
            size_t n = lo - j;
            if (n > 0) { memmove(&ts->arr[d*es], &ts->arr[j*es], n*es); d += n; j = lo; }
            if (j >= e2) break;
            if (ac >= (size_t)mg) { mg -= (n >= 8) ? 1 : 0; if (mg < 1) mg = 1; } }
        if (i >= l1) break;
        { size_t cnt = 1;
            while (i + cnt < l1 && ts->cmp(&ts->arr[j*es], &t[(i+cnt)*es]) >= 0) cnt <<= 1;
            size_t hi = i + cnt; if (hi > l1) hi = l1; size_t lo = i;
            while (lo < hi) { size_t m = lo + ((hi - lo) >> 1);
                if (ts->cmp(&ts->arr[j*es], &t[m*es]) < 0) hi = m; else lo = m + 1; }
            size_t n = lo - i;
            if (n > 0) { memcpy(&ts->arr[d*es], &t[i*es], n*es); d += n; i = lo; }
            if (bc >= (size_t)mg) { mg -= (n >= 8) ? 1 : 0; if (mg < 1) mg = 1; } }
        if (mg < 1) mg = 1;
    }
    ts->mg = mg;
    if (i < l1) memmove(&ts->arr[d*es], &t[i*es], (l1 - i) * es);
    return 0;
}

static int gen_merge_hi(gen_ts *ts, size_t s1, size_t l1, size_t s2, size_t l2) {
    if (l1 == 0 || l2 == 0) return 0;
    size_t e1 = s1 + l1, e2 = s2 + l2, es = ts->es;
    char *t = ts->tmp;
    size_t k = gen_lb(ts, s1, e1, &ts->arr[s2 * es]);
    l1 = e1 - k; s1 = k;
    if (l1 == 0) return 0;
    e2 = gen_ub(ts, s2, e2, &ts->arr[(s1 + l1 - 1) * es]);
    l2 = e2 - s2;
    if (l2 == 0) return 0;
    e1 = s1 + l1;
    for (size_t x = 0; x < l2; x++) memcpy(&t[x * es], &ts->arr[(s2 + x) * es], es);
    size_t li = e1, ri = l2, dest = e2;
    while (li > s1 && ri > 0) {
        if (!(ts->cmp(&t[(ri-1)*es], &ts->arr[(li-1)*es]) < 0))
            { dest--; ri--; memcpy(&ts->arr[dest*es], &t[ri*es], es); }
        else
            { dest--; li--; memcpy(&ts->arr[dest*es], &ts->arr[li*es], es); }
    }
    if (li == s1 && ri > 0)
        memcpy(&ts->arr[s1*es], t, ri * es);
    return 0;
}

static int gen_merge_at(gen_ts *ts, int idx) {
    size_t s1 = ts->rb[idx], l1 = ts->rl[idx];
    size_t l2 = ts->rl[idx+1], s2 = ts->rb[idx+1];
    ts->rl[idx] = l1 + l2;
    if (idx == ts->ss - 3) { ts->rb[idx+1] = ts->rb[idx+2]; ts->rl[idx+1] = ts->rl[idx+2]; }
    ts->ss--;
    if (l1 <= l2) return gen_merge_lo(ts, s1, l1, s2, l2);
    else return gen_merge_hi(ts, s1, l1, s2, l2);
}

static int gen_collapse(gen_ts *ts) {
    while (ts->ss > 1) {
        int n = ts->ss - 2;
        if (n > 0 && ts->rl[n-1] <= ts->rl[n] + ts->rl[n+1]) {
            if (ts->rl[n-1] < ts->rl[n+1]) n--;
            if (gen_merge_at(ts, n) != 0) return -1;
        } else if (ts->rl[n] <= ts->rl[n+1]) {
            if (gen_merge_at(ts, n) != 0) return -1;
        } else break;
    }
    return 0;
}

static int gen_force(gen_ts *ts) {
    while (ts->ss > 1) {
        int n = ts->ss - 2;
        if (n > 0 && ts->rl[n-1] < ts->rl[n+1]) n--;
        if (gen_merge_at(ts, n) != 0) return -1;
    }
    return 0;
}

int timsort_generic(void *base, size_t n, size_t elem_size, cmp_func cmp) {
    if (n < 2 || !cmp) return 0;
    /* Fast path: check if already sorted */
    { char *p = (char *)base; size_t i;
      for (i = 1; i < n; i++)
        if (cmp(&p[i*elem_size], &p[(i-1)*elem_size]) < 0) break;
      if (i == n) return 0; }
    int minrun = ts_compute_minrun(n);
    size_t tmp_sz = n >> 1; if (tmp_sz < 256) tmp_sz = 256;
    char *tmp = (char *)malloc(tmp_sz * elem_size);
    if (!tmp) return -1;

    gen_ts ts;
    ts.arr = (char *)base; ts.tmp = tmp; ts.n = n;
    ts.es = elem_size; ts.cmp = cmp; ts.ss = 0; ts.mg = INIT_GALLOP_THRESH;

    size_t lo = 0;
    while (lo < n) {
        size_t rem = n - lo;
        size_t len = gen_count_run(&ts, lo, lo + rem);
        if ((int)len < minrun) {
            size_t force = (size_t)minrun;
            if (force > rem) force = rem;
            gen_bin_insertion_sort(&ts, lo, lo + force);
            len = force;
        }
        ts.rb[ts.ss] = lo; ts.rl[ts.ss] = len; ts.ss++;
        if (gen_collapse(&ts) != 0) { free(tmp); return -1; }
        lo += len;
    }
    int ret = gen_force(&ts);
    free(tmp);
    return ret;
}
