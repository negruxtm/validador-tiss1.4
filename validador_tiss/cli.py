#!/usr/bin/env python3
"""
CLI do Validador TISS — uso ilimitado, sem amarração a CNPJ/prestador.

Exemplos:
    python -m validador_tiss.cli arquivo.xml
    python -m validador_tiss.cli pasta_com_xmls/*.xml
    python -m validador_tiss.cli --json arquivo.xml > resultado.json
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

from .validador import validar_arquivo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Valida arquivos XML no padrão TISS (estrutura XSD + regras de negócio)."
    )
    parser.add_argument(
        "arquivos", nargs="+",
        help="Caminho(s) para arquivo(s) XML, ou padrões glob (ex: lotes/*.xml)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Imprime o resultado em formato JSON em vez de texto legível",
    )
    parser.add_argument(
        "--apenas-erros", action="store_true",
        help="Ao final, retorna código de saída != 0 se houver qualquer arquivo inválido",
    )
    args = parser.parse_args(argv)

    caminhos: list[str] = []
    for padrao in args.arquivos:
        expandido = glob.glob(padrao)
        caminhos.extend(expandido if expandido else [padrao])

    if not caminhos:
        print("Nenhum arquivo encontrado para os padrões informados.", file=sys.stderr)
        return 2

    algum_invalido = False
    resultados_json = []

    for caminho in caminhos:
        resultado = validar_arquivo(caminho)
        if not resultado.valido:
            algum_invalido = True

        if args.json:
            resultados_json.append(resultado.to_dict())
        else:
            print(resultado.resumo())
            print("-" * 70)

    if args.json:
        print(json.dumps(resultados_json, ensure_ascii=False, indent=2))

    if args.apenas_erros and algum_invalido:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
