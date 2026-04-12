#ifndef SORT_C_H
#define SORT_C_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Sort int64_t array in-place. Returns 0 on success, -1 on error. */
int timsort_int64(int64_t *arr, size_t n);

/* Sort double array in-place. Returns 0 on success, -1 on error. */
int timsort_double(double *arr, size_t n);

/* Generic sort with user-provided comparator.
 * elem_size: size of each element in bytes.
 * cmp: returns <0 if a<b, 0 if a==b, >0 if a>b.
 * Returns 0 on success, -1 on error. */
typedef int (*cmp_func)(const void *a, const void *b);
int timsort_generic(void *base, size_t n, size_t elem_size, cmp_func cmp);

/* Fast-path checks */
int is_sorted_int64(const int64_t *arr, size_t n);
int is_sorted_double(const double *arr, size_t n);

#ifdef __cplusplus
}
#endif

#endif /* SORT_C_H */
