"""Tests of mathematical edge cases that commonly corrupt PUMS answers."""
import unittest
from fractions import Fraction

import pandas as pd

from solve import formatted, mean, quantile


class StatisticsTests(unittest.TestCase):
    def test_half_away_from_zero(self):
        self.assertEqual(formatted(Fraction(5, 2), 'integer'), '3')
        self.assertEqual(formatted(Fraction(-5, 2), 'integer'), '-3')
        self.assertEqual(formatted(Fraction(12345, 1000), 'decimal2'), '12.35')
        self.assertEqual(formatted(Fraction(2, 5), 'decimal2'), '0.40')

    def test_exact_half_uses_lower_value(self):
        frame = pd.DataFrame({'v': [10, 20], 'w': [1, 1]})
        self.assertEqual(quantile(frame, 'v', 'w'), 10)

    def test_signed_weights_require_first_crossing(self):
        frame = pd.DataFrame({'v': [1, 2, 3, 4], 'w': [6, -5, 1, 8]})
        self.assertEqual(quantile(frame, 'v', 'w'), 1)

    def test_tied_values_must_be_grouped(self):
        frame = pd.DataFrame({'v': [1, 1, 2], 'w': [10, -9, 9]})
        self.assertEqual(quantile(frame, 'v', 'w'), 2)

    def test_zero_wages_are_part_of_mean(self):
        frame = pd.DataFrame({'v': [0, 100], 'w': [3, 1]})
        self.assertEqual(mean(frame, 'v', 'w'), 25)


if __name__ == '__main__':
    unittest.main()
