from __future__ import annotations

import ast
import math
import operator


class NumericExpressionError(ValueError):
    pass


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def evaluate_numeric_expression(text: str) -> float:
    expression = text.strip()
    if not expression:
        raise NumericExpressionError("empty expression")

    try:
        node = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise NumericExpressionError("invalid expression") from exc

    try:
        value = _evaluate_node(node.body)
    except (OverflowError, ZeroDivisionError) as exc:
        raise NumericExpressionError(str(exc)) from exc

    if not math.isfinite(value):
        raise NumericExpressionError("result is not finite")
    return float(value)


def _evaluate_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)

    if isinstance(node, ast.BinOp):
        operator_func = _BINARY_OPERATORS.get(type(node.op))
        if operator_func is None:
            raise NumericExpressionError("unsupported operator")
        return operator_func(_evaluate_node(node.left), _evaluate_node(node.right))

    if isinstance(node, ast.UnaryOp):
        operator_func = _UNARY_OPERATORS.get(type(node.op))
        if operator_func is None:
            raise NumericExpressionError("unsupported operator")
        return operator_func(_evaluate_node(node.operand))

    raise NumericExpressionError("unsupported expression")
