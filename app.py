"""
CMAIU - Comissão Municipal de Avaliação de Impacto Urbano
Prefeitura Municipal de Palhoça - SC
Formulário Padrão de Avaliação de Impacto Urbano, Social e Viário
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import os
import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banco_cmaiu.xlsx")

COR_AZUL_ESCURO  = "#1a3a5c"
COR_AZUL_MEDIO   = "#2060a0"
COR_AZUL_CLARO   = "#d0e4f7"
COR_BRANCO       = "#ffffff"
COR_CINZA_CLARO  = "#f5f5f5"
COR_AMARELO      = "#f0c040"
COR_VERDE        = "#2e7d32"
COR_VERMELHO     = "#c62828"
COR_TEXTO        = "#1a1a1a"

TIPOS_EMPREENDIMENTO = [
    "Residencial Multifamiliar",
    "Comercial",
    "Industrial",
    "Misto",
    "Logístico / Centro de Distribuição",
    "Institucional (ensino/saúde)",
    "Outros",
]

MEDIDAS_COMPENSACAO = [
    "Implantação ou melhoria de calçadas acessíveis",
    "Alargamento ou pavimentação de via pública",
    "Doação de área para equipamentos públicos ou espaço comunitário",
    "Obras de drenagem urbana ou controle de águas pluviais",
    "Sistemas de transporte alternativo (bicicletas, pedestres)",
    "Planejamento de estacionamento ou acessos",
    "Outras",
]

EQUIPAMENTOS_DEMANDA = [
    "Escola / Creche",
    "Unidade de saúde",
    "Transporte coletivo",
    "Equipamento de lazer ou cultura",
    "Outros",
]

ESTADO_CALCADAS = [
    "Conformes à norma",
    "Existente, mas irregular",
    "Inexistente",
]

PROXIMIDADE_INTERSEC = [
    "Até 100m",
    "100m – 300m",
    "Mais de 300m",
]


def init_db():
    """Cria o banco de dados Excel se não existir."""
    if os.path.exists(DB_FILE):
        return
    wb = openpyxl.Workbook()
    _create_sheet_registros(wb)
    _create_sheet_cub(wb)
    wb.remove(wb["Sheet"])
    wb.save(DB_FILE)


def _header_style(cell, text, bg=COR_AZUL_ESCURO, fg=COR_BRANCO, bold=True, size=11):
    cell.value = text
    cell.font = Font(name="Calibri", bold=bold, color=fg.replace("#", ""), size=size)
    cell.fill = PatternFill("solid", fgColor=bg.replace("#", ""))
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _create_sheet_registros(wb):
    ws = wb.create_sheet("Registros")
    ws.freeze_panes = "A2"
    cols = [
        "ID", "Data Registro",
        # Seção 1
        "1.1 Nome do Empreendimento", "1.2 Endereço", "1.3 Matrícula(s)",
        "1.4 Proprietário/Resp. Legal", "1.5 End. Proprietário",
        "1.6 Bairro", "1.7 Responsável Técnico",
        "1.8 Tipo de Empreendimento", "1.8 Outros (tipo)",
        "1.9 Área Terreno (m²)", "1.10 Área Construída (m²)",
        "1.11 Nº Pavimentos", "1.12 Nº Blocos",
        "1.13 Total Unidades", "1.14 População Estimada",
        # Seção 2
        "2.1 Zona Adensamento", "2.2 Zoneamento",
        "2.3 Dem. Equipamentos Públicos",
        "2.4 Uso Misto/Ativ. Não Res.",
        "2.5 Impacto Topografia/Patrimônio", "2.5 Descrição",
        "2.6 Via Grande Circulação",
        # Seção 3
        "3.1 Tráfego Adicional (veíc/dia)",
        "3.2 Vagas Estacionamento",
        "3.3 Estudo Tráfego Anexo",
        "3.4 Acesso Compatível",
        "3.5 Estado Calçadas", "3.5 Descrição Calçadas",
        "3.6 Prox. Interseções",
        "3.7 Uso Transp. Público/Bicicletas", "3.7 Descrição",
        # Seção 4
        "4.1 Adensamento Populacional", "4.1 Qtd. Moradores",
        "4.2 Demandas Serviços Públicos",
        "4.3 Área Vulnerabilidade",
        "4.4 Espaços Públicos", "4.4 Descrição",
        "4.5 Consulta Pública", "4.5 Data Consulta", "4.5 Nº Participantes",
        # Seção 5
        "5.1 Equipamentos Entorno",
        "5.2 Transporte Coletivo Disponível",
        "5.3 Saneamento Compatível", "5.3 Detalhamento",
        "5.4 Áreas Verdes", "5.4 Área Estimada (m²)",
        "5.5 Sistema Resíduos", "5.5 Descrição",
        # Seção 6
        "6.1 Medidas de Compensação", "6.1 Outras (descrição)",
        # Cálculo
        "CUB Referência (R$/m²)", "Valor Estimado Compensação (R$)",
        "Observações Gerais",
    ]
    for c, col in enumerate(cols, 1):
        cell = ws.cell(row=1, column=c, value=col)
        cell.font = Font(name="Calibri", bold=True, color="FFFFFF", size=9)
        cell.fill = PatternFill("solid", fgColor=COR_AZUL_ESCURO.replace("#", ""))
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(c)].width = max(15, len(col) * 0.9)
    ws.row_dimensions[1].height = 45
    return ws


def _create_sheet_cub(wb):
    ws = wb.create_sheet("CUB")
    ws.freeze_panes = "A2"
    headers = ["Mês/Ano", "Categoria", "CUB (R$/m²)", "Fonte", "Observações"]
    widths  = [14, 30, 15, 25, 40]
    for c, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
        cell.fill = PatternFill("solid", fgColor=COR_AZUL_MEDIO.replace("#", ""))
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(c)].width = w
    # Exemplo de dados iniciais
    exemplos = [
        ["Jun/2025", "R8-N (Residencial 8 pavimentos - Normal)", 3200.00, "SINDUSCON-SC", ""],
        ["Jun/2025", "R8-B (Residencial 8 pavimentos - Baixo padrão)", 2650.00, "SINDUSCON-SC", ""],
        ["Jun/2025", "R8-A (Residencial 8 pavimentos - Alto padrão)", 4100.00, "SINDUSCON-SC", ""],
        ["Jun/2025", "CSL-8 (Comercial salas/loja 8 pav.)", 3500.00, "SINDUSCON-SC", ""],
        ["Jun/2025", "GI (Galpão Industrial)", 1850.00, "SINDUSCON-SC", ""],
    ]
    for r, row in enumerate(exemplos, 2):
        for c, val in enumerate(row, 1):
            ws.cell(row=r, column=c, value=val)
    ws.row_dimensions[1].height = 30
    return ws


def get_cub_values():
    """Retorna lista de (mês_ano, categoria, valor) do banco."""
    if not os.path.exists(DB_FILE):
        return []
    wb = openpyxl.load_workbook(DB_FILE, read_only=True, data_only=True)
    ws = wb["CUB"]
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] and row[2]:
            rows.append((f"{row[0]} – {row[1]}", float(row[2])))
    wb.close()
    return rows


def get_next_id():
    if not os.path.exists(DB_FILE):
        return 1
    wb = openpyxl.load_workbook(DB_FILE, read_only=True, data_only=True)
    ws = wb["Registros"]
    last = 0
    for row in ws.iter_rows(min_row=2, max_col=1, values_only=True):
        if row[0] and isinstance(row[0], int):
            last = max(last, row[0])
    wb.close()
    return last + 1


def salvar_registro(dados: dict):
    wb = openpyxl.load_workbook(DB_FILE)
    ws = wb["Registros"]
    next_row = ws.max_row + 1
    registro_id = get_next_id()
    hoje = datetime.date.today().strftime("%d/%m/%Y")

    valores = [
        registro_id, hoje,
        dados.get("nome_empreendimento"),
        dados.get("endereco_empreendimento"),
        dados.get("matriculas"),
        dados.get("proprietario"),
        dados.get("endereco_proprietario"),
        dados.get("bairro"),
        dados.get("responsavel_tecnico"),
        dados.get("tipo_empreendimento"),
        dados.get("tipo_outros"),
        dados.get("area_terreno"),
        dados.get("area_construida"),
        dados.get("num_pavimentos"),
        dados.get("num_blocos"),
        dados.get("total_unidades"),
        dados.get("populacao_estimada"),
        dados.get("zona_adensamento"),
        dados.get("zoneamento"),
        dados.get("dem_equipamentos"),
        dados.get("uso_misto"),
        dados.get("impacto_topografia"),
        dados.get("desc_topografia"),
        dados.get("via_grande_circulacao"),
        dados.get("trafego_adicional"),
        dados.get("vagas_estacionamento"),
        dados.get("estudo_trafego"),
        dados.get("acesso_compativel"),
        dados.get("estado_calcadas"),
        dados.get("desc_calcadas"),
        dados.get("prox_intersecoes"),
        dados.get("uso_transp_publico"),
        dados.get("desc_transp_publico"),
        dados.get("adensamento_pop"),
        dados.get("qtd_moradores"),
        dados.get("demandas_servicos"),
        dados.get("area_vulnerabilidade"),
        dados.get("espacos_publicos"),
        dados.get("desc_espacos_publicos"),
        dados.get("consulta_publica"),
        dados.get("data_consulta"),
        dados.get("num_participantes"),
        dados.get("equipamentos_entorno"),
        dados.get("transp_coletivo_disp"),
        dados.get("saneamento_compativel"),
        dados.get("det_saneamento"),
        dados.get("areas_verdes"),
        dados.get("area_verde_m2"),
        dados.get("sistema_residuos"),
        dados.get("desc_residuos"),
        dados.get("medidas_compensacao"),
        dados.get("desc_outras_medidas"),
        dados.get("cub_referencia"),
        dados.get("valor_compensacao"),
        dados.get("observacoes"),
    ]
    for c, val in enumerate(valores, 1):
        cell = ws.cell(row=next_row, column=c, value=val)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        if next_row % 2 == 0:
            cell.fill = PatternFill("solid", fgColor="EDF4FB")
    ws.row_dimensions[next_row].height = 20
    wb.save(DB_FILE)
    return registro_id


def listar_registros():
    if not os.path.exists(DB_FILE):
        return []
    wb = openpyxl.load_workbook(DB_FILE, read_only=True, data_only=True)
    ws = wb["Registros"]
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if any(v is not None for v in row):
            rows.append(row)
    wb.close()
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# WIDGETS HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def lbl(parent, text, bold=False, size=10, fg=COR_TEXTO, pady=0):
    f = ("Calibri", size, "bold") if bold else ("Calibri", size)
    return tk.Label(parent, text=text, font=f, fg=fg, bg=COR_BRANCO, pady=pady)


def entry(parent, var, width=40, state="normal"):
    return tk.Entry(parent, textvariable=var, width=width,
                    font=("Calibri", 10), relief="solid", bd=1,
                    highlightthickness=1, highlightcolor=COR_AZUL_MEDIO,
                    state=state)


def text_widget(parent, height=3, width=60):
    t = tk.Text(parent, height=height, width=width,
                font=("Calibri", 10), relief="solid", bd=1,
                wrap="word")
    return t


def sim_nao(parent, var):
    f = tk.Frame(parent, bg=COR_BRANCO)
    for txt in ("Sim", "Não"):
        tk.Radiobutton(f, text=txt, variable=var, value=txt,
                       font=("Calibri", 10), bg=COR_BRANCO,
                       activebackground=COR_BRANCO).pack(side="left", padx=6)
    return f


def section_title(parent, text):
    f = tk.Frame(parent, bg=COR_AZUL_MEDIO, pady=4)
    tk.Label(f, text=text, font=("Calibri", 11, "bold"),
             fg=COR_BRANCO, bg=COR_AZUL_MEDIO).pack(side="left", padx=10)
    return f


def field_row(parent, label_text, widget_builder, row, column=0, pady=3):
    lbl(parent, label_text, bold=False, size=10).grid(
        row=row, column=column, sticky="w", padx=(10, 4), pady=pady)
    w = widget_builder()
    w.grid(row=row, column=column + 1, sticky="ew", padx=(0, 10), pady=pady)
    return w


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────

class CMAIUApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CMAIU – Avaliação de Impacto Urbano | Prefeitura de Palhoça – SC")
        self.state("zoomed")
        self.configure(bg=COR_AZUL_ESCURO)
        self.minsize(1000, 700)
        init_db()
        self._build_header()
        self._build_notebook()
        self._build_footer()

    # ── Header ──────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=COR_AZUL_ESCURO, pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="ESTADO DE SANTA CATARINA  •  PREFEITURA MUNICIPAL DE PALHOÇA",
                 font=("Calibri", 10), fg=COR_AMARELO,
                 bg=COR_AZUL_ESCURO).pack()
        tk.Label(hdr, text="CMAIU – Comissão Municipal de Avaliação de Impacto Urbano",
                 font=("Calibri", 16, "bold"), fg=COR_BRANCO,
                 bg=COR_AZUL_ESCURO).pack()
        tk.Label(hdr, text="Formulário Padrão de Avaliação de Impacto Urbano, Social e Viário",
                 font=("Calibri", 11), fg=COR_AZUL_CLARO,
                 bg=COR_AZUL_ESCURO).pack()

    # ── Notebook ─────────────────────────────────────────────────────────────
    def _build_notebook(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=COR_AZUL_ESCURO, borderwidth=0)
        style.configure("TNotebook.Tab",
                        font=("Calibri", 10, "bold"),
                        padding=[14, 6],
                        background=COR_AZUL_MEDIO,
                        foreground=COR_BRANCO)
        style.map("TNotebook.Tab",
                  background=[("selected", COR_AZUL_CLARO)],
                  foreground=[("selected", COR_AZUL_ESCURO)])

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self._build_tab1()
        self._build_tab2()
        self._build_tab3()
        self._build_tab4()
        self._build_tab_consulta()
        self._build_tab_cub()

    # ── Footer ───────────────────────────────────────────────────────────────
    def _build_footer(self):
        ft = tk.Frame(self, bg=COR_AZUL_ESCURO, pady=4)
        ft.pack(fill="x", side="bottom")
        tk.Label(ft,
                 text=f"Banco de dados: {DB_FILE}",
                 font=("Calibri", 8), fg=COR_AZUL_CLARO,
                 bg=COR_AZUL_ESCURO).pack(side="left", padx=10)
        tk.Button(ft, text="Abrir Banco de Dados (Excel)",
                  font=("Calibri", 9, "bold"),
                  bg=COR_AMARELO, fg=COR_AZUL_ESCURO,
                  relief="flat", padx=8,
                  command=self._open_db).pack(side="right", padx=10)

    def _open_db(self):
        import subprocess, sys
        if sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", DB_FILE])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", DB_FILE])
        else:
            os.startfile(DB_FILE)

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 1 – Dados do Empreendimento
    # ─────────────────────────────────────────────────────────────────────────
    def _build_tab1(self):
        frame = self._scrollable_frame("1. Dados do Empreendimento")

        # Variáveis
        self.v_nome        = tk.StringVar()
        self.v_endereco    = tk.StringVar()
        self.v_matriculas  = tk.StringVar()
        self.v_proprietario = tk.StringVar()
        self.v_end_prop    = tk.StringVar()
        self.v_bairro      = tk.StringVar()
        self.v_resp_tec    = tk.StringVar()
        self.v_tipo        = tk.StringVar()
        self.v_tipo_outros = tk.StringVar()
        self.v_area_terreno    = tk.StringVar()
        self.v_area_construida = tk.StringVar()
        self.v_pavimentos  = tk.StringVar()
        self.v_blocos      = tk.StringVar()
        self.v_unidades    = tk.StringVar()
        self.v_populacao   = tk.StringVar()

        inner = frame
        inner.columnconfigure(1, weight=1)

        section_title(inner, "1. Dados do Empreendimento").grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        fields1 = [
            ("1.1  Nome do empreendimento:", self.v_nome),
            ("1.2  Endereço do empreendimento:", self.v_endereco),
            ("1.3  Matrícula(s) imobiliária(s):", self.v_matriculas),
            ("1.4  Proprietário / Responsável Legal:", self.v_proprietario),
            ("1.5  Endereço (logradouro, lote, quadra):", self.v_end_prop),
            ("1.6  Bairro:", self.v_bairro),
            ("1.7  Responsável Técnico (nome e CREA/CAU):", self.v_resp_tec),
        ]
        for i, (label, var) in enumerate(fields1, 1):
            lbl(inner, label).grid(row=i, column=0, sticky="w", padx=(10,4), pady=3)
            entry(inner, var).grid(row=i, column=1, sticky="ew", padx=(0,10), pady=3)

        # Tipo de empreendimento
        r = len(fields1) + 1
        lbl(inner, "1.8  Tipo de empreendimento:", bold=True).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 2))
        r += 1
        frm_tipo = tk.Frame(inner, bg=COR_BRANCO)
        frm_tipo.grid(row=r, column=0, columnspan=2, sticky="w", padx=20)
        for t in TIPOS_EMPREENDIMENTO:
            tk.Radiobutton(frm_tipo, text=t, variable=self.v_tipo, value=t,
                           font=("Calibri", 10), bg=COR_BRANCO,
                           activebackground=COR_BRANCO).pack(anchor="w")
        r += 1
        lbl(inner, "  Se 'Outros', especificar:").grid(row=r, column=0, sticky="w", padx=10, pady=2)
        entry(inner, self.v_tipo_outros, width=50).grid(row=r, column=1, sticky="ew", padx=(0,10))

        # Campos numéricos
        r += 1
        num_fields = [
            ("1.9   Área total do terreno (m²):", self.v_area_terreno),
            ("1.10  Área total construída (m²):", self.v_area_construida),
            ("1.11  Número de pavimentos:", self.v_pavimentos),
            ("1.12  Número de blocos:", self.v_blocos),
            ("1.13  Número total de unidades:", self.v_unidades),
            ("1.14  População estimada:", self.v_populacao),
        ]
        for label, var in num_fields:
            lbl(inner, label).grid(row=r, column=0, sticky="w", padx=(10,4), pady=3)
            entry(inner, var, width=20).grid(row=r, column=1, sticky="w", padx=(0,10), pady=3)
            r += 1

        # Botão avançar
        tk.Button(inner, text="Avançar →  Impactos Urbanísticos",
                  font=("Calibri", 11, "bold"), bg=COR_AZUL_MEDIO, fg=COR_BRANCO,
                  relief="flat", padx=16, pady=8,
                  command=lambda: self.nb.select(1)).grid(
            row=r, column=0, columnspan=2, pady=16)

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 2 – Impactos Urbanísticos e Viários (seções 2 e 3)
    # ─────────────────────────────────────────────────────────────────────────
    def _build_tab2(self):
        frame = self._scrollable_frame("2–3. Impactos Urbanísticos e Viários")
        inner = frame
        inner.columnconfigure(1, weight=1)

        self.v_zona_adensamento   = tk.StringVar()
        self.v_zoneamento         = tk.StringVar()
        self.v_dem_equipamentos   = []  # checkboxes
        self.v_dem_equipamentos_vars = {e: tk.BooleanVar() for e in EQUIPAMENTOS_DEMANDA}
        self.v_dem_outros_txt     = tk.StringVar()
        self.v_uso_misto          = tk.StringVar()
        self.v_impacto_topo       = tk.StringVar()
        self.v_desc_topo          = tk.StringVar()
        self.v_via_circ           = tk.StringVar()
        self.v_trafego_adic       = tk.StringVar()
        self.v_vagas              = tk.StringVar()
        self.v_estudo_trafego     = tk.StringVar()
        self.v_acesso_compat      = tk.StringVar()
        self.v_calcadas           = tk.StringVar()
        self.v_desc_calcadas      = tk.StringVar()
        self.v_prox_intersec      = tk.StringVar()

        r = 0
        section_title(inner, "2. Impactos Urbanísticos Previstos").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=(0, 6)); r += 1

        lbl(inner, "2.1  Está inserido em zona de adensamento ou expansão urbana?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_zona_adensamento).grid(row=r, column=1, sticky="w"); r += 1

        lbl(inner, "2.2  Zoneamento do empreendimento:").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        entry(inner, self.v_zoneamento, width=30).grid(row=r, column=1, sticky="w", padx=(0,10)); r += 1

        lbl(inner, "2.3  Geração de demanda por equipamentos públicos:", bold=True).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=10, pady=(8,2)); r += 1
        frm_eq = tk.Frame(inner, bg=COR_BRANCO)
        frm_eq.grid(row=r, column=0, columnspan=2, sticky="w", padx=20)
        for eq, var in self.v_dem_equipamentos_vars.items():
            tk.Checkbutton(frm_eq, text=eq, variable=var,
                           font=("Calibri", 10), bg=COR_BRANCO,
                           activebackground=COR_BRANCO).pack(anchor="w")
        r += 1
        lbl(inner, "  Outros (detalhar):").grid(row=r, column=0, sticky="w", padx=10)
        entry(inner, self.v_dem_outros_txt, width=50).grid(row=r, column=1, sticky="ew", padx=(0,10)); r += 1

        lbl(inner, "2.4  Uso misto ou atividades não residenciais previstas?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_uso_misto).grid(row=r, column=1, sticky="w"); r += 1

        lbl(inner, "2.5  Topografia, paisagem ou patrimônio cultural impactados?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_impacto_topo).grid(row=r, column=1, sticky="w"); r += 1
        lbl(inner, "  Se sim, descrever:").grid(row=r, column=0, sticky="w", padx=10)
        entry(inner, self.v_desc_topo, width=50).grid(row=r, column=1, sticky="ew", padx=(0,10)); r += 1

        lbl(inner, "2.6  Testada/acesso voltado para via de grande circulação?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_via_circ).grid(row=r, column=1, sticky="w"); r += 1

        section_title(inner, "3. Impactos Viários e de Mobilidade").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=(12, 6)); r += 1

        num_viar = [
            ("3.1  Estimativa de tráfego adicional (veíc/dia):", self.v_trafego_adic),
            ("3.2  Número de vagas de estacionamento previstas:", self.v_vagas),
        ]
        for label, var in num_viar:
            lbl(inner, label).grid(row=r, column=0, sticky="w", padx=10, pady=3)
            entry(inner, var, width=20).grid(row=r, column=1, sticky="w"); r += 1

        lbl(inner, "3.3  Existe estudo de tráfego ou mobilidade urbana anexo?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_estudo_trafego).grid(row=r, column=1, sticky="w"); r += 1

        lbl(inner, "3.4  Acesso/saída compatíveis com o tráfego gerado?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_acesso_compat).grid(row=r, column=1, sticky="w"); r += 1

        lbl(inner, "3.5  Estado das calçadas e infraestrutura de pedestres:", bold=True).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=10, pady=(8,2)); r += 1
        frm_calc = tk.Frame(inner, bg=COR_BRANCO)
        frm_calc.grid(row=r, column=0, columnspan=2, sticky="w", padx=20)
        for op in ESTADO_CALCADAS:
            tk.Radiobutton(frm_calc, text=op, variable=self.v_calcadas, value=op,
                           font=("Calibri", 10), bg=COR_BRANCO,
                           activebackground=COR_BRANCO).pack(anchor="w")
        r += 1
        lbl(inner, "  Se irregular/inexistente, descrever:").grid(row=r, column=0, sticky="w", padx=10)
        entry(inner, self.v_desc_calcadas, width=50).grid(row=r, column=1, sticky="ew", padx=(0,10)); r += 1

        lbl(inner, "3.6  Proximidade de interseções ou pontos críticos:", bold=True).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=10, pady=(8,2)); r += 1
        frm_prox = tk.Frame(inner, bg=COR_BRANCO)
        frm_prox.grid(row=r, column=0, columnspan=2, sticky="w", padx=20)
        for op in PROXIMIDADE_INTERSEC:
            tk.Radiobutton(frm_prox, text=op, variable=self.v_prox_intersec, value=op,
                           font=("Calibri", 10), bg=COR_BRANCO,
                           activebackground=COR_BRANCO).pack(anchor="w")
        r += 1

        tk.Button(inner, text="Avançar →  Impactos Sociais e Infraestrutura",
                  font=("Calibri", 11, "bold"), bg=COR_AZUL_MEDIO, fg=COR_BRANCO,
                  relief="flat", padx=16, pady=8,
                  command=lambda: self.nb.select(2)).grid(
            row=r, column=0, columnspan=2, pady=16)

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 3 – Impactos Sociais e Infraestrutura (seções 3.7 – 5 e início 6)
    # ─────────────────────────────────────────────────────────────────────────
    def _build_tab3(self):
        frame = self._scrollable_frame("3.7–5. Impactos Sociais e Infraestrutura")
        inner = frame
        inner.columnconfigure(1, weight=1)

        self.v_uso_transp       = tk.StringVar()
        self.v_desc_transp      = tk.StringVar()
        self.v_adensamento_pop  = tk.StringVar()
        self.v_qtd_moradores    = tk.StringVar()
        self.v_demandas_serv    = tk.StringVar()
        self.v_area_vuln        = tk.StringVar()
        self.v_espacos_pub      = tk.StringVar()
        self.v_desc_espacos     = tk.StringVar()
        self.v_consulta_pub     = tk.StringVar()
        self.v_data_consulta    = tk.StringVar()
        self.v_num_part         = tk.StringVar()
        self.v_transp_coletivo  = tk.StringVar()
        self.v_saneamento       = tk.StringVar()
        self.v_det_saneamento   = tk.StringVar()
        self.v_areas_verdes     = tk.StringVar()
        self.v_area_verde_m2    = tk.StringVar()
        self.v_residuos         = tk.StringVar()
        self.v_desc_residuos    = tk.StringVar()

        r = 0
        section_title(inner, "3.7 – Transporte Público e Bicicletas").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=(0, 6)); r += 1
        lbl(inner, "3.7  Há previsão de uso ou impacto para transporte público ou bicicletas?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_uso_transp).grid(row=r, column=1, sticky="w"); r += 1
        lbl(inner, "  Descrever:").grid(row=r, column=0, sticky="w", padx=10)
        entry(inner, self.v_desc_transp, width=50).grid(row=r, column=1, sticky="ew", padx=(0,10)); r += 1

        section_title(inner, "4. Impactos Sociais e Demanda por Serviços").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=(12, 6)); r += 1

        lbl(inner, "4.1  O empreendimento causa adensamento populacional relevante?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_adensamento_pop).grid(row=r, column=1, sticky="w"); r += 1
        lbl(inner, "  Se sim, estimativa de moradores adicionais:").grid(
            row=r, column=0, sticky="w", padx=10)
        entry(inner, self.v_qtd_moradores, width=20).grid(row=r, column=1, sticky="w"); r += 1

        lbl(inner, "4.2  Demandas geradas para serviços públicos:").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        entry(inner, self.v_demandas_serv, width=60).grid(row=r, column=1, sticky="ew", padx=(0,10)); r += 1

        lbl(inner, "4.3  Inserido em área de vulnerabilidade ou regularização urbanística?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_area_vuln).grid(row=r, column=1, sticky="w"); r += 1

        lbl(inner, "4.4  Contempla espaços públicos de convivência/lazer?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_espacos_pub).grid(row=r, column=1, sticky="w"); r += 1
        lbl(inner, "  Se sim, descrever:").grid(row=r, column=0, sticky="w", padx=10)
        entry(inner, self.v_desc_espacos, width=50).grid(row=r, column=1, sticky="ew", padx=(0,10)); r += 1

        lbl(inner, "4.5  Foi realizada consulta ou audiência pública?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_consulta_pub).grid(row=r, column=1, sticky="w"); r += 1
        lbl(inner, "  Data da consulta (dd/mm/aaaa):").grid(row=r, column=0, sticky="w", padx=10)
        entry(inner, self.v_data_consulta, width=20).grid(row=r, column=1, sticky="w"); r += 1
        lbl(inner, "  Número de participantes:").grid(row=r, column=0, sticky="w", padx=10)
        entry(inner, self.v_num_part, width=20).grid(row=r, column=1, sticky="w"); r += 1

        section_title(inner, "5. Infraestrutura Existente e Suporte Urbano").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=(12, 6)); r += 1

        lbl(inner, "5.1  Equipamentos públicos no entorno (listar):").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        self.txt_equip_entorno = text_widget(inner, height=2, width=50)
        self.txt_equip_entorno.grid(row=r, column=1, sticky="ew", padx=(0,10)); r += 1

        lbl(inner, "5.2  Transporte coletivo disponível?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_transp_coletivo).grid(row=r, column=1, sticky="w"); r += 1

        lbl(inner, "5.3  Rede de saneamento (água, esgoto, drenagem) compatível?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_saneamento).grid(row=r, column=1, sticky="w"); r += 1
        lbl(inner, "  Se não, detalhar adequações:").grid(row=r, column=0, sticky="w", padx=10)
        entry(inner, self.v_det_saneamento, width=50).grid(row=r, column=1, sticky="ew", padx=(0,10)); r += 1

        lbl(inner, "5.4  Áreas verdes ou sistema de lazer existentes?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_areas_verdes).grid(row=r, column=1, sticky="w"); r += 1
        lbl(inner, "  Se sim, área estimada (m²):").grid(row=r, column=0, sticky="w", padx=10)
        entry(inner, self.v_area_verde_m2, width=20).grid(row=r, column=1, sticky="w"); r += 1

        lbl(inner, "5.5  Sistema de resíduos sólidos previsto/compatível?").grid(
            row=r, column=0, sticky="w", padx=10, pady=3)
        sim_nao(inner, self.v_residuos).grid(row=r, column=1, sticky="w"); r += 1
        lbl(inner, "  Se não, descrever:").grid(row=r, column=0, sticky="w", padx=10)
        entry(inner, self.v_desc_residuos, width=50).grid(row=r, column=1, sticky="ew", padx=(0,10)); r += 1

        tk.Button(inner, text="Avançar →  Medidas de Compensação",
                  font=("Calibri", 11, "bold"), bg=COR_AZUL_MEDIO, fg=COR_BRANCO,
                  relief="flat", padx=16, pady=8,
                  command=lambda: self.nb.select(3)).grid(
            row=r, column=0, columnspan=2, pady=16)

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 4 – Medidas de Compensação e Cálculo
    # ─────────────────────────────────────────────────────────────────────────
    def _build_tab4(self):
        frame = self._scrollable_frame("6. Compensação e Cálculo")
        inner = frame
        inner.columnconfigure(1, weight=1)

        self.v_medidas_vars  = {m: tk.BooleanVar() for m in MEDIDAS_COMPENSACAO}
        self.v_outras_medidas = tk.StringVar()
        self.v_obs            = tk.StringVar()
        self.v_cub_sel        = tk.StringVar()
        self.v_cub_valor      = tk.DoubleVar(value=0.0)
        self.v_perc_comp      = tk.DoubleVar(value=5.0)
        self.v_val_comp       = tk.StringVar(value="R$ 0,00")

        r = 0
        section_title(inner, "6. Medidas de Compensação, Mitigação ou Contrapartida").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=(0, 6)); r += 1

        lbl(inner, "6.1  Marque e detalhe as que se aplicam:", bold=True).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=10, pady=(4,2)); r += 1
        frm_med = tk.Frame(inner, bg=COR_BRANCO)
        frm_med.grid(row=r, column=0, columnspan=2, sticky="w", padx=20); r += 1
        for med, var in self.v_medidas_vars.items():
            tk.Checkbutton(frm_med, text=med, variable=var,
                           font=("Calibri", 10), bg=COR_BRANCO,
                           activebackground=COR_BRANCO).pack(anchor="w")
        lbl(inner, "  Outras (descrever):").grid(row=r, column=0, sticky="w", padx=10)
        entry(inner, self.v_outras_medidas, width=50).grid(row=r, column=1, sticky="ew", padx=(0,10)); r += 1

        lbl(inner, "Observações gerais:").grid(row=r, column=0, sticky="nw", padx=10, pady=4)
        self.txt_obs = text_widget(inner, height=3)
        self.txt_obs.grid(row=r, column=1, sticky="ew", padx=(0,10), pady=4); r += 1

        # Cálculo com CUB
        section_title(inner, "Cálculo do Valor de Compensação (baseado no CUB)").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=(14, 8)); r += 1

        lbl(inner, "Selecionar CUB de referência:").grid(row=r, column=0, sticky="w", padx=10, pady=4)
        self.cub_cb = ttk.Combobox(inner, textvariable=self.v_cub_sel,
                                   font=("Calibri", 10), state="readonly", width=45)
        self.cub_cb.grid(row=r, column=1, sticky="ew", padx=(0,10), pady=4)
        self.cub_cb.bind("<<ComboboxSelected>>", self._on_cub_select); r += 1
        self._refresh_cub_combo()

        lbl(inner, "CUB selecionado (R$/m²):").grid(row=r, column=0, sticky="w", padx=10)
        self.lbl_cub_valor = lbl(inner, "—", bold=True, fg=COR_AZUL_ESCURO)
        self.lbl_cub_valor.grid(row=r, column=1, sticky="w", padx=(0,10)); r += 1

        lbl(inner, "Área construída sujeita à compensação (m²):").grid(
            row=r, column=0, sticky="w", padx=10, pady=4)
        self.v_area_comp = tk.StringVar()
        entry(inner, self.v_area_comp, width=20).grid(row=r, column=1, sticky="w"); r += 1

        lbl(inner, "Percentual de compensação (%):").grid(row=r, column=0, sticky="w", padx=10)
        tk.Spinbox(inner, from_=0.5, to=100, increment=0.5,
                   textvariable=self.v_perc_comp,
                   font=("Calibri", 10), width=10,
                   command=self._calcular).grid(row=r, column=1, sticky="w"); r += 1

        tk.Button(inner, text="Calcular Valor de Compensação",
                  font=("Calibri", 10, "bold"), bg=COR_VERDE, fg=COR_BRANCO,
                  relief="flat", padx=12, pady=6,
                  command=self._calcular).grid(row=r, column=0, columnspan=2, pady=8); r += 1

        # Resultado
        frm_res = tk.Frame(inner, bg=COR_AZUL_CLARO, bd=1, relief="solid", pady=10, padx=20)
        frm_res.grid(row=r, column=0, columnspan=2, sticky="ew", padx=10, pady=6); r += 1
        lbl(frm_res, "Valor Estimado de Compensação:", bold=True, size=12, fg=COR_AZUL_ESCURO).grid(
            row=0, column=0, sticky="w")
        self.lbl_resultado = lbl(frm_res, "R$ 0,00", bold=True, size=16, fg=COR_VERDE)
        self.lbl_resultado.grid(row=0, column=1, sticky="w", padx=20)

        frm_res.columnconfigure(1, weight=1)

        # Botão salvar
        tk.Button(inner, text="💾  SALVAR REGISTRO NO BANCO DE DADOS",
                  font=("Calibri", 13, "bold"), bg=COR_AZUL_ESCURO, fg=COR_AMARELO,
                  relief="flat", padx=20, pady=12,
                  command=self._salvar).grid(
            row=r, column=0, columnspan=2, pady=20); r += 1

        tk.Button(inner, text="Limpar Formulário (novo registro)",
                  font=("Calibri", 10), bg=COR_CINZA_CLARO, fg=COR_TEXTO,
                  relief="flat", padx=12, pady=6,
                  command=self._limpar).grid(
            row=r, column=0, columnspan=2, pady=4)

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 5 – Consulta de Registros
    # ─────────────────────────────────────────────────────────────────────────
    def _build_tab_consulta(self):
        tab = tk.Frame(self.nb, bg=COR_BRANCO)
        self.nb.add(tab, text="📋  Registros")

        top = tk.Frame(tab, bg=COR_AZUL_MEDIO, pady=8)
        top.pack(fill="x")
        tk.Label(top, text="Registros Salvos no Banco de Dados",
                 font=("Calibri", 13, "bold"), fg=COR_BRANCO, bg=COR_AZUL_MEDIO).pack(side="left", padx=16)
        tk.Button(top, text="↻ Atualizar", font=("Calibri", 10, "bold"),
                  bg=COR_AMARELO, fg=COR_AZUL_ESCURO, relief="flat", padx=10,
                  command=self._load_registros).pack(side="right", padx=10)

        # Busca
        frm_busca = tk.Frame(tab, bg=COR_CINZA_CLARO, pady=6, padx=10)
        frm_busca.pack(fill="x")
        tk.Label(frm_busca, text="Buscar:", font=("Calibri", 10),
                 bg=COR_CINZA_CLARO).pack(side="left")
        self.v_busca = tk.StringVar()
        self.v_busca.trace("w", lambda *a: self._filtrar_registros())
        tk.Entry(frm_busca, textvariable=self.v_busca,
                 font=("Calibri", 10), width=40, relief="solid", bd=1).pack(
            side="left", padx=8)

        # Treeview
        cols = ("ID", "Data", "Empreendimento", "Tipo", "Área (m²)", "Compensação (R$)")
        self.tree = ttk.Treeview(tab, columns=cols, show="headings", height=20)
        widths = [50, 90, 280, 160, 100, 140]
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center" if w < 150 else "w")

        style = ttk.Style()
        style.configure("Treeview", font=("Calibri", 10), rowheight=24)
        style.configure("Treeview.Heading", font=("Calibri", 10, "bold"),
                        background=COR_AZUL_MEDIO, foreground=COR_BRANCO)
        self.tree.tag_configure("odd", background=COR_CINZA_CLARO)
        self.tree.tag_configure("even", background=COR_BRANCO)

        sb = ttk.Scrollbar(tab, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(10,0), pady=10)
        sb.pack(side="left", fill="y", pady=10)

        self._all_registros = []
        self._load_registros()

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 6 – Gerenciar CUB
    # ─────────────────────────────────────────────────────────────────────────
    def _build_tab_cub(self):
        tab = tk.Frame(self.nb, bg=COR_BRANCO)
        self.nb.add(tab, text="📊  Tabela CUB")

        top = tk.Frame(tab, bg=COR_AZUL_MEDIO, pady=8)
        top.pack(fill="x")
        tk.Label(top, text="Custo Unitário Básico (CUB) – Tabela de Referência",
                 font=("Calibri", 13, "bold"), fg=COR_BRANCO, bg=COR_AZUL_MEDIO).pack(side="left", padx=16)

        # Formulário de inclusão
        frm_add = tk.LabelFrame(tab, text="Adicionar Novo Valor CUB",
                                font=("Calibri", 10, "bold"),
                                bg=COR_BRANCO, fg=COR_AZUL_ESCURO, pady=8, padx=10)
        frm_add.pack(fill="x", padx=14, pady=10)
        frm_add.columnconfigure(1, weight=1)
        frm_add.columnconfigure(3, weight=2)

        self.v_cub_mes      = tk.StringVar()
        self.v_cub_cat      = tk.StringVar()
        self.v_cub_val_novo = tk.StringVar()
        self.v_cub_fonte    = tk.StringVar(value="SINDUSCON-SC")
        self.v_cub_obs      = tk.StringVar()

        campos_cub = [
            ("Mês/Ano (ex: Jul/2025):", self.v_cub_mes, 15),
            ("Categoria CUB:", self.v_cub_cat, 40),
        ]
        for i, (lbl_txt, var, w) in enumerate(campos_cub):
            tk.Label(frm_add, text=lbl_txt, font=("Calibri", 10), bg=COR_BRANCO).grid(
                row=0, column=i*2, sticky="w", padx=(0,4))
            tk.Entry(frm_add, textvariable=var, width=w,
                     font=("Calibri", 10), relief="solid", bd=1).grid(
                row=0, column=i*2+1, sticky="ew", padx=(0,12))

        tk.Label(frm_add, text="CUB (R$/m²):", font=("Calibri", 10), bg=COR_BRANCO).grid(
            row=1, column=0, sticky="w", pady=6)
        tk.Entry(frm_add, textvariable=self.v_cub_val_novo, width=15,
                 font=("Calibri", 10), relief="solid", bd=1).grid(
            row=1, column=1, sticky="w", padx=(0,12))
        tk.Label(frm_add, text="Fonte:", font=("Calibri", 10), bg=COR_BRANCO).grid(
            row=1, column=2, sticky="w")
        tk.Entry(frm_add, textvariable=self.v_cub_fonte, width=25,
                 font=("Calibri", 10), relief="solid", bd=1).grid(
            row=1, column=3, sticky="ew", padx=(0,12))

        tk.Label(frm_add, text="Observações:", font=("Calibri", 10), bg=COR_BRANCO).grid(
            row=2, column=0, sticky="w")
        tk.Entry(frm_add, textvariable=self.v_cub_obs, width=70,
                 font=("Calibri", 10), relief="solid", bd=1).grid(
            row=2, column=1, columnspan=3, sticky="ew")

        tk.Button(frm_add, text="+ Adicionar CUB",
                  font=("Calibri", 10, "bold"), bg=COR_VERDE, fg=COR_BRANCO,
                  relief="flat", padx=12, pady=6,
                  command=self._add_cub).grid(row=3, column=0, columnspan=4, pady=8)

        # Lista de CUBs
        cols_cub = ("Mês/Ano", "Categoria", "CUB (R$/m²)", "Fonte", "Observações")
        self.tree_cub = ttk.Treeview(tab, columns=cols_cub, show="headings", height=16)
        widths_cub = [100, 300, 110, 160, 250]
        for c, w in zip(cols_cub, widths_cub):
            self.tree_cub.heading(c, text=c)
            self.tree_cub.column(c, width=w)
        sb2 = ttk.Scrollbar(tab, orient="vertical", command=self.tree_cub.yview)
        self.tree_cub.configure(yscrollcommand=sb2.set)
        self.tree_cub.pack(side="left", fill="both", expand=True, padx=(10,0), pady=(0,10))
        sb2.pack(side="left", fill="y", pady=(0,10))
        self._load_cub_tree()

    # ─────────────────────────────────────────────────────────────────────────
    # Lógica
    # ─────────────────────────────────────────────────────────────────────────

    def _scrollable_frame(self, tab_title):
        outer = tk.Frame(self.nb, bg=COR_BRANCO)
        self.nb.add(outer, text=f"  {tab_title}  ")

        canvas = tk.Canvas(outer, bg=COR_BRANCO, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=COR_BRANCO)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas_configure(e):
            canvas.itemconfig(win_id, width=e.width)

        inner.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        return inner

    def _on_cub_select(self, event=None):
        cubvals = get_cub_values()
        sel = self.v_cub_sel.get()
        for label, val in cubvals:
            if label == sel:
                self.v_cub_valor.set(val)
                self.lbl_cub_valor.config(text=f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                break
        self._calcular()

    def _calcular(self):
        try:
            area = float(self.v_area_comp.get().replace(",", ".") or 0)
            cub  = self.v_cub_valor.get()
            perc = self.v_perc_comp.get()
            valor = area * cub * (perc / 100)
            fmt = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            self.v_val_comp.set(fmt)
            self.lbl_resultado.config(text=fmt)
        except Exception:
            self.lbl_resultado.config(text="—")

    def _refresh_cub_combo(self):
        cubvals = get_cub_values()
        self.cub_cb["values"] = [label for label, _ in cubvals]

    def _load_registros(self):
        self._all_registros = listar_registros()
        self._filtrar_registros()

    def _filtrar_registros(self):
        query = self.v_busca.get().lower()
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(self._all_registros):
            nome = str(row[2] or "")
            tipo = str(row[9] or "")
            area = str(row[12] or "")
            comp = str(row[53] or "")
            if query and query not in f"{nome} {tipo}".lower():
                continue
            tag = "odd" if i % 2 else "even"
            self.tree.insert("", "end",
                             values=(row[0], row[1], nome, tipo, area, comp),
                             tags=(tag,))

    def _load_cub_tree(self):
        self.tree_cub.delete(*self.tree_cub.get_children())
        if not os.path.exists(DB_FILE):
            return
        wb = openpyxl.load_workbook(DB_FILE, read_only=True, data_only=True)
        ws = wb["CUB"]
        for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
            if any(v is not None for v in row):
                vals = list(row)
                if isinstance(vals[2], float):
                    vals[2] = f"R$ {vals[2]:,.2f}".replace(",","X").replace(".",",").replace("X",".")
                tag = "odd" if i % 2 else "even"
                self.tree_cub.insert("", "end", values=vals, tags=(tag,))
        wb.close()

    def _add_cub(self):
        mes   = self.v_cub_mes.get().strip()
        cat   = self.v_cub_cat.get().strip()
        fonte = self.v_cub_fonte.get().strip()
        obs   = self.v_cub_obs.get().strip()
        try:
            val = float(self.v_cub_val_novo.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Erro", "CUB inválido. Use número (ex: 3200.50)")
            return
        if not mes or not cat:
            messagebox.showerror("Erro", "Informe Mês/Ano e Categoria.")
            return
        wb = openpyxl.load_workbook(DB_FILE)
        ws = wb["CUB"]
        ws.append([mes, cat, val, fonte, obs])
        wb.save(DB_FILE)
        messagebox.showinfo("Sucesso", f"CUB adicionado: {mes} – {cat} = R$ {val:,.2f}")
        self.v_cub_mes.set("")
        self.v_cub_cat.set("")
        self.v_cub_val_novo.set("")
        self.v_cub_obs.set("")
        self._load_cub_tree()
        self._refresh_cub_combo()

    def _coletar_dados(self):
        medidas_sel = [m for m, v in self.v_medidas_vars.items() if v.get()]
        dem_eq_sel  = [e for e, v in self.v_dem_equipamentos_vars.items() if v.get()]
        if self.v_dem_outros_txt.get():
            dem_eq_sel.append(f"Outros: {self.v_dem_outros_txt.get()}")

        try:
            area_c = float(self.v_area_construida.get().replace(",", ".") or 0)
        except Exception:
            area_c = None

        try:
            area_t = float(self.v_area_terreno.get().replace(",", ".") or 0)
        except Exception:
            area_t = None

        return {
            "nome_empreendimento"  : self.v_nome.get(),
            "endereco_empreendimento": self.v_endereco.get(),
            "matriculas"           : self.v_matriculas.get(),
            "proprietario"         : self.v_proprietario.get(),
            "endereco_proprietario": self.v_end_prop.get(),
            "bairro"               : self.v_bairro.get(),
            "responsavel_tecnico"  : self.v_resp_tec.get(),
            "tipo_empreendimento"  : self.v_tipo.get(),
            "tipo_outros"          : self.v_tipo_outros.get(),
            "area_terreno"         : area_t,
            "area_construida"      : area_c,
            "num_pavimentos"       : self.v_pavimentos.get(),
            "num_blocos"           : self.v_blocos.get(),
            "total_unidades"       : self.v_unidades.get(),
            "populacao_estimada"   : self.v_populacao.get(),
            "zona_adensamento"     : self.v_zona_adensamento.get(),
            "zoneamento"           : self.v_zoneamento.get(),
            "dem_equipamentos"     : "; ".join(dem_eq_sel),
            "uso_misto"            : self.v_uso_misto.get(),
            "impacto_topografia"   : self.v_impacto_topo.get(),
            "desc_topografia"      : self.v_desc_topo.get(),
            "via_grande_circulacao": self.v_via_circ.get(),
            "trafego_adicional"    : self.v_trafego_adic.get(),
            "vagas_estacionamento" : self.v_vagas.get(),
            "estudo_trafego"       : self.v_estudo_trafego.get(),
            "acesso_compativel"    : self.v_acesso_compat.get(),
            "estado_calcadas"      : self.v_calcadas.get(),
            "desc_calcadas"        : self.v_desc_calcadas.get(),
            "prox_intersecoes"     : self.v_prox_intersec.get(),
            "uso_transp_publico"   : self.v_uso_transp.get(),
            "desc_transp_publico"  : self.v_desc_transp.get(),
            "adensamento_pop"      : self.v_adensamento_pop.get(),
            "qtd_moradores"        : self.v_qtd_moradores.get(),
            "demandas_servicos"    : self.v_demandas_serv.get(),
            "area_vulnerabilidade" : self.v_area_vuln.get(),
            "espacos_publicos"     : self.v_espacos_pub.get(),
            "desc_espacos_publicos": self.v_desc_espacos.get(),
            "consulta_publica"     : self.v_consulta_pub.get(),
            "data_consulta"        : self.v_data_consulta.get(),
            "num_participantes"    : self.v_num_part.get(),
            "equipamentos_entorno" : self.txt_equip_entorno.get("1.0", "end").strip(),
            "transp_coletivo_disp" : self.v_transp_coletivo.get(),
            "saneamento_compativel": self.v_saneamento.get(),
            "det_saneamento"       : self.v_det_saneamento.get(),
            "areas_verdes"         : self.v_areas_verdes.get(),
            "area_verde_m2"        : self.v_area_verde_m2.get(),
            "sistema_residuos"     : self.v_residuos.get(),
            "desc_residuos"        : self.v_desc_residuos.get(),
            "medidas_compensacao"  : "; ".join(medidas_sel),
            "desc_outras_medidas"  : self.v_outras_medidas.get(),
            "cub_referencia"       : self.v_cub_valor.get() or None,
            "valor_compensacao"    : self.v_val_comp.get(),
            "observacoes"          : self.txt_obs.get("1.0", "end").strip(),
        }

    def _salvar(self):
        dados = self._coletar_dados()
        if not dados["nome_empreendimento"]:
            messagebox.showwarning("Atenção",
                "Preencha ao menos o nome do empreendimento (campo 1.1).")
            self.nb.select(0)
            return
        rid = salvar_registro(dados)
        messagebox.showinfo("Registro Salvo",
            f"✔ Registro #{rid} salvo com sucesso!\n\nArquivo: {DB_FILE}")
        self._load_registros()

    def _limpar(self):
        if not messagebox.askyesno("Limpar Formulário",
                "Deseja limpar todos os campos para um novo registro?"):
            return
        vars_str = [
            self.v_nome, self.v_endereco, self.v_matriculas, self.v_proprietario,
            self.v_end_prop, self.v_bairro, self.v_resp_tec, self.v_tipo,
            self.v_tipo_outros, self.v_area_terreno, self.v_area_construida,
            self.v_pavimentos, self.v_blocos, self.v_unidades, self.v_populacao,
            self.v_zona_adensamento, self.v_zoneamento, self.v_dem_outros_txt,
            self.v_uso_misto, self.v_impacto_topo, self.v_desc_topo, self.v_via_circ,
            self.v_trafego_adic, self.v_vagas, self.v_estudo_trafego,
            self.v_acesso_compat, self.v_calcadas, self.v_desc_calcadas,
            self.v_prox_intersec, self.v_uso_transp, self.v_desc_transp,
            self.v_adensamento_pop, self.v_qtd_moradores, self.v_demandas_serv,
            self.v_area_vuln, self.v_espacos_pub, self.v_desc_espacos,
            self.v_consulta_pub, self.v_data_consulta, self.v_num_part,
            self.v_transp_coletivo, self.v_saneamento, self.v_det_saneamento,
            self.v_areas_verdes, self.v_area_verde_m2, self.v_residuos,
            self.v_desc_residuos, self.v_outras_medidas, self.v_obs,
            self.v_cub_sel, self.v_area_comp,
        ]
        for v in vars_str:
            v.set("")
        self.v_cub_valor.set(0.0)
        self.v_perc_comp.set(5.0)
        self.v_val_comp.set("R$ 0,00")
        self.lbl_resultado.config(text="R$ 0,00")
        self.lbl_cub_valor.config(text="—")
        for v in self.v_medidas_vars.values():
            v.set(False)
        for v in self.v_dem_equipamentos_vars.values():
            v.set(False)
        self.txt_equip_entorno.delete("1.0", "end")
        self.txt_obs.delete("1.0", "end")
        self.nb.select(0)


if __name__ == "__main__":
    app = CMAIUApp()
    app.mainloop()
