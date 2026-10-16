"""Avaliador seguro de fórmulas de tarifação.

Não utiliza eval() nem exec(). A expressão é convertida numa árvore (`ast`)
e só são aceites números, variáveis, os operadores + - * / ** e as funções
de `ALLOWED_FUNCTIONS`. Qualquer outro nó (atributos, índices, chamadas a
nomes não autorizados, lambdas, comparações, strings…) é recusado antes de
qualquer cálculo. Todos os valores são `Decimal`.

Além das variáveis que quem chama fornece, uma fórmula pode usar as
constantes do fornecedor (`PLATFORM_CONSTANTS`, ex.: `cambio_usd_aoa`) e
consultar tabelas de referência com `tabela("codigo", chave, "coluna")`. O
texto só é aceite como 1.º e 3.º argumento de `tabela` (e como chave).
Os valores vêm de `platform_inputs.current()`.
"""

import ast
import operator
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from apps.foundation.domain import platform_inputs
from apps.foundation.domain.system_parameters import PLATFORM_CONSTANTS


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

_SYMBOLS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Pow: "**", ast.UAdd: "+", ast.USub: "-"}

ALLOWED_FUNCTIONS = {
    "min": "Menor dos valores: min(a, b, …)",
    "max": "Maior dos valores: max(a, b, …)",
    "abs": "Valor absoluto: abs(a)",
    "round": "Arredondamento meio-para-cima: round(a) ou round(a, casas) com 0–6 casas",
    "tabela": 'Valor de uma tabela de referência do fornecedor: tabela("codigo", chave, "coluna")',
}
TABLE_FUNCTION = "tabela"
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
        if node.func.id == TABLE_FUNCTION:
            _check_table_call(node, names)
            return
        for arg in node.args:
            _check_node(arg, names)
    else:
        raise FormulaError(f"Expressão não permitida: {type(node).__name__}.")


def _is_text(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _check_table_call(node, names):
    if len(node.args) != 3:
        raise FormulaError('tabela() precisa de 3 argumentos: tabela("codigo", chave, "coluna").')
    code, key, column = node.args
    if not _is_text(code) or not code.value.strip():
        raise FormulaError('O 1.º argumento de tabela() é o código da tabela, entre aspas.')
    if not _is_text(column) or not column.value.strip():
        raise FormulaError('O 3.º argumento de tabela() é o nome da coluna, entre aspas.')
    if not _is_text(key):
        _check_node(key, names)


def referenced_tables(expression):
    """Códigos das tabelas de referência usadas por uma expressão."""
    tree, _ = parse_formula(expression)
    return {
        n.args[0].value.strip() for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == TABLE_FUNCTION
    }


class _Scope(dict):
    """Variáveis de quem chama + acesso preguiçoso aos valores do fornecedor."""

    def __init__(self, variables):
        super().__init__(variables or {})
        self._inputs = None

    def platform(self):
        if self._inputs is None:
            self._inputs = platform_inputs.current()
        return self._inputs


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


def _record(record, node, operation, operands, result):
    """Passo do cálculo (modo explicação): a subexpressão, a operação, os
    operandos já calculados e o resultado — pela ordem em que são feitos."""
    if record is not None:
        record.append({
            "step": len(record) + 1,
            "expression": ast.unparse(node),
            "operation": operation,
            "operands": [str(v) for v in operands],
            "result": str(result),
        })
    return result


def _evaluate(node, variables, record=None):
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, variables, record)

    if isinstance(node, ast.Constant):
        return _number(node.value)

    if isinstance(node, ast.Name):
        if node.id in variables:
            return _record(record, node, "VARIABLE", [], _number(variables[node.id]))
        if node.id in PLATFORM_CONSTANTS:
            value = variables.platform().constants.get(node.id)
            if value is None:
                raise FormulaError(f"A constante do fornecedor '{node.id}' não tem valor em vigor.")
            return _record(record, node, "CONSTANT", [], _number(value))
        raise FormulaError(f"Variável '{node.id}' não fornecida.")

    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left, variables, record)
        right = _evaluate(node.right, variables, record)

        if isinstance(node.op, ast.Div) and right == 0:
            raise FormulaError("Divisão por zero.")

        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise FormulaError(f"O expoente máximo permitido é {MAX_EXPONENT}.")

        try:
            result = _BINARY_OPERATORS[type(node.op)](left, right)
        except (ArithmeticError, ValueError):
            raise FormulaError("Não foi possível calcular esta operação.") from None

        return _record(record, node, _SYMBOLS[type(node.op)], [left, right], _number(result))

    if isinstance(node, ast.UnaryOp):
        operand = _evaluate(node.operand, variables, record)
        result = _UNARY_OPERATORS[type(node.op)](operand)
        if isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
            return result  # número negativo escrito na expressão, não é um passo
        return _record(record, node, _SYMBOLS[type(node.op)], [operand], result)

    # ast.Call (o único nó restante depois de `_check_node`)
    name = node.func.id
    if name == TABLE_FUNCTION:
        return _evaluate_table(node, variables, record)
    args = [_evaluate(arg, variables, record) for arg in node.args]

    if name == "abs" and len(args) == 1:
        return _record(record, node, "abs", args, abs(args[0]))

    if name == "min":
        return _record(record, node, "min", args, min(args))

    if name == "max":
        return _record(record, node, "max", args, max(args))

    if name == "round" and len(args) in (1, 2):
        places = args[1] if len(args) == 2 else Decimal(0)

        if places != places.to_integral_value() or places < 0 or places > 6:
            raise FormulaError("O arredondamento aceita entre 0 e 6 casas decimais.")

        quantum = Decimal("1").scaleb(-int(places))

        return _record(record, node, "round", args, args[0].quantize(quantum, rounding=ROUND_HALF_UP))

    raise FormulaError(f"Número de argumentos inválido para '{name}'.")


def _evaluate_table(node, variables, record):
    code = node.args[0].value.strip()
    column = node.args[2].value.strip()
    key_node = node.args[1]
    key = key_node.value if _is_text(key_node) else _evaluate(key_node, variables, record)
    table = variables.platform().tables.get(code)
    if table is None:
        raise FormulaError(f"A tabela de referência '{code}' não existe ou não tem versão em vigor.")
    try:
        raw = table.lookup(key, column)
    except KeyError as exc:
        raise FormulaError(str(exc.args[0])) from None
    if raw is None or raw == "":
        raise FormulaError(f"A tabela '{code}' não tem valor na coluna '{column}' para a chave '{key}'.")
    return _record(record, node, TABLE_FUNCTION, [code, key, column], _number(raw))


def evaluate_formula(expression, variables):
    """Valida e calcula uma expressão matemática."""
    tree, _names = parse_formula(expression)
    return _evaluate(tree, _Scope(variables))


def explain_formula(expression, variables):
    """Como `evaluate_formula`, mas devolve também os passos do cálculo:
    `(resultado, passos)`, cada passo com a subexpressão, a operação
    (VARIABLE para a substituição de uma variável), os operandos e o
    resultado intermédio."""
    tree, _names = parse_formula(expression)
    steps = []
    return _evaluate(tree, _Scope(variables), steps), steps
