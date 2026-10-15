"""Avaliador seguro de fórmulas de tarifação.

Não utiliza eval() nem exec(). A expressão é convertida numa árvore (`ast`)
e só são aceites números, variáveis, os operadores + - * / ** e as funções
de `ALLOWED_FUNCTIONS`. Qualquer outro nó (atributos, índices, chamadas a
nomes não autorizados, lambdas, comparações, strings…) é recusado antes de
qualquer cálculo. Todos os valores são `Decimal`.
"""

import ast
import operator
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

ALLOWED_FUNCTIONS = {
    "min": "Menor dos valores: min(a, b, …)",
    "max": "Maior dos valores: max(a, b, …)",
    "abs": "Valor absoluto: abs(a)",
    "round": "Arredondamento meio-para-cima: round(a) ou round(a, casas) com 0–6 casas",
}
ALLOWED_OPERATORS = ("+", "-", "*", "/", "**")

MAX_EXPRESSION_LENGTH = 500
MAX_NODES = 100
MAX_EXPONENT = 10


class FormulaError(ValueError):
    """Erro de validação ou execução de uma fórmula."""


def _number(value):
    if isinstance(value, bool):
        raise FormulaError("Valores booleanos não são números válidos.")

    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise FormulaError(f"Valor numérico inválido: {value!r}.") from None

    if not result.is_finite():
        raise FormulaError("A fórmula contém um número não finito.")

    return result


def _check_node(node, names):
    """Valida a forma da árvore sem calcular nada; recolhe as variáveis."""
    if isinstance(node, ast.Expression):
        _check_node(node.body, names)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise FormulaError("Só são permitidos números constantes.")
    elif isinstance(node, ast.Name):
        if node.id in ALLOWED_FUNCTIONS:
            raise FormulaError(f"'{node.id}' é uma função e tem de ser chamada com parênteses.")
        names.add(node.id)
    elif isinstance(node, ast.BinOp):
        if type(node.op) not in _BINARY_OPERATORS:
            raise FormulaError("Operador matemático não permitido.")
        _check_node(node.left, names)
        _check_node(node.right, names)
    elif isinstance(node, ast.UnaryOp):
        if type(node.op) not in _UNARY_OPERATORS:
            raise FormulaError("Operador unário não permitido.")
        _check_node(node.operand, names)
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise FormulaError("Chamada de função não permitida.")
        if node.func.id not in ALLOWED_FUNCTIONS:
            raise FormulaError(f"A função '{node.func.id}' não é permitida.")
        if node.keywords:
            raise FormulaError("Argumentos nomeados não são permitidos.")
        if not node.args:
            raise FormulaError(f"A função '{node.func.id}' precisa de argumentos.")
        for arg in node.args:
            _check_node(arg, names)
    else:
        raise FormulaError(f"Expressão não permitida: {type(node).__name__}.")


def parse_formula(expression):
    """Valida a sintaxe e devolve `(árvore, variáveis referenciadas)`."""
    if not isinstance(expression, str) or not expression.strip():
        raise FormulaError("A expressão é obrigatória.")

    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise FormulaError(f"A expressão não pode exceder {MAX_EXPRESSION_LENGTH} caracteres.")

    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError:
        raise FormulaError("A sintaxe da fórmula é inválida.") from None

    # Limita a complexidade para evitar expressões abusivas.
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise FormulaError("A fórmula é demasiado complexa.")

    names = set()
    _check_node(tree, names)
    return tree, names


def referenced_names(expression):
    """Variáveis usadas por uma expressão (valida a sintaxe)."""
    return parse_formula(expression)[1]


def _evaluate(node, variables):
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, variables)

    if isinstance(node, ast.Constant):
        return _number(node.value)

    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise FormulaError(f"Variável '{node.id}' não fornecida.")
        return _number(variables[node.id])

    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left, variables)
        right = _evaluate(node.right, variables)

        if isinstance(node.op, ast.Div) and right == 0:
            raise FormulaError("Divisão por zero.")

        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise FormulaError(f"O expoente máximo permitido é {MAX_EXPONENT}.")

        try:
            result = _BINARY_OPERATORS[type(node.op)](left, right)
        except (ArithmeticError, ValueError):
            raise FormulaError("Não foi possível calcular esta operação.") from None

        return _number(result)

    if isinstance(node, ast.UnaryOp):
        return _UNARY_OPERATORS[type(node.op)](_evaluate(node.operand, variables))

    # ast.Call (o único nó restante depois de `_check_node`)
    name = node.func.id
    args = [_evaluate(arg, variables) for arg in node.args]

    if name == "abs" and len(args) == 1:
        return abs(args[0])

    if name == "min":
        return min(args)

    if name == "max":
        return max(args)

    if name == "round" and len(args) in (1, 2):
        places = args[1] if len(args) == 2 else Decimal(0)

        if places != places.to_integral_value() or places < 0 or places > 6:
            raise FormulaError("O arredondamento aceita entre 0 e 6 casas decimais.")

        quantum = Decimal("1").scaleb(-int(places))

        return args[0].quantize(quantum, rounding=ROUND_HALF_UP)

    raise FormulaError(f"Número de argumentos inválido para '{name}'.")


def evaluate_formula(expression, variables):
    """Valida e calcula uma expressão matemática."""
    tree, _names = parse_formula(expression)
    return _evaluate(tree, variables)
