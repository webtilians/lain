"""Bounded Python-syntax lessons. Never eval/exec/compile untrusted source.

The lesson implements a scalar rule; World Core supplies the grid and neighbors.
Only booleans, small integers, comparisons and finite if/return blocks exist.
"""
import ast
import operator

LIFE_TEMPLATE = "def next_cell(alive, neighbors):\n    # Completa las reglas de nacimiento y supervivencia.\n    return False\n"
LIFE_HINT = "def next_cell(alive, neighbors):\n    if alive:\n        return neighbors == 2 or neighbors == 3\n    return neighbors == 3\n"
COMPARISONS = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
               ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}


class LessonError(ValueError):
    pass


def parse_source(source):
    if not isinstance(source, str) or len(source) > 4000:
        raise LessonError("El programa admite hasta 4000 caracteres.")
    try:
        tree = ast.parse(source)
    except (SyntaxError, RecursionError, ValueError) as error:
        raise LessonError(f"Línea {getattr(error, 'lineno', 1)}: revisa la sintaxis y la indentación.") from None
    if len(list(ast.walk(tree))) > 160:
        raise LessonError("Simplifica el programa: demasiadas instrucciones.")
    return tree


def life_function(source):
    tree = parse_source(source)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise LessonError("Escribe una única función: def next_cell(alive, neighbors):")
    fn = tree.body[0]
    args = fn.args
    if (fn.name != "next_cell" or [a.arg for a in args.args] != ["alive", "neighbors"]
            or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg or args.defaults
            or args.kw_defaults or fn.decorator_list or fn.returns or fn.type_comment
            or getattr(fn, "type_params", []) or any(a.annotation for a in args.args)):
        raise LessonError("La firma debe ser next_cell(alive, neighbors), sin argumentos adicionales.")
    allowed = (ast.FunctionDef, ast.arguments, ast.arg, ast.If, ast.Return, ast.BoolOp,
               ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.Compare, ast.Name, ast.Load,
               ast.Constant, *COMPARISONS)
    for node in ast.walk(fn):
        if not isinstance(node, allowed):
            raise LessonError(f"Línea {getattr(node, 'lineno', 1)}: usa if, return, and, or, not y comparaciones. No se permiten llamadas ni bucles.")
        if isinstance(node, ast.Name) and node.id not in {"alive", "neighbors"}:
            raise LessonError(f"Línea {node.lineno}: solo puedes consultar alive y neighbors.")
        if isinstance(node, ast.Constant) and not (type(node.value) in (int, bool) and 0 <= node.value <= 8):
            raise LessonError(f"Línea {node.lineno}: usa True, False o números de 0 a 8.")

    def expression(node, values):
        if isinstance(node, ast.Constant): return node.value
        if isinstance(node, ast.Name): return values[node.id]
        if isinstance(node, ast.UnaryOp): return not expression(node.operand, values)
        if isinstance(node, ast.BoolOp):
            result = expression(node.values[0], values)
            for part in node.values[1:]:
                if (isinstance(node.op, ast.And) and not result) or (isinstance(node.op, ast.Or) and result):
                    break
                result = expression(part, values)
            return result
        if isinstance(node, ast.Compare):
            left = expression(node.left, values)
            for op, other in zip(node.ops, node.comparators):
                right = expression(other, values)
                if not COMPARISONS[type(op)](left, right): return False
                left = right
            return True
        raise LessonError("Expresión incompleta.")

    def statements(block, values):
        for node in block:
            if isinstance(node, ast.Return):
                if node.value is None: raise LessonError(f"Línea {node.lineno}: devuelve True o False.")
                result = expression(node.value, values)
                if type(result) is not bool: raise LessonError(f"Línea {node.lineno}: el resultado debe ser True o False.")
                return result
            if isinstance(node, ast.If):
                result = statements(node.body if expression(node.test, values) else node.orelse, values)
                if result is not None: return result
        return None

    def run(alive, neighbors):
        result = statements(fn.body, {"alive": alive, "neighbors": neighbors})
        if result is None: raise LessonError("Falta un return para uno de los casos.")
        return result
    return run


def step_grid(grid, rule):
    size = len(grid)
    return [[int(rule(bool(grid[y][x]), sum(
        grid[ny][nx] for ny in range(max(0, y-1), min(size, y+2))
        for nx in range(max(0, x-1), min(size, x+2)) if (nx, ny) != (x, y))))
        for x in range(size)] for y in range(size)]


def test_life(source):
    try:
        rule = life_function(source)
        for alive in [False, True]:
            for neighbors in range(9):
                expected = neighbors == 3 or (alive and neighbors == 2)
                if rule(alive, neighbors) != expected:
                    return {"passed": False, "text": f"Caso fallido: alive={alive}, neighbors={neighbors}. Debe devolver {expected}.", "frames": []}
        grid = [[0] * 8 for _ in range(8)]
        for x, y in [(2,1), (3,2), (1,3), (2,3), (3,3)]: grid[y][x] = 1
        frames = [grid]
        for _ in range(8): frames.append(step_grid(frames[-1], rule))
        return {"passed": True, "text": "18/18 casos correctos. Simulación 8×8: los bordes exteriores están muertos; todas las células cambian a la vez.", "frames": frames}
    except LessonError as error:
        return {"passed": False, "text": str(error), "frames": []}


def program_modules(source):
    """Parse the fictional runtime's module loader; no arbitrary Python runs."""
    tree = parse_source(source)
    modules = []
    for node in tree.body:
        call = node.value if isinstance(node, ast.Expr) else None
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id == "use" and len(call.args) == 1 and not call.keywords
                and isinstance(call.args[0], ast.Constant) and type(call.args[0].value) is str):
            raise LessonError(f"Línea {getattr(node, 'lineno', 1)}: escribe use(\"nombre_del_modulo\").")
        if call.args[0].value not in modules: modules.append(call.args[0].value)
    if not modules or "routing" not in modules:
        raise LessonError('Incluye use("routing") para conectar el montaje.')
    return modules
