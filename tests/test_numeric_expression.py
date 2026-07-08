import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_SPEC = spec_from_file_location(
    "numeric_expression",
    Path(__file__).resolve().parents[1]
    / "round_track_connector"
    / "numeric_expression.py",
)
numeric_expression = module_from_spec(_SPEC)
_SPEC.loader.exec_module(numeric_expression)

NumericExpressionError = numeric_expression.NumericExpressionError
evaluate_numeric_expression = numeric_expression.evaluate_numeric_expression


class NumericExpressionTests(unittest.TestCase):
    def test_accepts_plain_numbers(self):
        self.assertEqual(evaluate_numeric_expression("1.25"), 1.25)

    def test_evaluates_arithmetic_with_precedence(self):
        self.assertEqual(evaluate_numeric_expression("1 + 2 * 3"), 7.0)
        self.assertEqual(evaluate_numeric_expression("(1 + 2) * 3"), 9.0)
        self.assertEqual(evaluate_numeric_expression("10 / 4"), 2.5)

    def test_accepts_unary_signs(self):
        self.assertEqual(evaluate_numeric_expression("-1 + +2"), 1.0)

    def test_rejects_unsupported_expressions(self):
        for expression in ("", "1 ** 2", "abs(-1)", "__import__('os')", "1 // 2"):
            with self.subTest(expression=expression):
                with self.assertRaises(NumericExpressionError):
                    evaluate_numeric_expression(expression)

    def test_rejects_non_finite_results(self):
        with self.assertRaises(NumericExpressionError):
            evaluate_numeric_expression("1 / 0")


if __name__ == "__main__":
    unittest.main()
