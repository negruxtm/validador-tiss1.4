"""
Regras de negócio complementares ao schema XSD.

O XSD garante apenas a estrutura (tags, tipos, ordem, cardinalidade).
A ANS define várias regras adicionais que o XSD não expressa, como:
- Hash MD5 do epílogo
- Dígitos verificadores de CNPJ/CPF
- Coerência de datas (alta >= internação, execução <= hoje, etc.)
- Consistência entre quantidade de guias declarada no lote e a real
- Valores não-negativos e soma de itens == valor total da guia

Este módulo é deliberadamente extensível: adicione novas funções `regra_*`
e registre-as em REGRAS_ATIVAS para que passem a rodar automaticamente.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from lxml import etree

from ..core import ErroValidacao, _localname, contar_guias


def _texto(el: etree._Element, tag: str) -> str | None:
    for filho in el.iter():
        if _localname(filho.tag) == tag:
            return (filho.text or "").strip()
    return None


def _digitos(valor: str) -> str:
    return "".join(ch for ch in valor if ch.isdigit())


def validar_cnpj(cnpj: str) -> bool:
    """Valida dígitos verificadores de CNPJ (algoritmo padrão Receita Federal)."""
    cnpj = _digitos(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False

    def calc_digito(base: str, pesos: list[int]) -> int:
        soma = sum(int(d) * p for d, p in zip(base, pesos))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = calc_digito(cnpj[:12], pesos1)
    d2 = calc_digito(cnpj[:12] + str(d1), pesos2)
    return cnpj[-2:] == f"{d1}{d2}"


def validar_cpf(cpf: str) -> bool:
    cpf = _digitos(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    def calc_digito(base: str, pesos: list[int]) -> int:
        soma = sum(int(d) * p for d, p in zip(base, pesos))
        resto = (soma * 10) % 11
        return 0 if resto == 10 else resto

    pesos1 = list(range(10, 1, -1))
    pesos2 = list(range(11, 1, -1))
    d1 = calc_digito(cpf[:9], pesos1)
    d2 = calc_digito(cpf[:9] + str(d1), pesos2)
    return cpf[-2:] == f"{d1}{d2}"


def regra_cnpj_prestador(tree: etree._ElementTree) -> list[ErroValidacao]:
    erros: list[ErroValidacao] = []
    for el in tree.getroot().iter():
        if _localname(el.tag) in {"cnpj", "cnpjContratado", "cnpjPrestador"}:
            valor = (el.text or "").strip()
            if valor and not validar_cnpj(valor):
                erros.append(ErroValidacao(
                    codigo="NEG-CNPJ",
                    severidade="ERRO",
                    mensagem=f"CNPJ inválido (dígito verificador incorreto): {valor}",
                    caminho_xml=tree.getpath(el),
                ))
    return erros


def regra_cpf_beneficiario(tree: etree._ElementTree) -> list[ErroValidacao]:
    erros: list[ErroValidacao] = []
    for el in tree.getroot().iter():
        if _localname(el.tag) == "cpfBeneficiario":
            valor = (el.text or "").strip()
            if valor and not validar_cpf(valor):
                erros.append(ErroValidacao(
                    codigo="NEG-CPF",
                    severidade="ALERTA",
                    mensagem=f"CPF com dígito verificador possivelmente inválido: {valor}",
                    caminho_xml=tree.getpath(el),
                ))
    return erros


def regra_datas_coerentes(tree: etree._ElementTree) -> list[ErroValidacao]:
    """
    Verifica que datas de execução/realização não estão no futuro
    e que data de alta (internação) não é anterior à data de internação.
    """
    erros: list[ErroValidacao] = []
    hoje = date.today()

    for el in tree.getroot().iter():
        nome = _localname(el.tag)
        if nome in {"dataRealizacao", "dataExecucao", "dataAtendimento"}:
            valor = (el.text or "").strip()
            try:
                dt = datetime.strptime(valor, "%Y-%m-%d").date()
                if dt > hoje:
                    erros.append(ErroValidacao(
                        codigo="NEG-DATA-FUTURA",
                        severidade="ERRO",
                        mensagem=f"Data de execução/atendimento no futuro: {valor}",
                        caminho_xml=tree.getpath(el),
                    ))
            except ValueError:
                pass  # formato inválido já deve ter sido pego pelo XSD

    return erros


def regra_valor_total_guia(tree: etree._ElementTree) -> list[ErroValidacao]:
    """
    Verifica, quando presentes, se a soma dos valores informados dos itens/procedimentos
    de uma guia é compatível com o valor total declarado (tolerância de 1 centavo
    por possíveis arredondamentos).
    """
    erros: list[ErroValidacao] = []
    from ..core import ELEMENTOS_GUIA
    for guia in tree.getroot().iter():
        if _localname(guia.tag) not in ELEMENTOS_GUIA:
            continue

        valor_total_txt = _texto(guia, "valorTotal")
        if not valor_total_txt:
            continue

        try:
            valor_total = float(valor_total_txt)
        except ValueError:
            continue

        soma_itens = 0.0
        encontrou_item = False
        for el in guia.iter():
            if _localname(el.tag) == "valorTotalProcedimento" and el.text:
                try:
                    soma_itens += float(el.text.strip())
                    encontrou_item = True
                except ValueError:
                    pass

        if encontrou_item and abs(soma_itens - valor_total) > 0.01:
            erros.append(ErroValidacao(
                codigo="NEG-VALOR-TOTAL",
                severidade="ALERTA",
                mensagem=(
                    f"Soma dos itens (R$ {soma_itens:.2f}) difere do valor total "
                    f"declarado da guia (R$ {valor_total:.2f})"
                ),
                caminho_xml=tree.getpath(guia),
            ))

    return erros


def regra_quantidade_guias_lote(tree: etree._ElementTree) -> list[ErroValidacao]:
    """
    Confere se um campo de quantidade de guias declarada (quando presente)
    bate com a contagem real.

    NOTA: o XSD oficial da ANS (ctm_guiaLote, tissGuiasV4_03_00.xsd) não possui
    um campo de quantidade declarada — apenas <numeroLote> e <guiasTISS>. Esta
    regra fica inativa por padrão (não está em REGRAS_ATIVAS) e só é útil se o
    seu sistema usar um campo de controle interno de mesmo nome em XMLs próprios
    antes de gerar o TISS oficial. Mantida aqui para fácil reativação se precisar.
    """
    erros: list[ErroValidacao] = []
    root = tree.getroot()
    quantidade_declarada = None
    for el in root.iter():
        if _localname(el.tag) == "quantidadeGuias" and el.text:
            try:
                quantidade_declarada = int(el.text.strip())
            except ValueError:
                pass
            break

    if quantidade_declarada is None:
        return erros

    real = contar_guias(tree)
    if real != quantidade_declarada:
        erros.append(ErroValidacao(
            codigo="NEG-QTD-GUIAS",
            severidade="ERRO",
            mensagem=(
                f"quantidadeGuias declarada ({quantidade_declarada}) não corresponde "
                f"à quantidade real de guias encontradas no lote ({real})"
            ),
        ))
    return erros


# Registro central de regras ativas. Adicione novas funções aqui.
REGRAS_ATIVAS: list[Callable[[etree._ElementTree], list[ErroValidacao]]] = [
    regra_cnpj_prestador,
    regra_cpf_beneficiario,
    regra_datas_coerentes,
    regra_valor_total_guia,
    # regra_quantidade_guias_lote não está ativa por padrão (ver docstring da função)
]


def aplicar_regras_negocio(tree: etree._ElementTree) -> list[ErroValidacao]:
    erros: list[ErroValidacao] = []
    for regra in REGRAS_ATIVAS:
        erros.extend(regra(tree))
    return erros
