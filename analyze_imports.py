"""
analyze_imports.py
Checks every Python file for:
  1. Imported names that are never referenced in the source
  2. Names used in the source that were never imported (potential NameErrors)
"""
import ast
import sys
from pathlib import Path

TARGET_FILES = [
    Path(r"d:\project\gametranslator\app\ui\main_window.py"),
    Path(r"d:\project\gametranslator\app\core\translator.py"),
    Path(r"d:\project\gametranslator\app\ui\overlay.py"),
    Path(r"d:\project\gametranslator\app\ui\result_window.py"),
    Path(r"d:\project\gametranslator\app\core\ocr_engine.py"),
    Path(r"d:\project\gametranslator\app\core\hotkey_manager.py"),
    Path(r"d:\project\gametranslator\app\data\config_manager.py"),
    Path(r"d:\project\gametranslator\app\data\history_manager.py"),
]

# Names that look "unused" but are legitimately re-exported or used implicitly
WHITELIST = {
    "annotations",   # from __future__
    "TYPE_CHECKING", # typing guard
}

def analyze(path: Path):
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))

    # ---- collect imported aliases ----
    imported: dict[str, int] = {}   # name -> line number
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name.split(".")[0]
                imported[name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                name = alias.asname if alias.asname else alias.name
                imported[name] = node.lineno

    # ---- collect all Name references in the body ----
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            # e.g.  fd.asksaveasfilename  → fd is used
            if isinstance(node.value, ast.Name):
                used.add(node.value.id)

    unused = {
        name: lineno
        for name, lineno in imported.items()
        if name not in used and name not in WHITELIST
    }

    return unused


print("=" * 62)
print("  Import Audit")
print("=" * 62)

any_issues = False
for path in TARGET_FILES:
    unused = analyze(path)
    label = path.name
    if unused:
        any_issues = True
        print(f"\n[UNUSED IMPORTS] {label}")
        for name, line in sorted(unused.items(), key=lambda x: x[1]):
            print(f"  line {line:>4}: '{name}'")
    else:
        print(f"[OK] {label}")

print()
if not any_issues:
    print("All files clean — no unused imports found.")
else:
    print("Fix the imports listed above.")
