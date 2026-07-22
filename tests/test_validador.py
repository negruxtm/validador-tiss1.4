"""Testes do Validador TISS."""
from pathlib import Path

import pytest

from validador_tiss.regras.negocio import validar_cnpj, validar_cpf
from validador_tiss.validador import validar_arquivo
from validador_tiss.tuss import CatalogoTUSS

EXEMPLOS = Path(__file__).parent.parent / "exemplos"


def test_cnpj_valido():
    assert validar_cnpj("11444777000161") is True


def test_cnpj_invalido():
    assert validar_cnpj("11444777000199") is False


def test_cnpj_todos_digitos_iguais_invalido():
    assert validar_cnpj("11111111111111") is False


def test_cpf_valido():
    assert validar_cpf("11144477735") is True


def test_cpf_invalido():
    assert validar_cpf("11144477700") is False


def test_arquivo_exemplo_valido():
    resultado = validar_arquivo(EXEMPLOS / "lote_valido.xml")
    assert resultado.versao_tiss == "4.03.00"
    assert resultado.tipo_mensagem == "loteGuias"
    assert resultado.total_guias == 1
    assert resultado.valido is True
    assert resultado.erros == []


def test_validacao_estrutural_contra_xsd_oficial_detecta_erro(tmp_path):
    """Garante que o XSD oficial real está sendo usado (não apenas regras de negócio)."""
    conteudo = (EXEMPLOS / "lote_valido.xml").read_text(encoding="utf-8")
    # Remove uma tag obrigatória pelo XSD (numeroGuiaPrestador) para forçar erro estrutural
    conteudo = conteudo.replace("<numeroGuiaPrestador>0001</numeroGuiaPrestador>", "")
    caminho = tmp_path / "sem_numero_guia.xml"
    caminho.write_text(conteudo, encoding="utf-8")
    resultado = validar_arquivo(caminho)
    assert resultado.valido is False
    assert any(e.codigo == "XSD-VAL" for e in resultado.erros)


def test_arquivo_inexistente():
    resultado = validar_arquivo("nao_existe.xml")
    assert resultado.valido is False
    assert any(e.codigo == "IO-000" for e in resultado.erros)


def test_xml_malformado(tmp_path):
    caminho = tmp_path / "malformado.xml"
    caminho.write_text("<mensagemTISS><cabecalho></mensagemTISS>", encoding="utf-8")
    resultado = validar_arquivo(caminho)
    assert resultado.valido is False
    assert any(e.codigo == "XML-000" for e in resultado.erros)


def test_arquivo_monitoramento_valido():
    """Versão 1.06.00 (monitoramento) usa <versaoPadrao>, não <Padrao>, e XSD próprio."""
    resultado = validar_arquivo(EXEMPLOS / "monitoramento_valido.xml")
    assert resultado.versao_tiss == "1.06.00"
    assert resultado.tipo_mensagem == "mensagemEnvioANS"
    assert resultado.valido is True
    assert resultado.erros == []


def test_versao_detectada_via_campo_padrao():
    """O campo oficial de versão é <Padrao>, dentro do cabecalho (não <versaoPadrao>)."""
    resultado = validar_arquivo(EXEMPLOS / "lote_valido.xml")
    assert resultado.versao_tiss == "4.03.00"


def test_cnpj_invalido_no_xml_real(tmp_path):
    conteudo = (EXEMPLOS / "lote_valido.xml").read_text(encoding="utf-8")
    conteudo = conteudo.replace("11444777000161", "11444777000199")
    caminho = tmp_path / "cnpj_invalido.xml"
    caminho.write_text(conteudo, encoding="utf-8")
    resultado = validar_arquivo(caminho)
    assert any(e.codigo == "NEG-CNPJ" for e in resultado.erros)


def test_importa_catalogo_tuss_csv_e_valida_codigo(tmp_path):
    tabela = tmp_path / "tuss.csv"
    tabela.write_text("Código TUSS;Descrição do termo;Início de vigência\n10101012;Consulta em consultório;01/01/2020\n", encoding="utf-8")
    catalogo = CatalogoTUSS.importar(tabela)
    assert len(catalogo) == 1
    resultado = validar_arquivo(EXEMPLOS / "lote_valido.xml", catalogo_tuss=catalogo)
    assert not any(e.codigo == "TUSS-NAO-ENCONTRADO" for e in resultado.erros)


def test_codigo_tuss_inexistente_invalida_arquivo(tmp_path):
    tabela = tmp_path / "tuss.csv"
    tabela.write_text("codigo;descricao\n99999999;Outro procedimento\n", encoding="utf-8")
    catalogo = CatalogoTUSS.importar(tabela)
    resultado = validar_arquivo(EXEMPLOS / "lote_valido.xml", catalogo_tuss=catalogo)
    assert resultado.valido is False
    assert any(e.codigo == "TUSS-NAO-ENCONTRADO" and "10101012" in e.mensagem for e in resultado.erros)


def test_ignora_codigo_de_tabela_que_nao_e_tuss(tmp_path):
    conteudo = (EXEMPLOS / "lote_valido.xml").read_text(encoding="utf-8")
    conteudo = conteudo.replace("<codigoTabela>22</codigoTabela>", "<codigoTabela>98</codigoTabela>")
    xml = tmp_path / "tabela_propria.xml"
    xml.write_text(conteudo, encoding="utf-8")
    resultado = validar_arquivo(xml, catalogo_tuss=CatalogoTUSS({}))
    assert not any(e.codigo == "TUSS-NAO-ENCONTRADO" for e in resultado.erros)


def test_importa_excel_ans_com_capa_e_cabecalho_na_linha_8(tmp_path):
    from openpyxl import Workbook

    arquivo = tmp_path / "TUSS 22 - VERSAO 202605.xlsx"
    wb = Workbook()
    capa = wb.active
    capa.title = "CAPA"
    capa["A6"] = "Tabela 22 - Terminologia de procedimentos e eventos em saúde"
    dados = wb.create_sheet("Tab 22  VERSÃO 202605")
    dados.append([])
    dados.append([])
    dados.append([])
    dados.append([])
    dados.append([])
    dados.append(["Tabela 22 - Terminologia de procedimentos e eventos em saúde"])
    dados.append([])
    dados.append(["Código do Termo", "Termo", "Descrição Detalhada", "Data de início de vigência", "Data de fim de vigência", "Data de fim de implantação"])
    dados.append([10101012, "Consulta em consultório", None, "13/02/2009", None, "15/10/2010"])
    wb.save(arquivo)

    catalogo = CatalogoTUSS.importar(arquivo)
    assert len(catalogo) == 1
    procedimento = catalogo.procedimentos["10101012"]
    assert procedimento.descricao == "Consulta em consultório"
    assert procedimento.inicio_vigencia == "2009-02-13"
    assert procedimento.fim_vigencia is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
