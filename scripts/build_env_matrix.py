from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
paths = sorted(ROOT.rglob('*.py'))
patterns = [
    re.compile(r"os\.getenv\(\s*['\"]([A-Z][A-Z0-9_]*)"),
    re.compile(r"os\.environ\.get\(\s*['\"]([A-Z][A-Z0-9_]*)"),
    re.compile(r"os\.environ\[\s*['\"]([A-Z][A-Z0-9_]*)"),
]
rows = {}
for path in paths:
    if any(part in {'tests', '__pycache__'} for part in path.parts):
        continue
    text = path.read_text(errors='ignore')
    names = sorted({name for pattern in patterns for name in pattern.findall(text)})
    if names:
        rows[str(path.relative_to(ROOT))] = names

out = ROOT / 'docs' / 'negobot-env-matrix-2026-08.md'
lines = [
    '# Matriz sanitizada de variáveis do NEGOBOT MOZ',
    '',
    'Este documento contém apenas nomes de variáveis encontrados no código; não contém valores, tokens ou passwords.',
    '',
]
for path, names in rows.items():
    lines.append(f'## `{path}`')
    lines.append('')
    lines.append('| Variável |')
    lines.append('|---|')
    for name in names:
        lines.append(f'| `{name}` |')
    lines.append('')
out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print({'files': len(rows), 'variables': len(set(name for names in rows.values() for name in names)), 'output': str(out)})
