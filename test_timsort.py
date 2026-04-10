"""Regression tests for timsort — stability, __lt__-only, key/reverse, boundary lengths."""
import random
import unittest
from timsort import timsort, MIN_MERGE


class LtOnly:
    __slots__ = ('val', 'idx')
    def __init__(self, val, idx=0):
        self.val = val; self.idx = idx
    def __lt__(self, other):
        return self.val < other.val
    def __repr__(self):
        return f'({self.val},{self.idx})'


def assert_stable(test, arr, msg=""):
    timsort(arr)
    for i in range(len(arr) - 1):
        test.assertFalse(arr[i+1][0] < arr[i][0],
            f'{msg} order wrong at {i}: {arr[i]} vs {arr[i+1]}')
        if arr[i][0] == arr[i+1][0]:
            test.assertLess(arr[i][1], arr[i+1][1],
                f'{msg} stability broken at {i}: {arr[i]} vs {arr[i+1]}')


class TestCorrectness(unittest.TestCase):
    def test_empty_and_single(self):
        self.assertEqual(timsort([]), [])
        self.assertEqual(timsort([1]), [1])

    def test_two_elements(self):
        a = [2, 1]; timsort(a); self.assertEqual(a, [1, 2])

    def test_sorted(self):
        a = list(range(200)); timsort(a); self.assertEqual(a, list(range(200)))

    def test_reverse(self):
        a = list(range(200, 0, -1)); timsort(a); self.assertEqual(a, list(range(1, 201)))

    def test_all_equal(self):
        a = [5] * 100; timsort(a); self.assertEqual(a, [5] * 100)

    def test_large_random(self):
        for seed in range(10):
            random.seed(seed)
            a = [random.randint(-10000, 10000) for _ in range(10000)]
            expected = sorted(a)
            timsort(a)
            self.assertEqual(a, expected, f'seed={seed}')

    def test_boundary_lengths(self):
        for n in [31, 32, 33, 63, 64, 65, 127, 128, 129]:
            random.seed(42)
            a = [random.randint(0, 100) for _ in range(n)]
            expected = sorted(a); timsort(a)
            self.assertEqual(a, expected, f'n={n}')


class TestStability(unittest.TestCase):
    def test_merge_hi_repro(self):
        a = [(7,0),(3,1),(2,2),(1,3),(2,4),(4,5),(5,6),(3,7),(7,8),(9,9),
             (7,10),(2,11),(9,12),(2,13),(3,14),(4,15),(8,16),(7,17),(3,18),
             (8,19),(0,20),(7,21),(5,22),(9,23),(3,24),(6,25),(0,26),(9,27),
             (5,28),(5,29),(0,30),(4,31),(2,32)]
        assert_stable(self, a)

    def test_merge_lo_repro(self):
        a = [(2,0),(4,1),(2,2),(3,3),(0,4),(0,5),(2,6),(0,7),(2,8),(4,9),
             (1,10),(2,11),(0,12),(4,13),(0,14),(2,15),(2,16),(4,17),(3,18),
             (2,19),(2,20),(1,21),(3,22),(2,23),(1,24),(0,25),(1,26),(1,27),
             (1,28),(2,29),(3,30),(0,31),(4,32),(3,33)]
        assert_stable(self, a)

    def test_merge_lo_gallop_repro(self):
        a = [(3,0),(6,1),(8,2),(0,3),(4,4),(4,5),(0,6),(2,7),(5,8),(7,9),
             (5,10),(8,11),(4,12),(2,13),(5,14),(2,15),(6,16),(8,17),(9,18),
             (2,19),(8,20),(0,21),(3,22),(6,23),(8,24),(0,25),(3,26),(6,27),
             (2,28),(8,29),(6,30),(0,31),(1,32)]
        assert_stable(self, a)

    def test_stability_few_keys_small(self):
        for n in [33, 50, 64, 100]:
            for seed in range(20):
                random.seed(seed)
                a = [(random.randint(0, 5), i) for i in range(n)]
                assert_stable(self, a, f'n={n} seed={seed}')

    def test_stability_few_keys_large(self):
        for seed in range(20):
            random.seed(seed)
            a = [(random.randint(0, 5), i) for i in range(500)]
            assert_stable(self, a, f'seed={seed}')

    def test_stability_force_merge_hi(self):
        for right_size in [10, 20, 31, 32]:
            left = [(i % 8, i) for i in range(100)]
            right = [(i % 8, 100 + i) for i in range(right_size)]
            a = left + right
            a[:100] = sorted(a[:100])
            a[100:] = sorted(a[100:])
            timsort(a)
            for i in range(len(a) - 1):
                if a[i][0] == a[i+1][0]:
                    self.assertLess(a[i][1], a[i+1][1],
                        f'right_size={right_size} stability broken at {i}')

    def test_stability_stress(self):
        for n in [33, 64, 100, 128, 200, 500]:
            for num_keys in [2, 3, 5, 10]:
                for seed in range(10):
                    random.seed(seed * 1000 + n)
                    a = [(random.randint(0, num_keys - 1), i) for i in range(n)]
                    assert_stable(self, a, f'n={n} keys={num_keys} seed={seed}')


class TestLtOnly(unittest.TestCase):
    def test_lt_only_small(self):
        a = [LtOnly(v, i) for i, v in enumerate([3,1,4,1,5,9,2,6])]
        timsort(a)
        vals = [x.val for x in a]
        self.assertEqual(vals, sorted(vals))

    def test_lt_only_boundary(self):
        for n in [31, 32, 33, 40, 64]:
            random.seed(42)
            a = [LtOnly(random.randint(0, 20), i) for i in range(n)]
            timsort(a)
            for i in range(len(a) - 1):
                self.assertFalse(a[i+1] < a[i], f'n={n} order wrong at {i}')

    def test_lt_only_large(self):
        random.seed(0)
        a = [LtOnly(random.randint(0, 100), i) for i in range(500)]
        timsort(a)
        for i in range(len(a) - 1):
            self.assertFalse(a[i+1] < a[i])


class TestKeyReverse(unittest.TestCase):
    def test_key_function(self):
        a = ['banana', 'apple', 'cherry', 'date']
        timsort(a, key=len)
        self.assertEqual(a, ['date', 'apple', 'banana', 'cherry'])

    def test_reverse(self):
        a = [3, 1, 4, 1, 5, 9, 2, 6]
        timsort(a, reverse=True)
        self.assertEqual(a, [9, 6, 5, 4, 3, 2, 1, 1])

    def test_key_and_reverse(self):
        a = ['banana', 'apple', 'cherry', 'date']
        timsort(a, key=len, reverse=True)
        # cherry(6) and banana(6) are equal by len; stability preserves original order
        self.assertEqual(a, ['banana', 'cherry', 'apple', 'date'])

    def test_reverse_stability(self):
        a = [(3, 0), (1, 1), (3, 2), (1, 3), (2, 4)]
        timsort(a, key=lambda x: x[0], reverse=True)
        # Descending by key, stable within equal keys
        keys = [x[0] for x in a]
        self.assertEqual(keys, [3, 3, 2, 1, 1])
        # Original order preserved within equal keys
        self.assertEqual(a[0][1], 0)
        self.assertEqual(a[1][1], 2)
        self.assertEqual(a[3][1], 1)
        self.assertEqual(a[4][1], 3)

    def test_key_large_random(self):
        random.seed(42)
        a = [random.randint(-1000, 1000) for _ in range(1000)]
        expected = sorted(a, key=lambda x: -x)
        timsort(a, key=lambda x: -x)
        self.assertEqual(a, expected)

    def test_reverse_large_random(self):
        random.seed(42)
        a = [random.randint(-1000, 1000) for _ in range(1000)]
        expected = sorted(a, reverse=True)
        timsort(a, reverse=True)
        self.assertEqual(a, expected)


if __name__ == '__main__':
    unittest.main()
