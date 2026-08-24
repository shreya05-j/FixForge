import tree_sitter_python as tspython
from tree_sitter import Language, Parser
from typing import Dict, Any, List

PY_LANGUAGE = Language(tspython.language())
parser = Parser()
parser.language = PY_LANGUAGE

def extract_functions_and_classes(source_code: str) -> Dict[str, Any]:
    """
    Uses Tree-sitter to parse Python code and extract function and class boundaries.
    """
    tree = parser.parse(bytes(source_code, "utf8"))
    root_node = tree.root_node
    
    extracted = {"functions": [], "classes": []}
    
    # A simple tree traversal to find functions and classes
    def traverse(node):
        if node.type == 'function_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                name = source_code[name_node.start_byte:name_node.end_byte]
                extracted["functions"].append({
                    "name": name,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "code": source_code[node.start_byte:node.end_byte]
                })
        elif node.type == 'class_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                name = source_code[name_node.start_byte:name_node.end_byte]
                extracted["classes"].append({
                    "name": name,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "code": source_code[node.start_byte:node.end_byte]
                })
        for child in node.children:
            traverse(child)

    traverse(root_node)
    return extracted
