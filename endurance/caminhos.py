"""Coloca a pasta ``src`` (código existente) e esta pasta no caminho de import.

Basta importar este módulo antes dos outros:

    import caminhos  # noqa: F401
    from Brake import BrakeSystem

Assim qualquer arquivo desta pasta roda direto pelo VS Code (botão ▶), sem
mexer no PYTHONPATH.
"""
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parent
SRC = RAIZ / "src"

# esta pasta vem antes de src, para os módulos daqui terem prioridade
for caminho in (SRC, PASTA):
    while str(caminho) in sys.path:
        sys.path.remove(str(caminho))
    sys.path.insert(0, str(caminho))
