#!/usr/bin/env python3
"""
Ponto de entrada do executável standalone do Validador TISS.

- Com argumentos de linha de comando: comporta-se como CLI normal.
- Sem argumentos (duplo-clique): abre a interface gráfica.
"""
from __future__ import annotations

import glob
import os
import sys

if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS  # type: ignore[attr-defined]
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from validador_tiss.cli import main as cli_main  # noqa: E402
from validador_tiss.validador import validar_arquivo  # noqa: E402


def _pausar_antes_de_sair() -> None:
    """Mantém a janela aberta no Windows para o usuário ler o resultado.
    Em ambientes não-interativos (CI, pipes) o input() lança EOFError — ignorado."""
    if os.name == "nt":
        try:
            input("\nPressione ENTER para fechar...")
        except EOFError:
            pass


def modo_interativo() -> int:
    print("=" * 70)
    print(" VALIDADOR TISS — uso ilimitado, sem trava de CNPJ/prestador")
    print("=" * 70)
    print()
    print("Arraste um arquivo .xml para esta janela e pressione ENTER,")
    print("ou digite o caminho do arquivo/pasta a validar.")
    print("Pode informar vários caminhos separados por ponto e vírgula (;).")
    print("Digite 'sair' para encerrar.")
    print()

    while True:
        try:
            entrada = input("Caminho do arquivo/pasta (ou 'sair'): ").strip().strip('"')
        except EOFError:
            return 0

        if not entrada:
            continue
        if entrada.lower() in {"sair", "exit", "q"}:
            return 0

        caminhos_informados = [c.strip().strip('"') for c in entrada.split(";") if c.strip()]
        caminhos: list[str] = []
        for caminho in caminhos_informados:
            if os.path.isdir(caminho):
                caminhos.extend(glob.glob(os.path.join(caminho, "*.xml")))
            else:
                expandido = glob.glob(caminho)
                caminhos.extend(expandido if expandido else [caminho])

        if not caminhos:
            print(f"  Nenhum arquivo .xml encontrado em: {entrada}\n")
            continue

        print()
        for caminho in caminhos:
            resultado = validar_arquivo(caminho)
            print(resultado.resumo())
            print("-" * 70)
        print()


def main() -> int:
    if len(sys.argv) > 1:
        codigo = cli_main(sys.argv[1:])
        _pausar_antes_de_sair()
        return codigo

    from validador_tiss.gui import main as gui_main
    return gui_main()


if __name__ == "__main__":
    sys.exit(main())
