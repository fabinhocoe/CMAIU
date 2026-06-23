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
