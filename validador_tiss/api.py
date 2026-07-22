"""
API REST do Validador TISS.

Permite validar arquivos TISS via upload HTTP, sem nenhuma limitação
de CNPJ, prestador ou volume de requisições embutida no código.

Rodar localmente:
    uvicorn validador_tiss.api:app --reload --port 8000

Endpoints:
    POST /validar           - valida um único arquivo XML (multipart/form-data, campo "arquivo")
    POST /validar-lote      - valida múltiplos arquivos XML de uma vez
    GET  /saude             - healthcheck simples
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .validador import validar_arquivo

app = FastAPI(
    title="Validador TISS",
    description="Validação de arquivos XML no padrão TISS/ANS, sem limite de prestador/CNPJ.",
    version="1.2.0",
)

# CORS liberado para uso a partir de qualquer frontend do seu próprio sistema
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/saude")
def saude() -> dict:
    return {"status": "ok"}


@app.post("/validar")
async def validar(arquivo: UploadFile = File(...)) -> dict:
    conteudo = await arquivo.read()
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        tmp.write(conteudo)
        caminho_tmp = Path(tmp.name)

    try:
        resultado = validar_arquivo(caminho_tmp)
        resultado.arquivo = arquivo.filename or resultado.arquivo
        return resultado.to_dict()
    finally:
        caminho_tmp.unlink(missing_ok=True)


@app.post("/validar-lote")
async def validar_lote_endpoint(arquivos: list[UploadFile] = File(...)) -> list[dict]:
    """Valida quantos arquivos forem enviados, sem limite de quantidade ou de CNPJ."""
    resultados = []
    for arquivo in arquivos:
        conteudo = await arquivo.read()
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
            tmp.write(conteudo)
            caminho_tmp = Path(tmp.name)
        try:
            resultado = validar_arquivo(caminho_tmp)
            resultado.arquivo = arquivo.filename or resultado.arquivo
            resultados.append(resultado.to_dict())
        finally:
            caminho_tmp.unlink(missing_ok=True)
    return resultados
