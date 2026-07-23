"""Interface desktop do Validador TISS, construída apenas com Tk/ttk."""
from __future__ import annotations

import csv
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from PIL     import Image, ImageTk

from .tuss import CATALOGO_PADRAO, CatalogoTUSS
from .validador import validar_arquivo


CORES = {
    "fundo": "#F3F6FA", "painel": "#FFFFFF", "primaria": "#1261A0",
    "primaria_escura": "#0B416D", "texto": "#172B3A", "muted": "#607585",
    "borda": "#D9E2EA", "sucesso": "#16835B", "erro": "#C33B45", "alerta": "#C67A10",
}

def caminho_recurso(caminho_relativo: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent.parent

    return base / caminho_relativo

class ValidadorTISSApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        
        caminho_icone = caminho_recurso("assets/validador-tiss.ico")
        
        try:
            self.iconbitmap(default=str(caminho_icone))
        except (tk.TclError, OSError) as erro:
            print(f"Não foi possível carregar o ícone: {erro}")
            
        self.title("Validador TISS")
        self.geometry("1180x760")
        self.minsize(940, 620)
        self.configure(bg=CORES["fundo"])
        self.arquivos: list[Path] = []
        self.resultados = []
        try:
            self.catalogo = CatalogoTUSS.carregar()
        except Exception:
            self.catalogo = CatalogoTUSS()
        self._configurar_estilo()
        self._montar_interface()
        self._atualizar_tuss()

    def _configurar_estilo(self) -> None:
        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        estilo.configure(".", font=("Segoe UI", 10), background=CORES["fundo"], foreground=CORES["texto"])
        estilo.configure("Primary.TButton", padding=(18, 11), background=CORES["primaria"], foreground="white", borderwidth=0)
        estilo.map("Primary.TButton", background=[("active", CORES["primaria_escura"]), ("disabled", "#A9BBC9")])
        estilo.configure("Secondary.TButton", padding=(14, 9), background="#E9F1F7", foreground=CORES["primaria"], borderwidth=0)
        estilo.map("Secondary.TButton", background=[("active", "#D9E8F2")])
        estilo.configure("Treeview", rowheight=36, background="white", fieldbackground="white", bordercolor=CORES["borda"], borderwidth=1)
        estilo.configure("Treeview.Heading", font=("Segoe UI Semibold", 10), background="#EAF0F5", foreground=CORES["texto"], relief="flat")
        estilo.map("Treeview", background=[("selected", "#D9ECFA")], foreground=[("selected", CORES["texto"])])

    def _montar_interface(self) -> None:
        topo = tk.Frame(self, bg=CORES["primaria_escura"], height=100)
        topo.pack(fill="x")
        topo.pack_propagate(False)
        
        # Logo do Hospital da Providência no canto superior direito
        try:
            caminho_logo = caminho_recurso("assets/logo_hospital.png")

            imagem_logo = Image.open(caminho_logo)
            imagem_logo.thumbnail((155, 64), Image.Resampling.LANCZOS)

            self.logo_hospital = ImageTk.PhotoImage(imagem_logo)

            quadro_logo = tk.Frame(topo, bg=CORES["primaria_escura"], padx=8, pady=4)
            quadro_logo.pack(side="right", padx=(10, 22), pady=7)

            label_logo = tk.Label(quadro_logo, image=self.logo_hospital, bg=CORES["primaria_escura"], borderwidth=0)
            label_logo.pack()

        except (OSError, tk.TclError) as erro:
            print(f"Não foi possível carregar a logo do hospital: {erro}")
        
        tk.Label(topo, text="✓", font=("Segoe UI", 26, "bold"), bg=CORES["primaria_escura"], fg="#75D6B1").pack(side="left", padx=(26, 12))
        titulos = tk.Frame(topo, bg=CORES["primaria_escura"])
        titulos.pack(side="left", pady=15)
        tk.Label(titulos, text="Validador TISS", font=("Segoe UI Semibold", 20), bg=CORES["primaria_escura"], fg="white").pack(anchor="w")
        tk.Label(titulos, text="Validador TISS do Hospital da Providência e Materno Infantil", font=("Segoe UI", 9), bg=CORES["primaria_escura"], fg="#C8DCEB").pack(anchor="w")

        corpo = tk.Frame(self, bg=CORES["fundo"])
        corpo.pack(fill="both", expand=True, padx=22, pady=20)

        acoes = tk.Frame(corpo, bg=CORES["fundo"])
        acoes.pack(fill="x", pady=(0, 14))
        ttk.Button(acoes, text="＋ Selecionar XML", style="Primary.TButton", command=self._selecionar_arquivos).pack(side="left")
        ttk.Button(acoes, text="Selecionar pasta", style="Secondary.TButton", command=self._selecionar_pasta).pack(side="left", padx=8)
        ttk.Button(acoes, text="Limpar", style="Secondary.TButton", command=self._limpar).pack(side="left")
        ttk.Button(acoes, text="Importar tabela TUSS", style="Secondary.TButton", command=self._importar_tuss).pack(side="right")

        cards = tk.Frame(corpo, bg=CORES["fundo"])
        cards.pack(fill="x", pady=(0, 14))
        self.card_arquivos = self._card(cards, "ARQUIVOS", "0", CORES["primaria"])
        self.card_validos = self._card(cards, "VÁLIDOS", "0", CORES["sucesso"])
        self.card_invalidos = self._card(cards, "INVÁLIDOS", "0", CORES["erro"])
        self.card_tuss = self._card(cards, "TABELA TUSS", "Não carregada", CORES["alerta"], largo=True)

        painel = tk.Frame(corpo, bg=CORES["painel"], highlightbackground=CORES["borda"], highlightthickness=1)
        painel.pack(fill="both", expand=True)
        colunas = ("arquivo", "status", "versao", "tipo", "guias", "erros", "alertas")
        self.tabela = ttk.Treeview(painel, columns=colunas, show="headings", selectmode="browse")
        larguras = {"arquivo": 270, "status": 90, "versao": 95, "tipo": 165, "guias": 70, "erros": 65, "alertas": 70}
        nomes = {"arquivo": "Arquivo", "status": "Status", "versao": "Versão", "tipo": "Mensagem", "guias": "Guias", "erros": "Erros", "alertas": "Alertas"}
        for coluna in colunas:
            self.tabela.heading(coluna, text=nomes[coluna])
            self.tabela.column(coluna, width=larguras[coluna], anchor="w" if coluna in {"arquivo", "tipo"} else "center")
        self.tabela.tag_configure("valido", foreground=CORES["sucesso"])
        self.tabela.tag_configure("invalido", foreground=CORES["erro"])
        self.tabela.bind("<<TreeviewSelect>>", self._mostrar_detalhes)
        barra = ttk.Scrollbar(painel, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=barra.set)
        self.tabela.pack(side="left", fill="both", expand=True, padx=(1, 0), pady=1)
        barra.pack(side="right", fill="y", pady=1)

        rodape = tk.Frame(corpo, bg=CORES["fundo"])
        rodape.pack(fill="x", pady=(14, 0))
        self.status = tk.Label(rodape, text="Selecione arquivos XML para começar.", bg=CORES["fundo"], fg=CORES["muted"], anchor="w")
        self.status.pack(side="left", fill="x", expand=True)
        self.btn_exportar = ttk.Button(rodape, text="Exportar relatório", style="Secondary.TButton", command=self._exportar, state="disabled")
        self.btn_exportar.pack(side="right", padx=(8, 0))
        self.btn_validar = ttk.Button(rodape, text="Validar arquivos", style="Primary.TButton", command=self._iniciar_validacao, state="disabled")
        self.btn_validar.pack(side="right")

    def _card(self, pai, titulo: str, valor: str, cor: str, largo: bool = False):
        frame = tk.Frame(pai, bg="white", highlightbackground=CORES["borda"], highlightthickness=1)
        frame.pack(side="left", fill="x", expand=largo, padx=(0, 10 if not largo else 0))
        tk.Frame(frame, bg=cor, width=5).pack(side="left", fill="y")
        miolo = tk.Frame(frame, bg="white")
        miolo.pack(fill="both", padx=14, pady=10)
        tk.Label(miolo, text=titulo, font=("Segoe UI Semibold", 8), bg="white", fg=CORES["muted"]).pack(anchor="w")
        label = tk.Label(miolo, text=valor, font=("Segoe UI Semibold", 16), bg="white", fg=cor)
        label.pack(anchor="w")
        return label

    def _selecionar_arquivos(self) -> None:
        caminhos = filedialog.askopenfilenames(title="Selecione os arquivos TISS", filetypes=[("Arquivos XML", "*.xml")])
        self._adicionar([Path(c) for c in caminhos])

    def _selecionar_pasta(self) -> None:
        pasta = filedialog.askdirectory(title="Selecione a pasta com XMLs")
        if pasta:
            self._adicionar(sorted(Path(pasta).glob("*.xml")))

    def _adicionar(self, caminhos: list[Path]) -> None:
        existentes = {p.resolve() for p in self.arquivos}
        self.arquivos.extend(p for p in caminhos if p.resolve() not in existentes)
        self.resultados = []
        self._preencher_pendentes()

    def _preencher_pendentes(self) -> None:
        self.tabela.delete(*self.tabela.get_children())
        for i, caminho in enumerate(self.arquivos):
            self.tabela.insert("", "end", iid=str(i), values=(caminho.name, "Pendente", "—", "—", "—", "—", "—"))
        self.card_arquivos.config(text=str(len(self.arquivos)))
        self.card_validos.config(text="0")
        self.card_invalidos.config(text="0")
        self.btn_validar.config(state="normal" if self.arquivos else "disabled")
        self.btn_exportar.config(state="disabled")
        self.status.config(text=f"{len(self.arquivos)} arquivo(s) pronto(s) para validação.")

    def _limpar(self) -> None:
        self.arquivos.clear()
        self.resultados.clear()
        self._preencher_pendentes()

    def _importar_tuss(self) -> None:
        caminho = filedialog.askopenfilename(title="Importar tabela oficial TUSS", filetypes=[("Tabelas", "*.xlsx *.xlsm *.csv"), ("Excel", "*.xlsx *.xlsm"), ("CSV", "*.csv")])
        if not caminho:
            return
        try:
            catalogo = CatalogoTUSS.importar(caminho)
            catalogo.salvar(CATALOGO_PADRAO)
            self.catalogo = catalogo
            self._atualizar_tuss()
            messagebox.showinfo("Tabela TUSS importada", f"{len(catalogo):,} códigos foram carregados com sucesso.".replace(",", "."))
        except Exception as exc:
            messagebox.showerror("Não foi possível importar", str(exc))

    def _atualizar_tuss(self) -> None:
        if len(self.catalogo):
            self.card_tuss.config(text=f"{len(self.catalogo):,} códigos".replace(",", "."), fg=CORES["sucesso"])
        else:
            self.card_tuss.config(text="Não carregada", fg=CORES["alerta"])

    def _iniciar_validacao(self) -> None:
        self.btn_validar.config(state="disabled")
        self.status.config(text="Validando arquivos…")
        threading.Thread(target=self._validar, daemon=True).start()

    def _validar(self) -> None:
        catalogo = self.catalogo if len(self.catalogo) else None
        resultados = [validar_arquivo(c, catalogo_tuss=catalogo) for c in self.arquivos]
        self.after(0, lambda: self._concluir(resultados))

    def _concluir(self, resultados) -> None:
        self.resultados = resultados
        self.tabela.delete(*self.tabela.get_children())
        for i, r in enumerate(resultados):
            self.tabela.insert("", "end", iid=str(i), tags=("valido" if r.valido else "invalido",), values=(
                r.arquivo, "Válido" if r.valido else "Inválido", r.versao_tiss or "—", r.tipo_mensagem or "—",
                r.total_guias, len(r.erros), len(r.alertas)))
        validos = sum(r.valido for r in resultados)
        self.card_validos.config(text=str(validos))
        self.card_invalidos.config(text=str(len(resultados) - validos))
        complemento = "" if len(self.catalogo) else " Tabela TUSS não carregada; essa etapa foi ignorada."
        self.status.config(text=f"Validação concluída: {validos} válido(s), {len(resultados)-validos} inválido(s).{complemento}")
        self.btn_validar.config(state="normal")
        self.btn_exportar.config(state="normal")

    def _mostrar_detalhes(self, _evento=None) -> None:
        selecao = self.tabela.selection()
        if not selecao or not self.resultados:
            return
        resultado = self.resultados[int(selecao[0])]
        janela = tk.Toplevel(self)
        janela.title(f"Detalhes — {resultado.arquivo}")
        janela.geometry("820x520")
        janela.configure(bg=CORES["fundo"])
        texto = tk.Text(janela, wrap="word", font=("Consolas", 10), bg="white", fg=CORES["texto"], relief="flat", padx=18, pady=18)
        texto.insert("1.0", resultado.resumo())
        texto.config(state="disabled")
        texto.pack(fill="both", expand=True, padx=16, pady=16)

    def _exportar(self) -> None:
        caminho = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="relatorio-validacao-tiss.csv")
        if not caminho:
            return
        with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:
            escritor = csv.writer(arquivo, delimiter=";")
            escritor.writerow(["arquivo", "status", "versao", "tipo_mensagem", "guias", "codigo", "severidade", "mensagem", "linha", "caminho_xml"])
            for r in self.resultados:
                itens = r.erros + r.alertas
                if not itens:
                    escritor.writerow([r.arquivo, "VALIDO", r.versao_tiss, r.tipo_mensagem, r.total_guias, "", "", "", "", ""])
                for item in itens:
                    escritor.writerow([r.arquivo, "VALIDO" if r.valido else "INVALIDO", r.versao_tiss, r.tipo_mensagem, r.total_guias, item.codigo, item.severidade, item.mensagem, item.linha or "", item.caminho_xml or ""])
        messagebox.showinfo("Relatório exportado", f"Relatório salvo em:\n{caminho}")


def main() -> int:
    app = ValidadorTISSApp()
    app.mainloop()
    return 0
