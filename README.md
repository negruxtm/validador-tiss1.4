# Validador TISS — open source, sem limite de prestador/CNPJ

Validador próprio para arquivos no padrão TISS (ANS), construído em Python,
sem qualquer trava de licenciamento, CNPJ ou quantidade de uso. Pode validar
quantos prestadores e quantos arquivos você precisar. Já vem com os XSDs
oficiais da ANS (versões 4.03.00 — guias/lotes/glosa/etc. — e 1.06.00 —
monitoramento) embutidos, validando estruturalmente de verdade.

## Interface gráfica e validação TUSS

Ao abrir `validador-tiss.exe`, o aplicativo apresenta uma interface gráfica para
selecionar vários XMLs ou uma pasta, acompanhar os resultados, consultar os
detalhes de cada erro e exportar um relatório CSV.

Use o botão **Importar tabela TUSS** para selecionar a planilha oficial em CSV
ou XLSX. O aplicativo reconhece colunas comuns de código, descrição e vigência,
salva o catálogo no perfil do usuário e o reutiliza nas próximas execuções.
Somente itens marcados com `<codigoTabela>22</codigoTabela>` são conferidos. Sem
uma tabela carregada, a interface informa que essa etapa foi ignorada e continua
com as validações estrutural e de negócio.

## Executável pronto (sem precisar instalar Python)

⚠️ O executável já compilado em `dist/validador-tiss` neste pacote é para
**Linux**. Se você usa **Windows**, veja a seção "Gerando o .exe do Windows"
abaixo — é rápido e gratuito via GitHub Actions.

Uso no Linux:

```bash
# Modo linha de comando — valida um arquivo e mostra o relatório
./validador-tiss caminho/lote_guias.xml

# Vários arquivos de uma vez (sem limite de prestador/CNPJ)
./validador-tiss "lotes/*.xml"

# Saída em JSON
./validador-tiss --json arquivo.xml

# Sem nenhum argumento: abre a interface gráfica
./validador-tiss
```

No Windows, dê duplo clique em `validador-tiss.exe` para abrir a interface.
Para automações e terminal, use o executável separado `validador-tiss-cli.exe`.

### Compilando manualmente (se tiver acesso a uma máquina Windows/macOS)

Caso prefira compilar você mesmo em vez de usar o GitHub Actions, rode isto
*na própria máquina Windows/macOS de destino* (PyInstaller não faz compilação
cruzada — compilar em Linux não gera um `.exe` válido para Windows):

```bash
pip install -r requirements.txt
pip install pyinstaller

pyinstaller --name validador-tiss --onefile --console ^
  --add-data "validador_tiss/schemas;validador_tiss/schemas" ^
  --hidden-import lxml.etree --hidden-import lxml._elementpath ^
  validador_tiss_app.py
```

(No Windows use `;` no `--add-data` como acima; no Linux/macOS use `:` em vez
de `;`.) O executável final aparece em `dist/validador-tiss.exe`.

## Gerando o .exe do Windows via GitHub Actions (recomendado)

Como o executável incluído neste pacote foi compilado em Linux, ele **não roda
no Windows**. A forma mais simples de gerar o `.exe` real do Windows, sem
precisar de uma máquina Windows própria, é usar o GitHub Actions (gratuito):
este projeto já vem com o workflow pronto em `.github/workflows/build-windows.yml`.

Passo a passo:

1. Crie um repositório novo no GitHub (pode ser privado).
2. Suba todo o conteúdo deste pacote para o repositório:
   ```bash
   git init
   git add .
   git commit -m "Validador TISS"
   git branch -M main
   git remote add origin https://github.com/SEU_USUARIO/validador-tiss.git
   git push -u origin main
   ```
3. No GitHub, abra a aba **Actions** do repositório. O workflow "Build Windows
   EXE" já vai disparar automaticamente após o push. Aguarde ficar verde
   (leva uns 2-3 minutos).
4. Clique no workflow concluído → na seção **Artifacts**, baixe
   `validador-tiss-windows` → dentro tem o `validador-tiss.exe`, pronto para
   usar em qualquer Windows, sem precisar instalar Python nem nada.

### Alternativa: gerar uma Release oficial com link de download direto

Se preferir um link fixo de download (em vez de pegar pelos Artifacts), crie
uma tag de versão e suba ela também:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Isso vai disparar o mesmo build, mas dessa vez ele também publica o `.exe`
na aba **Releases** do repositório, com um link permanente de download.

### Usando o .exe no Windows

Depois de baixado:
- **`validador-tiss.exe`** → abre a interface gráfica.
- **`validador-tiss-cli.exe`** → versão para cmd, PowerShell e automações:
  ```cmd
  validador-tiss-cli.exe caminho\lote_guias.xml
  validador-tiss-cli.exe --json arquivo.xml
  validador-tiss-cli.exe "lotes\*.xml"
  ```

Nenhuma instalação de Python, lxml ou qualquer dependência é necessária no
computador onde o `.exe` for executado — tudo (incluindo os XSDs oficiais)
já está embutido dentro do arquivo `.exe`.



1. **Detecta automaticamente** a versão do padrão TISS e o tipo de mensagem a
   partir do próprio XML, lendo o campo oficial correto conforme a família de
   schema: `<cabecalho><Padrao>4.03.00</Padrao></cabecalho>` para mensagens de
   guias/lote/glosa/etc. (schema `tissV4_03_00.xsd`), ou
   `<cabecalho><versaoPadrao>1.06.00</versaoPadrao></cabecalho>` para mensagens
   de monitoramento (schema `tissMonitoramentoV1_06_00.xsd`) — esses dois campos
   têm nomes diferentes nos dois schemas oficiais da ANS, e o validador já trata
   essa diferença automaticamente, junto com um fallback extra de robustez.
2. **Valida a estrutura** do XML contra o XSD oficial correspondente da ANS,
   já embutido no pacote.
3. **Aplica regras de negócio complementares** que o XSD por si só não cobre:
   - Dígito verificador de CNPJ e CPF
   - Coerência de datas (sem datas de atendimento no futuro)
   - Soma dos valores dos procedimentos vs. valor total da guia
4. Gera um relatório claro (texto ou JSON) com erros e alertas, indicando
   código, severidade, mensagem e, quando possível, a linha/caminho no XML.

## Sobre os XSDs oficiais incluídos

Os arquivos em `validador_tiss/schemas/` vêm do pacote oficial "Componente de
Comunicação" da ANS (Padrão TISS). Foi necessário corrigir uma inconsistência
do próprio pacote oficial: o arquivo `tissComplexTypesMonitoramentoV1_06_00.xsd`
referenciava (via `<include>`) um arquivo chamado
`tissSimpleTypesMonitoramentoV1_05_01.xsd`, que não existe no ZIP distribuído
(o ZIP só contém a versão `V1_06_00` desse arquivo). Isso foi corrigido apontando
o `include` para o arquivo correto já presente — sem alterar nenhuma regra de
validação, apenas a referência de nome de arquivo.

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uso como CLI

```bash
# Validar um arquivo
python -m validador_tiss.cli caminho/lote_guias.xml

# Validar vários de uma vez (glob)
python -m validador_tiss.cli "lotes/*.xml"

# Saída em JSON (útil para integrar com outros scripts)
python -m validador_tiss.cli --json arquivo.xml > resultado.json

# Retornar código de saída != 0 se algum arquivo for inválido (útil em pipelines CI)
python -m validador_tiss.cli --apenas-erros "lotes/*.xml"
```

## Uso como biblioteca Python (dentro do seu sistema)

```python
from validador_tiss.validador import validar_arquivo, validar_lote

resultado = validar_arquivo("lote_guias_prestador_123.xml")
print(resultado.resumo())

if not resultado.valido:
    for erro in resultado.erros:
        print(erro.codigo, erro.mensagem)

# Vários prestadores, vários arquivos, sem limite nenhum:
resultados = validar_lote([
    "prestador_A/lote1.xml",
    "prestador_B/lote1.xml",
    "prestador_C/lote7.xml",
])
```

## Uso como API REST

```bash
uvicorn validador_tiss.api:app --reload --port 8000
```

Endpoints:
- `GET /saude` — healthcheck
- `POST /validar` — multipart/form-data, campo `arquivo`, valida um único XML
- `POST /validar-lote` — multipart/form-data, campo `arquivos` (múltiplos),
  valida quantos arquivos forem enviados de uma vez

Exemplo com curl:
```bash
curl -X POST http://localhost:8000/validar \
  -F "arquivo=@lote_guias.xml"
```

Documentação interativa automática (Swagger) disponível em
`http://localhost:8000/docs` quando o servidor estiver rodando.

## Rodando os testes

```bash
pytest tests/ -v
```

## Estendendo as regras de negócio

Para adicionar uma nova regra, crie uma função em
`validador_tiss/regras/negocio.py` que receba uma `etree._ElementTree` e
retorne uma lista de `ErroValidacao`, depois registre-a na lista
`REGRAS_ATIVAS` no final do arquivo. Exemplos já implementados: `regra_cnpj_prestador`,
`regra_datas_coerentes`, `regra_valor_total_guia`.

## Estrutura do projeto

```
validador-tiss/
├── dist/
│   └── validador-tiss          # executável standalone compilado (Linux)
├── validador_tiss_app.py        # ponto de entrada da interface gráfica
├── validador_tiss_cli.py        # ponto de entrada da linha de comando
├── validador_tiss/
│   ├── core.py              # detecção de versão, validação XSD, utilidades
│   ├── validador.py         # orquestração de alto nível (validar_arquivo)
│   ├── cli.py                # interface de linha de comando
│   ├── api.py                 # API REST (FastAPI)
│   ├── gui.py                 # interface gráfica desktop
│   ├── tuss.py                # importação e validação do catálogo TUSS
│   ├── regras/
│   │   └── negocio.py        # regras de negócio complementares ao XSD
│   └── schemas/               # XSDs oficiais da ANS, já incluídos
│       ├── 4.03.00/
│       └── 1.06.00/
├── tests/
│   └── test_validador.py
├── exemplos/
│   ├── lote_valido.xml
│   └── monitoramento_valido.xml
└── requirements.txt
```

## Licença e responsabilidade

Este é um projeto próprio construído a partir do padrão TISS público da ANS,
sem qualquer relação com softwares comerciais de terceiros e sem nenhuma
trava de uso por CNPJ, prestador ou volume — use livremente no seu sistema.
Como qualquer ferramenta de validação, ela é um auxílio: para envio oficial
de faturamento, sempre confirme a conformidade com as regras vigentes
publicadas pela ANS e, se aplicável, pela operadora destinatária.
