import tree_sitter_python as tspython
from tree_sitter import Language, Parser

PY_LANGUAGE = Language(tspython.language())
parser = Parser()
parser.language = PY_LANGUAGE

def parse_code(code: bytes):
    tree = parser.parse(code)
    # Extract functions and classes logic here
    return tree
