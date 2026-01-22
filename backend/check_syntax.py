#!/usr/bin/env python3
"""Comprehensive syntax checker for Python files."""
import ast
import sys
import py_compile
from pathlib import Path

def check_file(filepath: str) -> bool:
    """Check syntax of a Python file using multiple methods."""
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        return False
    
    errors = []
    
    # Method 1: AST parsing (most thorough)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        print(f"✅ AST parse: {filepath.name}")
    except SyntaxError as e:
        errors.append(f"AST parse error: {e}")
        print(f"❌ AST parse failed: {filepath.name}")
        print(f"   Line {e.lineno}: {e.text}")
        print(f"   {e.msg}")
    
    # Method 2: py_compile (catches some AST misses)
    try:
        py_compile.compile(str(filepath), doraise=True)
        print(f"✅ py_compile: {filepath.name}")
    except py_compile.PyCompileError as e:
        errors.append(f"py_compile error: {e}")
        print(f"❌ py_compile failed: {filepath.name}")
        print(f"   {e}")
    
    # Method 3: Import test (if it's a module)
    if filepath.stem != '__main__' and 'test' not in filepath.stem:
        try:
            # Try to import the module
            import importlib.util
            spec = importlib.util.spec_from_file_location(filepath.stem, filepath)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                print(f"✅ Import test: {filepath.name}")
        except Exception as e:
            # Import errors are OK, we just care about syntax
            if isinstance(e, SyntaxError):
                errors.append(f"Import syntax error: {e}")
                print(f"❌ Import syntax error: {filepath.name}")
                print(f"   {e}")
    
    if errors:
        print(f"\n❌ {filepath.name} has syntax errors:")
        for error in errors:
            print(f"   - {error}")
        return False
    
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        # Default: check confidence_engine.py
        files = ["confidence_engine.py"]
    
    all_passed = True
    for filepath in files:
        if not check_file(filepath):
            all_passed = False
        print()
    
    sys.exit(0 if all_passed else 1)

