"""
Ponto de entrada de alto nível do validador.

Uso como biblioteca:

    from validador_tiss.validador import validar_arquivo
    resultado = validar_arquivo("caminho/para/lote.xml")
    print(resultado.resumo())

Não há nenhuma limitação de prestador, CNPJ ou quantidade de arquivos:
use livremente para validar quantos arquivos de quantos prestadores precisar.
"""
from __future__ import annotations

from pathlib import Path

from .core import (
    ResultadoValidacao,
    contar_guias,
    detectar_versao_e_tipo,
    localizar_xsd,
    validar_estrutura_xsd,
)
from .regras.negocio import aplicar_regras_negocio


def validar_arquivo(caminho_xml: str | Path, catalogo_tuss=None) -> ResultadoValidacao:
    caminho_xml = Path(caminho_xml)
    nome_arquivo = caminho_xml.name

    if not caminho_xml.exists():
        resultado = ResultadoValidacao(arquivo=nome_arquivo, valido=False)
        resultado.erros.append(
            __erro_arquivo_nao_encontrado(nome_arquivo)
        )
        return resultado

    versao, tipo_mensagem, tree = detectar_versao_e_tipo(caminho_xml)
    elemento_raiz = tree.getroot().tag.split("}")[-1] if tree is not None else None
    resultado = ResultadoValidacao(
        arquivo=nome_arquivo,
        valido=True,
        versao_tiss=versao,
        tipo_mensagem=tipo_mensagem,
    )

    if tree is None:
        from .core import ErroValidacao
        resultado.valido = False
        resultado.erros.append(ErroValidacao(
            codigo="XML-000",
            severidade="ERRO",
            mensagem="Não foi possível interpretar o arquivo como XML válido (erro de sintaxe).",
        ))
        return resultado

    resultado.total_guias = contar_guias(tree)

    # Validação estrutural via XSD, se a versão foi identificada e o schema existe
    if versao:
        caminho_xsd = localizar_xsd(versao, tipo_mensagem, elemento_raiz)
        if caminho_xsd:
            erros_xsd = validar_estrutura_xsd(tree, caminho_xsd)
            resultado.erros.extend(erros_xsd)
        else:
            from .core import ErroValidacao
            resultado.alertas.append(ErroValidacao(
                codigo="XSD-NAOENCONTRADO",
                severidade="ALERTA",
                mensagem=(
                    f"Schema XSD para a versão {versao} não encontrado em "
                    f"validador_tiss/schemas/{versao}/. Validação estrutural pulada; "
                    f"apenas regras de negócio foram aplicadas."
                ),
            ))
    else:
        from .core import ErroValidacao
        resultado.alertas.append(ErroValidacao(
            codigo="VERSAO-NAOIDENTIFICADA",
            severidade="ALERTA",
            mensagem="Não foi possível identificar a versão do padrão TISS no arquivo.",
        ))

    # Regras de negócio complementares, independentes de XSD
    erros_negocio = aplicar_regras_negocio(tree)
    for erro in erros_negocio:
        if erro.severidade == "ERRO":
            resultado.erros.append(erro)
        else:
            resultado.alertas.append(erro)

    # A validação TUSS é opcional porque depende da versão oficial importada pelo usuário.
    # Quando fornecido, o catálogo é aplicado apenas a itens cuja tabela é 22 (TUSS).
    if catalogo_tuss is not None:
        from .tuss import validar_procedimentos_tuss
        erros_tuss = validar_procedimentos_tuss(tree, catalogo_tuss)
        resultado.erros.extend(erros_tuss)

    resultado.valido = len(resultado.erros) == 0
    return resultado


def __erro_arquivo_nao_encontrado(nome_arquivo: str):
    from .core import ErroValidacao
    return ErroValidacao(
        codigo="IO-000",
        severidade="ERRO",
        mensagem=f"Arquivo não encontrado: {nome_arquivo}",
    )


def validar_lote(caminhos_xml: list[str | Path], catalogo_tuss=None) -> list[ResultadoValidacao]:
    """Valida múltiplos arquivos de uma vez, sem nenhum limite de quantidade."""
    return [validar_arquivo(c, catalogo_tuss=catalogo_tuss) for c in caminhos_xml]
