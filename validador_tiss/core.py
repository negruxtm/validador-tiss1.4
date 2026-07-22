"""
Núcleo do Validador TISS.

Responsável por:
- Detectar a versão do padrão TISS e o tipo de mensagem do XML
- Validar a estrutura do XML contra o XSD oficial da ANS correspondente
- Agregar os erros estruturais e de regras de negócio em um único relatório

Sem qualquer limitação de CNPJ, prestador ou quantidade de arquivos:
este validador é de uso livre, ilimitado, para quantos prestadores você precisar.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lxml import etree

SCHEMAS_DIR = Path(__file__).parent / "schemas"


@dataclass
class ErroValidacao:
    codigo: str          # ex: "XSD-001", "NEG-014"
    severidade: str       # "ERRO" | "ALERTA"
    mensagem: str
    linha: Optional[int] = None
    caminho_xml: Optional[str] = None  # xpath aproximado do nó com erro

    def __str__(self) -> str:
        local = f" (linha {self.linha})" if self.linha else ""
        return f"[{self.severidade}] {self.codigo}{local}: {self.mensagem}"


@dataclass
class ResultadoValidacao:
    arquivo: str
    valido: bool
    versao_tiss: Optional[str] = None
    tipo_mensagem: Optional[str] = None  # ex: loteGuias, monitoramento, etc.
    total_guias: int = 0
    erros: list[ErroValidacao] = field(default_factory=list)
    alertas: list[ErroValidacao] = field(default_factory=list)

    def resumo(self) -> str:
        status = "VÁLIDO" if self.valido else "INVÁLIDO"
        linhas = [
            f"Arquivo: {self.arquivo}",
            f"Status: {status}",
            f"Versão TISS detectada: {self.versao_tiss or 'não identificada'}",
            f"Tipo de mensagem: {self.tipo_mensagem or 'não identificado'}",
            f"Guias encontradas: {self.total_guias}",
            f"Erros: {len(self.erros)} | Alertas: {len(self.alertas)}",
        ]
        for e in self.erros:
            linhas.append(f"  {e}")
        for a in self.alertas:
            linhas.append(f"  {a}")
        return "\n".join(linhas)

    def to_dict(self) -> dict:
        return {
            "arquivo": self.arquivo,
            "valido": self.valido,
            "versao_tiss": self.versao_tiss,
            "tipo_mensagem": self.tipo_mensagem,
            "total_guias": self.total_guias,
            "erros": [e.__dict__ for e in self.erros],
            "alertas": [a.__dict__ for a in self.alertas],
        }


# Mapeamento: namespace ou nome de elemento raiz -> arquivo xsd
# Populado a partir dos XSDs oficiais carregados em schemas/<versao>/.
# Estrutura real confirmada nos XSDs oficiais da ANS (Componente de Comunicação):
#   schemas/4.03.00/tissV4_03_00.xsd            -> elemento raiz <mensagemTISS> (guias/lote/glosa/etc.)
#   schemas/1.06.00/tissMonitoramentoV1_06_00.xsd -> elemento raiz <mensagemEnvioANS> (monitoramento)
VERSAO_PATTERN = re.compile(r"(\d\.\d{2}\.\d{2})")

# Elemento raiz do XML -> (arquivo xsd esperado, "família" de versão a usar como fallback)
ELEMENTO_RAIZ_PARA_XSD = {
    "mensagemTISS": "tissV4_03_00.xsd",
    "mensagemEnvioANS": "tissMonitoramentoV1_06_00.xsd",
}

# Tipos de mensagem reais, conforme o <choice> de prestadorParaOperadora / operadoraParaPrestador
# definido em tissV4_03_00.xsd. Usado apenas para fins informativos no relatório
# (a validação em si é feita pelo elemento raiz mensagemTISS, que já cobre todos eles).
TIPOS_MENSAGEM_PRESTADOR_OPERADORA = {
    "loteGuias", "loteAnexos", "solicitacaoDemonstrativoRetorno",
    "solicitacaoStatusProtocolo", "solicitacaoProcedimento", "solicitaStatusAutorizacao",
    "verificaElegibilidade", "cancelaGuia", "comunicacaoInternacao", "recursoGlosa",
    "solicitacaoStatusRecursoGlosa", "envioDocumentos",
}
TIPOS_MENSAGEM_OPERADORA_PRESTADOR = {
    "recebimentoLote", "recebimentoAnexo", "recebimentoRecursoGlosa", "demonstrativosRetorno",
    "situacaoProtocolo", "autorizacaoServicos", "situacaoAutorizacao", "respostaElegibilidade",
}
TODOS_TIPOS_MENSAGEM = TIPOS_MENSAGEM_PRESTADOR_OPERADORA | TIPOS_MENSAGEM_OPERADORA_PRESTADOR

# Elementos de guia reais, conforme tissGuiasV4_03_00.xsd (usado para contagem de guias)
ELEMENTOS_GUIA = {
    "guiaSP-SADT", "guiaResumoInternacao", "guiaHonorarios",
    "guiaConsulta", "guiaOdonto", "guiaSolicInternacao", "guiaPrincipal",
}


def _localname(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def detectar_versao_e_tipo(caminho_xml: str | Path) -> tuple[Optional[str], Optional[str], Optional[etree._ElementTree]]:
    """
    Faz parse do XML e tenta identificar:
    - a versão do padrão TISS (ex: 4.03.00), lida do elemento <Padrao> dentro do
      <cabecalho> (campo oficial, tipo ans:dm_versao no XSD). Mantém fallback para
      tags antigas/alternativas (ex: versaoPadrao) por robustez com arquivos não-padrão.
    - o tipo de mensagem (loteGuias, recursoGlosa, monitoramento, etc.), lido do
      elemento filho de prestadorParaOperadora/operadoraParaPrestador/Mensagem,
      conforme o <choice> definido nos XSDs oficiais.

    Retorna (versao, tipo_mensagem, tree). Se o parse falhar, tree é None.
    """
    try:
        parser = etree.XMLParser(recover=False, huge_tree=True)
        tree = etree.parse(str(caminho_xml), parser)
    except etree.XMLSyntaxError:
        return None, None, None

    root = tree.getroot()
    versao = None

    # Campo oficial: <cabecalho><Padrao>4.03.00</Padrao></cabecalho>
    for el in root.iter():
        if _localname(el.tag) == "Padrao" and el.text:
            match = VERSAO_PATTERN.search(el.text.strip())
            if match:
                versao = match.group(1)
                break

    # Fallback: tags não-oficiais usadas por algumas implementações/exemplos antigos
    if not versao:
        for el in root.iter():
            if _localname(el.tag) == "versaoPadrao" and el.text:
                match = VERSAO_PATTERN.search(el.text.strip())
                if match:
                    versao = match.group(1)
                    break

    # Último fallback: versão embutida no namespace (raro, mas alguns XMLs customizados fazem isso)
    if not versao and root.tag.startswith("{"):
        ns = root.tag.split("}")[0][1:]
        match = VERSAO_PATTERN.search(ns)
        if match:
            versao = match.group(1)

    # Tipo de mensagem real: primeiro filho dentro do choice de
    # prestadorParaOperadora / operadoraParaPrestador / Mensagem (monitoramento)
    tipo_mensagem = None
    for el in root.iter():
        nome = _localname(el.tag)
        if nome in TODOS_TIPOS_MENSAGEM:
            tipo_mensagem = nome
            break

    # Para o monitoramento (mensagemEnvioANS) e outros casos não cobertos pelo
    # choice de prestadorParaOperadora/operadoraParaPrestador, o "tipo" reportado
    # é o nome do próprio elemento raiz do XML (legível, ex: "mensagemEnvioANS")
    if not tipo_mensagem:
        tipo_mensagem = _localname(root.tag)

    return versao, tipo_mensagem, tree


def localizar_xsd(versao: str, tipo_mensagem: Optional[str], elemento_raiz: Optional[str] = None) -> Optional[Path]:
    """
    Localiza o arquivo XSD correspondente à versão/elemento raiz detectado.

    A estrutura oficial da ANS usa um único XSD "guarda-chuva" por família de
    mensagens (ex: tissV4_03_00.xsd cobre TODAS as mensagens prestador<->operadora:
    lote de guias, recurso de glosa, cancelamento, etc., através de um <choice> na
    estrutura). O monitoramento (operadora->ANS) usa outro XSD raiz, em outra pasta
    de versão (1.06.00). Por isso a busca é primariamente pelo elemento raiz real
    do XML, com fallback por nome de arquivo.
    """
    pasta_versao = SCHEMAS_DIR / versao
    if not pasta_versao.exists():
        return None

    candidatos = list(pasta_versao.glob("*.xsd"))
    if not candidatos:
        return None

    # 1) Busca direta pelo arquivo XSD que define o elemento raiz real do XML
    #    (ex: mensagemTISS -> tissV4_03_00.xsd, mensagemEnvioANS -> tissMonitoramentoV1_06_00.xsd)
    if elemento_raiz:
        nome_esperado = ELEMENTO_RAIZ_PARA_XSD.get(elemento_raiz)
        if nome_esperado:
            for c in candidatos:
                if c.name == nome_esperado:
                    return c
        # fallback: procura um xsd que declare esse elemento como <element name="...">
        for c in candidatos:
            try:
                conteudo = c.read_text(encoding="latin-1", errors="ignore")
            except OSError:
                continue
            if f'name="{elemento_raiz}"' in conteudo and "<element" in conteudo:
                return c

    # 2) Heurística por nome de arquivo / tipo de mensagem (fallback)
    if tipo_mensagem:
        for c in candidatos:
            if tipo_mensagem.lower() in c.stem.lower():
                return c

    # 3) Último fallback: maior arquivo .xsd que não seja claramente auxiliar
    auxiliares = {"xmldsig-core-schema.xsd", "tissassinaturadigital_v1.01.xsd"}
    principais = [c for c in candidatos if c.name.lower() not in auxiliares and "simpletypes" not in c.stem.lower() and "complextypes" not in c.stem.lower()]
    if principais:
        return sorted(principais, key=lambda p: p.stat().st_size, reverse=True)[0]
    return candidatos[0]


def validar_estrutura_xsd(tree: etree._ElementTree, caminho_xsd: Path) -> list[ErroValidacao]:
    """Valida a árvore XML já parseada contra um arquivo XSD específico."""
    erros: list[ErroValidacao] = []
    try:
        xsd_doc = etree.parse(str(caminho_xsd))
        schema = etree.XMLSchema(xsd_doc)
    except etree.XMLSchemaParseError as e:
        erros.append(ErroValidacao(
            codigo="XSD-000",
            severidade="ERRO",
            mensagem=f"Falha ao carregar schema XSD '{caminho_xsd.name}': {e}",
        ))
        return erros

    if not schema.validate(tree):
        for log_entry in schema.error_log:
            erros.append(ErroValidacao(
                codigo="XSD-VAL",
                severidade="ERRO",
                mensagem=log_entry.message,
                linha=log_entry.line,
                caminho_xml=log_entry.path,
            ))
    return erros


def calcular_hash_md5(valores_concatenados: str) -> str:
    """
    Calcula o HASH MD5 conforme especificação TISS: hash dos valores dos atributos
    da transação justapostos (sem as tags XML), lidos da esquerda para a direita.
    """
    return hashlib.md5(valores_concatenados.encode("utf-8")).hexdigest()


def contar_guias(tree: etree._ElementTree) -> int:
    contagem = 0
    for el in tree.getroot().iter():
        if _localname(el.tag) in ELEMENTOS_GUIA:
            contagem += 1
    return contagem
