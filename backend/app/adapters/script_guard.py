import ast
import re

ALLOWED_MODULES = {"bpy", "math", "mathutils", "bmesh"}
DENIED_CALLS = {"exec", "eval", "open", "compile", "__import__", "input", "breakpoint"}
DENIED_ATTRS = {
    "system",
    "popen",
    "remove",
    "rmtree",
    "unlink",
    "quit_blender",
    "save_as_mainfile",
    "save_mainfile",
    "open_mainfile",
    "revert_mainfile",
    "quit",
}
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,40}$")


class ScriptRejected(Exception):
    pass


def validate_names(object_name: str, material_name: str) -> None:
    if not NAME_RE.match(object_name or ""):
        raise ScriptRejected("object_name must be a short identifier")
    if not NAME_RE.match(material_name or ""):
        raise ScriptRejected("material_name must be a short identifier")


def validate_script(script: str, object_name: str, material_name: str) -> None:
    if not script or len(script) > 8000:
        raise ScriptRejected("script is empty or longer than 8000 characters")
    if "\x00" in script:
        raise ScriptRejected("script contains a null byte")
    if object_name not in script:
        raise ScriptRejected("script does not mention object_name")
    if material_name not in script:
        raise ScriptRejected("script does not mention material_name")
    try:
        tree = ast.parse(script)
    except SyntaxError as exc:
        raise ScriptRejected(f"script syntax error: {exc.msg}") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_MODULES:
                    raise ScriptRejected(f"import not allowed: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in ALLOWED_MODULES:
                raise ScriptRejected(f"import not allowed: {node.module}")
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in DENIED_CALLS:
                raise ScriptRejected(f"call not allowed: {name}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") or node.attr in DENIED_ATTRS:
                raise ScriptRejected(f"attribute not allowed: {node.attr}")


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""
