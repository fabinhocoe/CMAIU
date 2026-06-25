from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

db = SQLAlchemy()

MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

SITUACOES_PROCESSO = [
    'Em análise', 'Aprovado', 'Aprovado com condicionantes',
    'Reprovado', 'Arquivado', 'Aguardando documentação'
]

USOS = [
    'Residencial Multifamiliar', 'Comercial', 'Industrial',
    'Serviços', 'Misto Residencial/Comercial', 'Institucional',
    'Logístico / Centro de Distribuição', 'Outros'
]

PADROES_IMPACTO = ['Baixo', 'Baixo a moderado', 'Moderado', 'Moderado a alto', 'Alto']

CLASSIFICACOES_IMPACTO = [
    'Inexistente', 'Baixo', 'Baixo a moderado', 'Moderado',
    'Moderado a alto', 'Alto', 'Não aplicável'
]

IMPACTOS_SOCIAIS = [
    ('dem_equip_pub',       'Aumento da demanda por equipamentos públicos'),
    ('dem_educacao',        'Aumento da demanda por educação'),
    ('dem_saude',           'Aumento da demanda por saúde'),
    ('dem_servicos',        'Aumento da demanda por serviços públicos'),
    ('alt_densidade',       'Alteração da densidade populacional'),
    ('interf_vizinhanca',   'Interferência na vizinhança'),
    ('outros_sociais',      'Outros impactos sociais'),
]

IMPACTOS_VIARIOS = [
    ('ger_viagens',         'Aumento da geração de viagens'),
    ('fluxo_veiculos',      'Aumento do fluxo de veículos'),
    ('intersecoes',         'Interferência em cruzamentos'),
    ('acessos',             'Acessos ao empreendimento'),
    ('transp_coletivo',     'Demanda por transporte coletivo'),
    ('estacionamento',      'Demanda por estacionamento'),
    ('calcadas',            'Condições das calçadas'),
    ('pedestres',           'Mobilidade de pedestres'),
    ('sinalizacao',         'Necessidade de sinalização'),
    ('melhorias_viarias',   'Necessidade de melhorias viárias'),
    ('outros_viarios',      'Outros impactos viários'),
]

NIVEIS_COMPENSACAO = [
    ('dispensado', 'Dispensado'),
    ('25', '25%'),
    ('50', '50%'),
    ('75', '75%'),
    ('100', '100%'),
]

PARAMS_INICIAIS = [
    ('hab_por_dormitorio',     'Habitantes por dormitório',         '2',    'hab/dorm'),
    ('fator_base_compensacao', 'Fator-base da compensação (FC)',    '0.33', '%'),
    ('nivel_1',                'Nível 1 da compensação',            '0.25', '%'),
    ('nivel_2',                'Nível 2 da compensação',            '0.50', '%'),
    ('nivel_3',                'Nível 3 da compensação',            '0.75', '%'),
    ('nivel_4',                'Nível 4 da compensação',            '1.00', '%'),
    ('perc_cub_solo_criado',   'Percentual do CUB para solo criado','0.06', '%'),
    ('limite_oneroso',         'Limite oneroso (%)',                '40',   '%'),
    ('limite_infra',           'Limite infraestrutura (%)',         '5',    '%'),
    ('limite_captacao',        'Limite captação (%)',               '5',    '%'),
    ('limite_total',           'Limite total (%)',                  '50',   '%'),
]


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    perfil = db.Column(db.String(20), nullable=False, default='consulta')
    situacao = db.Column(db.String(10), nullable=False, default='ativo')
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def set_senha(self, s):
        self.senha_hash = generate_password_hash(s)

    def check_senha(self, s):
        return check_password_hash(self.senha_hash, s)

    @property
    def is_admin(self):
        return self.perfil == 'administrador'

    @property
    def is_tecnico(self):
        return self.perfil in ('administrador', 'tecnico')

    @property
    def perfil_label(self):
        return {'administrador': 'Administrador', 'tecnico': 'Técnico', 'consulta': 'Consulta'}.get(self.perfil, self.perfil)


class Zoneamento(db.Model):
    __tablename__ = 'zoneamentos'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    descricao = db.Column(db.String(300), nullable=False)
    cab = db.Column(db.Float, nullable=False, default=1.0)
    cmax = db.Column(db.Float, nullable=False, default=4.0)
    permite_solo_criado = db.Column(db.Boolean, default=True)
    limite_oneroso = db.Column(db.Float, default=40.0)
    limite_infra = db.Column(db.Float, default=5.0)
    limite_captacao = db.Column(db.Float, default=5.0)
    norma = db.Column(db.String(200))
    observacoes = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True)

    @property
    def limite_total(self):
        return self.limite_oneroso + self.limite_infra + self.limite_captacao


class CUB(db.Model):
    __tablename__ = 'cub'
    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    valor = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(200), nullable=False, default='R8-N (Residencial 8 pav. - Normal)')
    fonte = db.Column(db.String(200), default='SINDUSCON-SC')
    data_publicacao = db.Column(db.Date)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    observacoes = db.Column(db.Text)

    usuario = db.relationship('Usuario', backref='cubs_cadastrados')

    @property
    def mes_ano_str(self):
        return f"{MESES[self.mes-1]}/{self.ano}"

    __table_args__ = (
        db.UniqueConstraint('mes', 'ano', 'categoria', name='uq_cub_mes_ano_cat'),
    )


class Parametro(db.Model):
    __tablename__ = 'parametros'
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), unique=True, nullable=False)
    descricao = db.Column(db.String(300), nullable=False)
    valor = db.Column(db.String(100), nullable=False)
    unidade = db.Column(db.String(20))

    @property
    def valor_float(self):
        try:
            return float(self.valor)
        except Exception:
            return 0.0


class HistoricoParametro(db.Model):
    __tablename__ = 'historico_parametros'
    id = db.Column(db.Integer, primary_key=True)
    parametro_id = db.Column(db.Integer, db.ForeignKey('parametros.id'))
    valor_anterior = db.Column(db.String(100))
    valor_novo = db.Column(db.String(100))
    data_alteracao = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    justificativa = db.Column(db.Text)

    parametro = db.relationship('Parametro', backref='historico')
    usuario = db.relationship('Usuario', backref='alteracoes_parametros')


class Integrante(db.Model):
    __tablename__ = 'integrantes'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    cargo = db.Column(db.String(200))
    orgao = db.Column(db.String(200))
    ativo = db.Column(db.Boolean, default=True)


# ---------------------------------------------------------------------------
# Cadastro unificado de pessoas (proprietários / compromissários)
# ---------------------------------------------------------------------------

PAPEIS_PROCESSO = ['Proprietário', 'Responsável Técnico', 'Representante Legal', 'Outro']
PAPEIS_TAC      = ['Compromissário', 'Responsável Técnico', 'Representante Legal', 'Outro']


class Pessoa(db.Model):
    """Cadastro único de pessoas físicas/jurídicas reutilizável em TACs e Processos."""
    __tablename__ = 'pessoas'
    id          = db.Column(db.Integer, primary_key=True)
    nome        = db.Column(db.String(300), nullable=False)
    cpf_cnpj    = db.Column(db.String(30), index=True)
    tipo        = db.Column(db.String(20), default='Pessoa Física')  # Pessoa Física / Pessoa Jurídica
    endereco    = db.Column(db.String(400))
    telefone    = db.Column(db.String(50))
    email       = db.Column(db.String(200))
    observacoes = db.Column(db.Text)
    criado_em   = db.Column(db.DateTime, default=datetime.utcnow)

    vinculos_processo = db.relationship('ProcessoPessoa', back_populates='pessoa', cascade='all, delete-orphan')
    vinculos_tac      = db.relationship('TACPessoa',      back_populates='pessoa', cascade='all, delete-orphan')

    @property
    def doc_formatado(self):
        d = (self.cpf_cnpj or '').replace('.','').replace('-','').replace('/','').replace(' ','')
        if len(d) == 11:
            return f'{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}'
        if len(d) == 14:
            return f'{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}'
        return self.cpf_cnpj or '—'

    def __repr__(self):
        return f'<Pessoa {self.nome}>'


class ProcessoPessoa(db.Model):
    """Vínculo entre Pessoa e Processo (many-to-many com papel)."""
    __tablename__ = 'processo_pessoas'
    id          = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey('processos.id'), nullable=False)
    pessoa_id   = db.Column(db.Integer, db.ForeignKey('pessoas.id'),   nullable=False)
    papel       = db.Column(db.String(60), default='Proprietário')

    processo = db.relationship('Processo', back_populates='pessoas_vinculadas')
    pessoa   = db.relationship('Pessoa',   back_populates='vinculos_processo')


class TACPessoa(db.Model):
    """Vínculo entre Pessoa e TAC (many-to-many com papel)."""
    __tablename__ = 'tac_pessoas'
    id       = db.Column(db.Integer, primary_key=True)
    tac_id   = db.Column(db.Integer, db.ForeignKey('tacs.id'),    nullable=False)
    pessoa_id= db.Column(db.Integer, db.ForeignKey('pessoas.id'), nullable=False)
    papel    = db.Column(db.String(60), default='Compromissário')

    tac    = db.relationship('TAC',    back_populates='pessoas_vinculadas')
    pessoa = db.relationship('Pessoa', back_populates='vinculos_tac')


# ---------------------------------------------------------------------------

class Processo(db.Model):
    __tablename__ = 'processos'
    id = db.Column(db.Integer, primary_key=True)
    num_processo = db.Column(db.String(100))
    protocolo_cmaiu = db.Column(db.String(100))
    protocolo_aprovacao = db.Column(db.String(100))
    data_entrada = db.Column(db.Date)
    data_analise = db.Column(db.Date)
    situacao = db.Column(db.String(80), default='Em análise')
    observacoes = db.Column(db.Text)
    criado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    usuario = db.relationship('Usuario', backref='processos')
    proprietario = db.relationship('Proprietario', uselist=False, back_populates='processo', cascade='all, delete-orphan')
    pessoas_vinculadas = db.relationship('ProcessoPessoa', back_populates='processo', cascade='all, delete-orphan')
    empreendimento = db.relationship('Empreendimento', uselist=False, back_populates='processo', cascade='all, delete-orphan')
    impactos = db.relationship('Impacto', back_populates='processo', cascade='all, delete-orphan')
    calculos = db.relationship('Calculo', back_populates='processo', cascade='all, delete-orphan', order_by='Calculo.data_calculo.desc()')
    relatorios = db.relationship('Relatorio', back_populates='processo', cascade='all, delete-orphan')

    @property
    def ultimo_calculo(self):
        return self.calculos[0] if self.calculos else None

    @property
    def ultimo_relatorio(self):
        return self.relatorios[-1] if self.relatorios else None

    @property
    def situacao_badge(self):
        cores = {
            'Em análise': 'warning',
            'Aprovado': 'success',
            'Aprovado com condicionantes': 'info',
            'Reprovado': 'danger',
            'Arquivado': 'secondary',
            'Aguardando documentação': 'primary',
        }
        return cores.get(self.situacao, 'secondary')


class Proprietario(db.Model):
    """Mantido para compatibilidade com dados legados. Novos vínculos usam ProcessoPessoa."""
    __tablename__ = 'proprietarios'
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey('processos.id'), unique=True)
    nome = db.Column(db.String(300))
    cpf_cnpj = db.Column(db.String(30))
    endereco = db.Column(db.String(400))
    telefone = db.Column(db.String(50))
    email = db.Column(db.String(200))

    processo = db.relationship('Processo', back_populates='proprietario')


class Empreendimento(db.Model):
    __tablename__ = 'empreendimentos'
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey('processos.id'), unique=True)
    nome = db.Column(db.String(300))
    endereco = db.Column(db.String(400))
    bairro = db.Column(db.String(200))
    inscricao = db.Column(db.String(100))
    matricula = db.Column(db.String(200))
    zoneamento_id = db.Column(db.Integer, db.ForeignKey('zoneamentos.id'))
    uso_predominante = db.Column(db.String(100))
    uso_secundario = db.Column(db.String(100))
    responsavel_tecnico = db.Column(db.String(200))
    registro_profissional = db.Column(db.String(100))
    # Dados urbanísticos
    area_terreno = db.Column(db.Float)
    area_construida = db.Column(db.Float)
    area_computavel = db.Column(db.Float)
    cab = db.Column(db.Float)
    cmax = db.Column(db.Float)
    num_pavimentos = db.Column(db.Integer)
    num_uh = db.Column(db.Integer)
    num_uc = db.Column(db.Integer)
    total_dormitorios = db.Column(db.Integer)
    pop_residencial = db.Column(db.Integer)
    pop_nao_residencial = db.Column(db.Integer)
    pop_total = db.Column(db.Integer)
    vagas = db.Column(db.Integer)
    padrao_impacto = db.Column(db.String(50))

    processo = db.relationship('Processo', back_populates='empreendimento')
    zoneamento = db.relationship('Zoneamento', backref='empreendimentos')


class Impacto(db.Model):
    __tablename__ = 'impactos'
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey('processos.id'))
    tipo = db.Column(db.String(20))
    chave = db.Column(db.String(60))
    descricao = db.Column(db.String(300))
    classificacao = db.Column(db.String(50), default='Inexistente')
    justificativa = db.Column(db.Text)
    medida_proposta = db.Column(db.Text)

    processo = db.relationship('Processo', back_populates='impactos')

    @property
    def badge_cor(self):
        cores = {
            'Inexistente': 'secondary', 'Baixo': 'success',
            'Baixo a moderado': 'info', 'Moderado': 'warning',
            'Moderado a alto': 'orange', 'Alto': 'danger',
            'Não aplicável': 'light',
        }
        return cores.get(self.classificacao, 'secondary')


class Calculo(db.Model):
    __tablename__ = 'calculos'
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey('processos.id'))
    cub_id = db.Column(db.Integer, db.ForeignKey('cub.id'))
    cub_valor = db.Column(db.Float)
    cub_mes_ref = db.Column(db.String(20))
    populacao = db.Column(db.Integer)
    fator_base = db.Column(db.Float, default=0.33)
    nivel_selecionado = db.Column(db.String(20))
    valor_compensacao = db.Column(db.Float, default=0)
    justificativa_dispensa = db.Column(db.Text)
    area_basica = db.Column(db.Float, default=0)
    area_excedente = db.Column(db.Float, default=0)
    perc_oneroso = db.Column(db.Float, default=0)
    area_onerosa = db.Column(db.Float, default=0)
    valor_oneroso = db.Column(db.Float, default=0)
    perc_infra = db.Column(db.Float, default=0)
    area_infra = db.Column(db.Float, default=0)
    valor_infra = db.Column(db.Float, default=0)
    desc_infra = db.Column(db.Text)
    loc_infra = db.Column(db.Text)
    perc_captacao = db.Column(db.Float, default=0)
    area_captacao = db.Column(db.Float, default=0)
    valor_captacao = db.Column(db.Float, default=0)
    desc_captacao = db.Column(db.Text)
    cap_reservatorio = db.Column(db.Float)
    uso_agua = db.Column(db.Text)
    padrao_impacto = db.Column(db.String(50))
    data_calculo = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

    processo = db.relationship('Processo', back_populates='calculos')
    cub = db.relationship('CUB', backref='calculos')
    usuario = db.relationship('Usuario', backref='calculos')

    @property
    def valor_base(self):
        if self.populacao and self.cub_valor:
            return self.populacao * self.cub_valor * (self.fator_base or 0.33)
        return 0

    @property
    def valor_25(self):
        return self.valor_base * 0.25

    @property
    def valor_50(self):
        return self.valor_base * 0.50

    @property
    def valor_75(self):
        return self.valor_base * 0.75

    @property
    def valor_100(self):
        return self.valor_base * 1.00

    @property
    def valor_total_solo(self):
        return (self.valor_oneroso or 0) + (self.valor_infra or 0) + (self.valor_captacao or 0)

    @property
    def perc_total(self):
        return (self.perc_oneroso or 0) + (self.perc_infra or 0) + (self.perc_captacao or 0)

    @property
    def area_total_solo(self):
        return (self.area_onerosa or 0) + (self.area_infra or 0) + (self.area_captacao or 0)

    @property
    def valor_unitario(self):
        if self.cub_valor:
            return self.cub_valor * 0.06
        return 0

    @property
    def nivel_label(self):
        return {'dispensado': 'Dispensado', '25': '25%', '50': '50%',
                '75': '75%', '100': '100%'}.get(self.nivel_selecionado, '-')


class Relatorio(db.Model):
    __tablename__ = 'relatorios'
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey('processos.id'))
    numero = db.Column(db.String(50))
    data = db.Column(db.Date, default=date.today)
    versao = db.Column(db.Integer, default=1)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    deliberacao = db.Column(db.Text)
    medidas = db.Column(db.Text)
    obs_deliberacao = db.Column(db.Text)
    emitido_em = db.Column(db.DateTime, default=datetime.utcnow)

    processo = db.relationship('Processo', back_populates='relatorios')
    usuario = db.relationship('Usuario', backref='relatorios')


# ─── TAC – Termo de Ajustamento de Conduta (Lei Municipal 5.031/2021) ────────

SITUACOES_TAC = [
    'Rascunho', 'Em análise', 'Cálculo concluído',
    'Aguardando parecer jurídico', 'Pronto para assinatura',
    'Assinado', 'Publicado', 'Cancelado',
]

GRUPOS_OBRA = [
    ('G1', 'Grupo 1 – Unifamiliar'),
    ('G2', 'Grupo 2 – Multifamiliar / Comercial / Industrial'),
]

TIPOS_IRREGULARIDADE = [
    ('afastamento_lateral_fundos',    'Afastamentos laterais/fundos'),
    ('recuo_frontal_ate50',           'Recuo frontal – desconformidade ≤ 50%'),
    ('recuo_frontal_acima50',         'Recuo frontal – desconformidade > 50%'),
    ('dimensoes_ambientes',           'Dimensões de ambientes'),
    ('taxa_ocupacao_ate50',           'Taxa de ocupação em excesso ≤ 50%'),
    ('taxa_ocupacao_acima50',         'Taxa de ocupação em excesso > 50%'),
    ('indice_aproveitamento_ate50',   'Índice de aproveitamento em excesso ≤ 50%'),
    ('indice_aproveitamento_acima50', 'Índice de aproveitamento em excesso > 50%'),
    ('gabarito',                      'Gabarito – pav. excedente (máx. 2)'),
    ('demais',                        'Demais irregularidades (por item)'),
]

PERC_TAC = {
    ('afastamento_lateral_fundos',    'G1'): 0.005,
    ('afastamento_lateral_fundos',    'G2'): 0.010,
    ('recuo_frontal_ate50',           'G1'): 0.010,
    ('recuo_frontal_ate50',           'G2'): 0.020,
    ('recuo_frontal_acima50',         'G1'): 0.015,
    ('recuo_frontal_acima50',         'G2'): 0.025,
    ('dimensoes_ambientes',           'G1'): 0.005,
    ('dimensoes_ambientes',           'G2'): 0.010,
    ('taxa_ocupacao_ate50',           'G1'): 0.005,
    ('taxa_ocupacao_ate50',           'G2'): 0.010,
    ('taxa_ocupacao_acima50',         'G1'): 0.010,
    ('taxa_ocupacao_acima50',         'G2'): 0.020,
    ('indice_aproveitamento_ate50',   'G1'): 0.005,
    ('indice_aproveitamento_ate50',   'G2'): 0.010,
    ('indice_aproveitamento_acima50', 'G1'): 0.010,
    ('indice_aproveitamento_acima50', 'G2'): 0.020,
    ('gabarito',                      'G1'): 0.025,
    ('gabarito',                      'G2'): 0.025,
    ('demais',                        'G1'): 0.010,
    ('demais',                        'G2'): 0.010,
}

DICT_IREG = dict(TIPOS_IRREGULARIDADE)


class TAC(db.Model):
    __tablename__ = 'tacs'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50))
    versao = db.Column(db.Integer, default=1)
    situacao = db.Column(db.String(60), default='Rascunho')
    num_processo_adm = db.Column(db.String(100))
    data_abertura = db.Column(db.Date, default=date.today)
    data_assinatura = db.Column(db.Date)
    data_publicacao = db.Column(db.Date)
    cub_id = db.Column(db.Integer, db.ForeignKey('cub.id'))
    observacoes = db.Column(db.Text)
    criado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cub = db.relationship('CUB', backref='tacs')
    usuario = db.relationship('Usuario', backref='tacs')
    compromissarios = db.relationship('CompromissarioTAC', back_populates='tac',
                                      cascade='all, delete-orphan')
    pessoas_vinculadas = db.relationship('TACPessoa', back_populates='tac',
                                         cascade='all, delete-orphan')
    obras = db.relationship('ObraTAC', back_populates='tac',
                            cascade='all, delete-orphan')
    calculo = db.relationship('CalculoTAC', uselist=False, back_populates='tac',
                              cascade='all, delete-orphan')

    @property
    def situacao_badge(self):
        cores = {
            'Rascunho': 'secondary', 'Em análise': 'warning',
            'Cálculo concluído': 'info',
            'Aguardando parecer jurídico': 'primary',
            'Pronto para assinatura': 'success',
            'Assinado': 'success', 'Publicado': 'dark',
            'Cancelado': 'danger',
        }
        return cores.get(self.situacao, 'secondary')

    @property
    def bloqueado(self):
        return self.situacao in ('Assinado', 'Publicado')


class CompromissarioTAC(db.Model):
    __tablename__ = 'compromissarios_tac'
    id = db.Column(db.Integer, primary_key=True)
    tac_id = db.Column(db.Integer, db.ForeignKey('tacs.id'))
    nome = db.Column(db.String(300), nullable=False)
    cpf_cnpj = db.Column(db.String(30))
    endereco = db.Column(db.String(400))
    telefone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    tipo = db.Column(db.String(60), default='Proprietário')

    tac = db.relationship('TAC', back_populates='compromissarios')


class ObraTAC(db.Model):
    __tablename__ = 'obras_tac'
    id = db.Column(db.Integer, primary_key=True)
    tac_id = db.Column(db.Integer, db.ForeignKey('tacs.id'))
    descricao = db.Column(db.String(300))
    endereco = db.Column(db.String(400))
    bairro = db.Column(db.String(200))
    inscricao_imobiliaria = db.Column(db.String(100))
    grupo = db.Column(db.String(5), default='G1')
    area_construida = db.Column(db.Float, default=0.0)
    is_unifamiliar_ate150 = db.Column(db.Boolean, default=False)
    data_construcao = db.Column(db.Date)
    observacoes = db.Column(db.Text)

    tac = db.relationship('TAC', back_populates='obras')
    irregularidades = db.relationship('IrregularidadeTAC', back_populates='obra',
                                      cascade='all, delete-orphan')
    vagas = db.relationship('VagasTAC', uselist=False, back_populates='obra',
                            cascade='all, delete-orphan')

    @property
    def grupo_label(self):
        return dict(GRUPOS_OBRA).get(self.grupo, self.grupo)

    def calcular(self, cub_valor, data_tac):
        """Retorna dict com todos os valores calculados para esta obra.

        Vagas (Lei 5.031/2021 com redação da Lei 5.410/2024):
          - Calculadas exclusivamente por QVF × CUB × fator — sem área.
          - QVF = max(0, exigidas − computáveis)
          - QVF 1–5 → fator 1,0; QVF > 5 → fator 1,5 sobre TODAS as faltantes.
          - Vagas dim. irregular: QVD × CUB × 0,5 (sem área).
          - MTV integra o subtotal bruto; teto legal aplica-se ao consolidado.
        """
        area = self.area_construida or 0.0
        g = self.grupo or 'G1'

        # Irregularidades percentuais (sb_ireg usa área conforme lei)
        sb_ireg = 0.0
        itens = []
        for irr in self.irregularidades:
            perc = PERC_TAC.get((irr.tipo, g), 0.0)
            qty = min(irr.quantidade, 2) if irr.tipo == 'gabarito' else irr.quantidade
            subtotal = area * cub_valor * perc * qty
            sb_ireg += subtotal
            itens.append({'tipo': irr.tipo, 'descricao': DICT_IREG.get(irr.tipo, irr.tipo),
                          'perc': perc * 100, 'qty': qty, 'subtotal': subtotal})

        # Vagas — Lei 5.410/2024: SÓ CUB, sem área
        mtv = sv_faltantes = sv_dim = 0.0
        vagas_info = {}
        if self.vagas:
            v = self.vagas
            qvf = max(0, v.vagas_faltantes or 0)
            qvd = v.vagas_dimensao_irregular or 0
            fator_faltantes = 1.5 if qvf > 5 else (1.0 if qvf > 0 else 0.0)
            sv_faltantes = qvf * cub_valor * fator_faltantes
            sv_dim = qvd * cub_valor * 0.5
            mtv = sv_faltantes + sv_dim
            vagas_info = {
                'exigidas': v.vagas_exigidas or 0,
                'regulares_executadas': v.vagas_regulares_executadas or 0,
                'computaveis': v.vagas_computaveis or 0,
                'qvf': qvf,
                'qvd': qvd,
                'fator_faltantes': fator_faltantes,
                'sv_faltantes': sv_faltantes,
                'sv_dim': sv_dim,
                'mtv': mtv,
                'largura_exigida': v.largura_exigida,
                'comprimento_exigido': v.comprimento_exigido,
                'largura_executada': v.largura_executada,
                'comprimento_executado': v.comprimento_executado,
                'justificativa': v.justificativa_tecnica,
            }

        # Subtotal bruto = irregularidades percentuais + multa total vagas
        sb = sb_ireg + mtv

        # Teto legal: CUB × área × 5% (aplica-se ao consolidado)
        tl = cub_valor * area * 0.05
        vba = min(sb, tl)

        # Fator de acréscimo (FA)
        fa = 1.0
        if data_tac and self.data_construcao:
            anos = (data_tac - self.data_construcao).days / 365.25
            if anos < 5:
                fa = 1.20

        # Fator de redução por idade (FR)
        fr = 1.0
        data_corte = date(1993, 4, 7)
        if self.data_construcao:
            if self.data_construcao <= data_corte:
                fr = 0.0
            elif data_tac:
                anos = (data_tac - self.data_construcao).days / 365.25
                if anos >= 15:
                    fr = 0.60
                elif anos > 10:
                    fr = 0.70

        # Fator unifamiliar ≤150 m²
        f_uni = 0.5 if (g == 'G1' and area <= 150 and self.is_unifamiliar_ate150) else 1.0

        vf = vba * fa * fr * f_uni

        return {
            'area': area, 'cub': cub_valor, 'grupo': g,
            'itens_ireg': itens,
            'sb_ireg': sb_ireg,
            'vagas': vagas_info,
            'sv_faltantes': sv_faltantes, 'sv_dim': sv_dim, 'mtv': mtv,
            'sb': sb, 'tl': tl, 'vba': vba,
            'fa': fa, 'fr': fr, 'f_uni': f_uni, 'vf': vf,
        }


class IrregularidadeTAC(db.Model):
    __tablename__ = 'irregularidades_tac'
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras_tac.id'))
    tipo = db.Column(db.String(60), nullable=False)
    quantidade = db.Column(db.Integer, default=1)

    obra = db.relationship('ObraTAC', back_populates='irregularidades')

    @property
    def descricao(self):
        return DICT_IREG.get(self.tipo, self.tipo)


class VagasTAC(db.Model):
    """Vagas de estacionamento — Lei 5.031/2021, redação Lei 5.410/2024.
    Cálculo: SÓ CUB, sem área construída."""
    __tablename__ = 'vagas_tac'
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras_tac.id'), unique=True)

    # Quantidades (seção 15 da instrução)
    vagas_exigidas = db.Column(db.Integer, default=0)
    vagas_regulares_executadas = db.Column(db.Integer, default=0)
    vagas_computaveis = db.Column(db.Integer, default=0)
    vagas_faltantes = db.Column(db.Integer, default=0)       # max(0, exigidas - computaveis)
    vagas_dimensao_irregular = db.Column(db.Integer, default=0)

    # Dimensões
    largura_exigida = db.Column(db.Float)
    comprimento_exigido = db.Column(db.Float)
    largura_executada = db.Column(db.Float)
    comprimento_executado = db.Column(db.Float)

    # Justificativa para preenchimento manual de QVF
    justificativa_tecnica = db.Column(db.Text)

    # Auditoria
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    data_calculo = db.Column(db.DateTime)

    obra = db.relationship('ObraTAC', back_populates='vagas')
    usuario = db.relationship('Usuario', backref='vagas_tac')

    @property
    def qvf_calculado(self):
        return max(0, (self.vagas_exigidas or 0) - (self.vagas_computaveis or 0))


class CalculoTAC(db.Model):
    __tablename__ = 'calculos_tac'
    id = db.Column(db.Integer, primary_key=True)
    tac_id = db.Column(db.Integer, db.ForeignKey('tacs.id'), unique=True)
    cub_valor = db.Column(db.Float)
    cub_mes_ref = db.Column(db.String(20))
    vf_total = db.Column(db.Float, default=0.0)
    num_parcelas = db.Column(db.Integer, default=1)
    valor_parcela = db.Column(db.Float, default=0.0)
    resultado_json = db.Column(db.Text)  # JSON serializado por obra
    data_calculo = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

    tac = db.relationship('TAC', back_populates='calculo')
    usuario = db.relationship('Usuario', backref='calculos_tac')
