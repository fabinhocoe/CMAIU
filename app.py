"""
CMAIU – Sistema de Cálculo e Relatórios
Comissão Municipal de Avaliação de Impacto Urbano – Palhoça/SC
"""
import os, io, re, secrets
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, send_file, abort, session, g)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import json
from models import (db, Usuario, Zoneamento, CUB, Parametro, HistoricoParametro,
                    Integrante, Processo, Proprietario, Empreendimento, Obra,
                    Impacto, Calculo, Relatorio,
                    Pessoa, ProcessoPessoa, TACPessoa,
                    SITUACOES_PROCESSO, USOS, PADROES_IMPACTO,
                    CLASSIFICACOES_IMPACTO, IMPACTOS_SOCIAIS, IMPACTOS_VIARIOS,
                    NIVEIS_COMPENSACAO, PARAMS_INICIAIS, MESES,
                    TAC, CompromissarioTAC, ObraTAC, IrregularidadeTAC,
                    VagasTAC, CalculoTAC,
                    SITUACOES_TAC, GRUPOS_OBRA, TIPOS_IRREGULARIDADE, PERC_TAC,
                    PAPEIS_PROCESSO, PAPEIS_TAC,
                    SoloCriado, SITUACOES_SC,
                    ResponsavelTecnico)

app = Flask(__name__)

# Chave secreta: sempre via variável de ambiente em produção
_default_key = secrets.token_hex(32)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', _default_key)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cmaiu.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Segurança de sessão
app.config['SESSION_COOKIE_HTTPONLY'] = True   # JS não acessa o cookie
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' # Proteção CSRF básica
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
# Em produção com HTTPS, ativar: app.config['SESSION_COOKIE_SECURE'] = True

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para acessar o sistema.'
login_manager.login_message_category = 'warning'

# ─── CSRF Protection (token manual) ─────────────────────────────────────────

def _generate_csrf():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

def _check_csrf():
    """Valida token CSRF em todas as requisições POST."""
    if request.method == 'POST':
        token = session.get('_csrf_token')
        form_token = request.form.get('_csrf_token') or request.headers.get('X-CSRFToken')
        if not token or not form_token or not secrets.compare_digest(token, form_token):
            abort(403)

app.jinja_env.globals['csrf_token'] = _generate_csrf

@app.before_request
def enforce_csrf():
    # Login tem seu próprio token; static não tem form
    if request.endpoint not in ('login', 'static', None):
        _check_csrf()

# ─── Rate limiting simples (tentativas de login) ─────────────────────────────

_login_attempts: dict = {}  # ip -> [timestamps]

def _check_rate_limit(ip: str) -> bool:
    """Bloqueia IP após 10 tentativas de login em 5 minutos."""
    now = datetime.utcnow()
    window = timedelta(minutes=5)
    attempts = [t for t in _login_attempts.get(ip, []) if now - t < window]
    _login_attempts[ip] = attempts
    return len(attempts) >= 10

def _record_attempt(ip: str):
    _login_attempts.setdefault(ip, []).append(datetime.utcnow())


@login_manager.user_loader
def load_user(uid):
    return db.session.get(Usuario, int(uid))


# ─── Decoradores ────────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def tecnico_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_tecnico:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ─── Helpers ────────────────────────────────────────────────────────────────

def get_param(chave, default=None):
    p = Parametro.query.filter_by(chave=chave).first()
    return p.valor_float if p else (float(default) if default is not None else 0.0)


def fmt_brl(valor):
    if valor is None:
        return 'R$ 0,00'
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


app.jinja_env.filters['brl'] = fmt_brl
app.jinja_env.filters['fmt_area'] = lambda v: f"{v:,.2f} m²".replace(',', 'X').replace('.', ',').replace('X', '.') if v else '0,00 m²'
app.jinja_env.filters['fmt_perc'] = lambda v: f"{v:.4f}%".rstrip('0').rstrip('.') + '%' if v else '0%'
app.jinja_env.globals['now'] = datetime.now

def _gerar_senha_temporaria():
    """Gera senha segura temporária: 12 caracteres com letras, números, símbolos."""
    import string
    chars = string.ascii_letters + string.digits + '!@#$%'
    return ''.join(secrets.choice(chars) for _ in range(12))


def _validar_numero(valor, min_val=0, max_val=None, nome_campo='campo'):
    """Valida se valor é número válido dentro de range."""
    try:
        num = float(valor) if valor else 0
        if num < min_val:
            return None, f'{nome_campo} não pode ser menor que {min_val}'
        if max_val and num > max_val:
            return None, f'{nome_campo} não pode ser maior que {max_val}'
        return num, None
    except (ValueError, TypeError):
        return None, f'{nome_campo} deve ser um número válido'


def _validar_texto(valor, min_len=1, max_len=255, nome_campo='campo'):
    """Valida se texto está dentro dos limites."""
    if not valor or not str(valor).strip():
        if min_len > 0:
            return None, f'{nome_campo} é obrigatório'
        return '', None

    texto = str(valor).strip()
    if len(texto) < min_len:
        return None, f'{nome_campo} deve ter no mínimo {min_len} caracteres'
    if len(texto) > max_len:
        return None, f'{nome_campo} não pode ter mais de {max_len} caracteres'
    return texto, None


def _validar_data(valor, nome_campo='data'):
    """Valida se data é válida e não é futura."""
    if not valor:
        return None, f'{nome_campo} é obrigatória'

    data = _parse_date(valor)
    if not data:
        return None, f'{nome_campo} inválida'

    if data > date.today():
        return None, f'{nome_campo} não pode ser futura'

    return data, None


def _fmt_fone(v):
    """Formata telefone para exibição: (XX) XXXXX-XXXX ou (XX) XXXX-XXXX."""
    if not v:
        return '—'
    d = re.sub(r'\D', '', str(v))
    if len(d) == 11:
        return f'({d[:2]}) {d[2:7]}-{d[7:]}'
    if len(d) == 10:
        return f'({d[:2]}) {d[2:6]}-{d[6:]}'
    return v or '—'

def _fmt_doc(v):
    """Formata CPF (11 dígitos) ou CNPJ (14 dígitos) para exibição."""
    if not v:
        return '—'
    d = re.sub(r'\D', '', str(v))
    if len(d) == 11:
        return f'{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}'
    if len(d) == 14:
        return f'{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}'
    return v or '—'

def _fmt_inscricao(v):
    """Formata inscrição imobiliária para XX.XX.XXX.XXXX (11 dígitos)."""
    if not v:
        return '—'
    d = re.sub(r'\D', '', str(v))
    if len(d) == 11:
        return f'{d[:2]}.{d[2:4]}.{d[4:7]}.{d[7:]}'
    return v or '—'

app.jinja_env.filters['fmt_fone']     = _fmt_fone
app.jinja_env.filters['fmt_doc']      = _fmt_doc
app.jinja_env.filters['fmt_inscricao'] = _fmt_inscricao


# ─── Auth ────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        ip = request.remote_addr or '0.0.0.0'
        if _check_rate_limit(ip):
            flash('Muitas tentativas. Aguarde 5 minutos.', 'danger')
            return render_template('login.html')
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        u = Usuario.query.filter_by(email=email, situacao='ativo').first()
        if u and u.check_senha(senha):
            login_user(u, remember=False)   # sem cookie permanente
            session.permanent = True        # expira em 8h conforme config
            # Valida o next para evitar open redirect
            next_url = request.args.get('next', '')
            if next_url and not next_url.startswith('/'):
                next_url = ''
            return redirect(next_url or url_for('dashboard'))
        _record_attempt(ip)
        flash('E-mail ou senha inválidos.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ─── Dashboard ───────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    hoje = date.today()
    ano_atual = hoje.year

    cub_atual = CUB.query.order_by(CUB.ano.desc(), CUB.mes.desc()).first()
    cub_mes_faltante = not (cub_atual and cub_atual.mes == hoje.month and cub_atual.ano == hoje.year)

    # ── CMAIU / Processos ──
    processos = Processo.query.all()
    proc_ano = [p for p in processos if p.criado_em and p.criado_em.year == ano_atual]
    proc_totais = {
        'ano': ano_atual,
        'total': len(processos),
        'qtd_ano': len(proc_ano),
        'em_analise': sum(1 for p in processos if p.situacao == 'Em análise'),
        'aprovados': sum(1 for p in processos if p.situacao == 'Aprovado'),
        'vcomp': sum(p.ultimo_calculo.valor_compensacao or 0 for p in proc_ano
                     if p.ultimo_calculo and p.ultimo_calculo.nivel_selecionado),
    }
    proc_recentes = Processo.query.order_by(Processo.criado_em.desc()).limit(5).all()

    # ── TAC ──
    tacs = TAC.query.all()
    tacs_ano = [t for t in tacs if t.criado_em and t.criado_em.year == ano_atual]
    tac_totais = {
        'ano': ano_atual,
        'total': len(tacs),
        'qtd_ano': len(tacs_ano),
        'em_andamento': sum(1 for t in tacs if t.situacao not in
                             ('Assinado', 'Publicado', 'Cancelado')),
        'concluidos': sum(1 for t in tacs if t.situacao in ('Assinado', 'Publicado')),
        'vtot': sum(t.calculo.vf_total for t in tacs_ano if t.calculo),
    }
    tac_recentes = TAC.query.order_by(TAC.criado_em.desc()).limit(5).all()

    # ── Solo Criado ──
    registros_sc = SoloCriado.query.all()
    sc_ano = [r for r in registros_sc if r.criado_em and r.criado_em.year == ano_atual]
    sc_totais = {
        'ano': ano_atual,
        'total': len(registros_sc),
        'qtd_ano': len(sc_ano),
        'em_andamento': sum(1 for r in registros_sc if r.situacao not in
                             ('Aprovado', 'Encaminhado à Receita', 'Guia emitida', 'Cancelado', 'Substituído por nova versão')),
        'aprovados': sum(1 for r in registros_sc if r.situacao in
                          ('Aprovado', 'Encaminhado à Receita', 'Guia emitida')),
        'vtot': sum((r.von or 0) + (r.vin or 0) for r in sc_ano),
    }
    sc_recentes = SoloCriado.query.order_by(SoloCriado.criado_em.desc()).limit(5).all()

    # ── Dados para gráficos — últimos 12 meses ──
    meses_labels = []
    graf_proc_qtd, graf_tac_qtd, graf_sc_qtd = [], [], []
    graf_proc_val, graf_tac_val, graf_sc_val = [], [], []

    for i in range(11, -1, -1):
        total_months = hoje.year * 12 + hoje.month - 1 - i
        a, m = divmod(total_months, 12)
        m += 1
        meses_labels.append(f"{m:02d}/{a}")

        # quantidades
        graf_proc_qtd.append(sum(1 for p in processos
                                 if p.criado_em and p.criado_em.year == a and p.criado_em.month == m))
        graf_tac_qtd.append(sum(1 for t in tacs
                                if t.criado_em and t.criado_em.year == a and t.criado_em.month == m))
        graf_sc_qtd.append(sum(1 for r in registros_sc
                               if r.criado_em and r.criado_em.year == a and r.criado_em.month == m))

        # valores arrecadados (apenas processos com cálculo e nível selecionado)
        graf_proc_val.append(round(sum(
            p.ultimo_calculo.valor_compensacao or 0
            for p in processos
            if p.criado_em and p.criado_em.year == a and p.criado_em.month == m
            and p.ultimo_calculo and p.ultimo_calculo.nivel_selecionado), 2))
        graf_tac_val.append(round(sum(
            t.calculo.vf_total for t in tacs
            if t.criado_em and t.criado_em.year == a and t.criado_em.month == m
            and t.calculo), 2))
        graf_sc_val.append(round(sum(
            (r.von or 0) + (r.vin or 0)
            for r in registros_sc
            if r.criado_em and r.criado_em.year == a and r.criado_em.month == m), 2))

    return render_template('dashboard.html', ano_atual=ano_atual, cub_atual=cub_atual,
                           cub_mes_faltante=cub_mes_faltante,
                           proc_totais=proc_totais, proc_recentes=proc_recentes,
                           tac_totais=tac_totais, tac_recentes=tac_recentes,
                           sc_totais=sc_totais, sc_recentes=sc_recentes,
                           meses_labels=meses_labels,
                           graf_proc_qtd=graf_proc_qtd, graf_tac_qtd=graf_tac_qtd, graf_sc_qtd=graf_sc_qtd,
                           graf_proc_val=graf_proc_val, graf_tac_val=graf_tac_val, graf_sc_val=graf_sc_val)


# ─── Processos ───────────────────────────────────────────────────────────────

@app.route('/processos')
@login_required
def processos_index():
    q = request.args.get('q', '')
    sit = request.args.get('situacao', '')
    sort = request.args.get('sort', 'data_entrada')
    order = request.args.get('order', 'desc')

    query = Processo.query
    if q:
        like = f'%{q}%'
        query = query.filter(
            Processo.num_processo.ilike(like) |
            Processo.protocolo_cmaiu.ilike(like) |
            Processo.protocolo_aprovacao.ilike(like)
        )
    if sit:
        query = query.filter_by(situacao=sit)

    # Aplicar ordenação
    sort_map = {
        'num_processo': Processo.num_processo,
        'situacao': Processo.situacao,
        'data_entrada': Processo.data_entrada,
        'proprietario': Proprietario.nome,
        'empreendimento': Empreendimento.nome,
        'bairro': Empreendimento.bairro,
    }
    sort_column = sort_map.get(sort, Processo.data_entrada)

    # Se for ordenar por proprietário, empreendimento ou bairro, fazer join
    if sort in ['proprietario', 'empreendimento', 'bairro']:
        query = query.outerjoin(Processo.proprietario).outerjoin(Processo.empreendimento)

    if order == 'asc':
        processos = query.order_by(sort_column.asc()).all()
    else:
        processos = query.order_by(sort_column.desc()).all()
    ano_atual = date.today().year
    proc_ano = [p for p in processos if p.criado_em and p.criado_em.year == ano_atual]

    # Calcular infraestrutura de solo criado por processo
    v_infra_total = 0
    for p in proc_ano:
        if p.empreendimento and p.empreendimento.obra and p.empreendimento.obra.solos_criados_vinculados:
            v_infra_total += sum(sc.vin or 0 for sc in p.empreendimento.obra.solos_criados_vinculados)

    v_cmu = sum(p.ultimo_calculo.valor_compensacao or 0 for p in proc_ano if p.ultimo_calculo and p.ultimo_calculo.nivel_selecionado)

    totais_ano = {
        'ano': ano_atual,
        'qtd': len(proc_ano),
        'com_calculo': sum(1 for p in proc_ano if p.ultimo_calculo),
        'vcomp': v_cmu,
        'v_cmu': v_cmu,
        'v_infra': v_infra_total,
        'v_total': v_cmu + v_infra_total,
    }
    return render_template('processos/index.html', processos=processos,
                           q=q, sit=sit, situacoes=SITUACOES_PROCESSO, totais_ano=totais_ano,
                           sort=sort, order=order)


@app.route('/processos/pessoas/buscar')
@login_required
def processos_pessoas_buscar():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return {'resultados': []}
    like = f'%{q}%'
    pessoas = Pessoa.query.filter(
        Pessoa.nome.ilike(like) | Pessoa.cpf_cnpj.ilike(like)
    ).order_by(Pessoa.nome).limit(10).all()
    return {'resultados': [
        {'id': p.id, 'nome': p.nome, 'cpf_cnpj': p.cpf_cnpj or '',
         'telefone': p.telefone or '', 'email': p.email or ''}
        for p in pessoas
    ]}


def _salvar_pessoas_processo(processo_id, form):
    """Vincula pessoas selecionadas e/ou cria nova pessoa inline."""
    ids_selecionados = form.getlist('pessoa_id')
    for pid_str in ids_selecionados:
        pid = _int(pid_str)
        if pid and not ProcessoPessoa.query.filter_by(
                processo_id=processo_id, pessoa_id=pid).first():
            db.session.add(ProcessoPessoa(
                processo_id=processo_id, pessoa_id=pid, papel='Proprietário'))

    # Cadastro inline de nova pessoa
    novo_nome = form.get('nova_pessoa_nome', '').strip()
    if novo_nome:
        nova = Pessoa(
            nome=novo_nome,
            cpf_cnpj=form.get('nova_pessoa_cpf_cnpj', '').strip() or None,
            telefone=form.get('nova_pessoa_telefone', '').strip() or None,
            email=form.get('nova_pessoa_email', '').strip() or None,
            endereco=form.get('nova_pessoa_endereco', '').strip() or None,
        )
        db.session.add(nova)
        db.session.flush()
        db.session.add(ProcessoPessoa(
            processo_id=processo_id, pessoa_id=nova.id, papel='Proprietário'))


@app.route('/processos/novo', methods=['GET', 'POST'])
@login_required
@tecnico_required
def processos_novo():
    zoneamentos = Zoneamento.query.filter_by(ativo=True).order_by(Zoneamento.codigo).all()
    pessoas = Pessoa.query.order_by(Pessoa.nome).all()
    if request.method == 'POST':
        f = request.form
        # Validação de campos obrigatórios
        erros = []
        campos_obrigatorios = {
            'emp_nome': 'Nome do Empreendimento',
            'emp_padrao_empreendimento': 'Padrão do Empreendimento',
            'num_uc': 'Unidades Comerciais',
            'vagas': 'Nº de Vagas',
            'padrao_impacto': 'Padrão de Impacto',
            'total_dormitorios': 'Total de Dormitórios',
        }
        for campo, label in campos_obrigatorios.items():
            if not f.get(campo) or (campo in ['num_uc', 'vagas', 'total_dormitorios'] and f.get(campo) == ''):
                erros.append(f'{label} é obrigatório.')

        if erros:
            for erro in erros:
                flash(erro, 'danger')
            return redirect(url_for('processos_novo'))

        p = Processo(
            num_processo=f.get('num_processo'),
            protocolo_aprovacao=f.get('protocolo_aprovacao'),
            data_entrada=_parse_date(f.get('data_entrada')),
            data_analise=_parse_date(f.get('data_analise')),
            situacao=f.get('situacao', 'Em análise'),
            observacoes=f.get('observacoes'),
            criado_por=current_user.id,
        )
        db.session.add(p)
        db.session.flush()

        _salvar_pessoas_processo(p.id, f)

        zon_id = _int(f.get('zoneamento_id'))
        zon = Zoneamento.query.get(zon_id) if zon_id else None
        emp = Empreendimento(
            processo_id=p.id,
            obra_id=_get_or_create_obra(f, current_user.id),
            nome=f.get('emp_nome'),
            cep=f.get('emp_cep'),
            endereco=f.get('emp_endereco'),
            bairro=f.get('emp_bairro'),
            inscricao=f.get('emp_inscricao'),
            matricula=f.get('emp_matricula'),
            zoneamento_id=zon_id,
            uso_predominante=f.get('emp_uso_predominante'),
            uso_secundario=f.get('emp_uso_secundario'),
            padrao_empreendimento=f.get('emp_padrao_empreendimento'),
            responsavel_tecnico=f.get('emp_responsavel_tecnico'),
            registro_profissional=f.get('emp_registro_profissional'),
            area_terreno=_float(f.get('area_terreno')),
            area_construida=_float(f.get('area_construida')),
            area_computavel=_float(f.get('area_computavel')),
            cab=_float(f.get('cab')) or (zon.cab if zon else None),
            cmax=_float(f.get('cmax')) or (zon.cmax if zon else None),
            num_pavimentos=_int(f.get('num_pavimentos')),
            num_uh=_int(f.get('num_uh')),
            num_uc=_int(f.get('num_uc')),
            total_dormitorios=_int(f.get('total_dormitorios')),
            pop_residencial=_int(f.get('pop_residencial')),
            pop_nao_residencial=_int(f.get('pop_nao_residencial')),
            pop_total=_int(f.get('pop_total')),
            vagas=_int(f.get('vagas')),
            padrao_impacto=f.get('padrao_impacto'),
        )
        db.session.add(emp)
        db.session.commit()
        flash('Processo cadastrado com sucesso.', 'success')
        return redirect(url_for('processos_detail', pid=p.id))

    return render_template('processos/form.html', processo=None, prop=None, emp=None,
                           zoneamentos=zoneamentos, situacoes=SITUACOES_PROCESSO,
                           usos=USOS, padroes=PADROES_IMPACTO, pessoas=pessoas)


@app.route('/processos/<int:pid>')
@login_required
def processos_detail(pid):
    p = Processo.query.get_or_404(pid)
    # Force eager loading of Obra and its SoloCriado to avoid lazy loading issues in template
    if p.empreendimento and p.empreendimento.obra:
        _ = p.empreendimento.obra.solos_criados_vinculados
    return render_template('processos/detail.html', processo=p)


@app.route('/processos/<int:pid>/editar', methods=['GET', 'POST'])
@login_required
@tecnico_required
def processos_editar(pid):
    p = Processo.query.get_or_404(pid)
    emp = p.empreendimento or Empreendimento(processo_id=pid)
    zoneamentos = Zoneamento.query.filter_by(ativo=True).order_by(Zoneamento.codigo).all()
    pessoas = Pessoa.query.order_by(Pessoa.nome).all()

    if request.method == 'POST':
        f = request.form
        # Validação de campos obrigatórios
        erros = []
        campos_obrigatorios = {
            'emp_nome': 'Nome do Empreendimento',
            'emp_padrao_empreendimento': 'Padrão do Empreendimento',
            'num_uc': 'Unidades Comerciais',
            'vagas': 'Nº de Vagas',
            'padrao_impacto': 'Padrão de Impacto',
            'total_dormitorios': 'Total de Dormitórios',
        }
        for campo, label in campos_obrigatorios.items():
            if not f.get(campo) or (campo in ['num_uc', 'vagas', 'total_dormitorios'] and f.get(campo) == ''):
                erros.append(f'{label} é obrigatório.')

        if erros:
            for erro in erros:
                flash(erro, 'danger')
            return redirect(url_for('processos_editar', pid=pid))

        p.num_processo = f.get('num_processo')
        p.protocolo_aprovacao = f.get('protocolo_aprovacao')
        p.data_entrada = _parse_date(f.get('data_entrada'))
        p.data_analise = _parse_date(f.get('data_analise'))
        p.situacao = f.get('situacao', p.situacao)
        p.observacoes = f.get('observacoes')

        # Remove vínculos existentes e reconstrói a partir do formulário
        ProcessoPessoa.query.filter_by(processo_id=pid).delete()
        db.session.flush()
        _salvar_pessoas_processo(pid, f)

        if not p.empreendimento:
            emp.processo_id = pid
            db.session.add(emp)
        emp.obra_id = _get_or_create_obra(f, current_user.id, existing_obra_id=emp.obra_id)
        zon_id = _int(f.get('zoneamento_id'))
        zon = Zoneamento.query.get(zon_id) if zon_id else None
        emp.nome = f.get('emp_nome')
        emp.cep = f.get('emp_cep')
        emp.endereco = f.get('emp_endereco')
        emp.bairro = f.get('emp_bairro')
        emp.inscricao = f.get('emp_inscricao')
        emp.matricula = f.get('emp_matricula')
        emp.zoneamento_id = zon_id
        emp.uso_predominante = f.get('emp_uso_predominante')
        emp.uso_secundario = f.get('emp_uso_secundario')
        emp.padrao_empreendimento = f.get('emp_padrao_empreendimento')
        emp.responsavel_tecnico = f.get('emp_responsavel_tecnico')
        emp.registro_profissional = f.get('emp_registro_profissional')
        emp.area_terreno = _float(f.get('area_terreno'))
        emp.area_construida = _float(f.get('area_construida'))
        emp.area_computavel = _float(f.get('area_computavel'))
        emp.cab = _float(f.get('cab')) or (zon.cab if zon else emp.cab)
        emp.cmax = _float(f.get('cmax')) or (zon.cmax if zon else emp.cmax)
        emp.num_pavimentos = _int(f.get('num_pavimentos'))
        emp.num_uh = _int(f.get('num_uh'))
        emp.num_uc = _int(f.get('num_uc'))
        emp.total_dormitorios = _int(f.get('total_dormitorios'))
        emp.pop_residencial = _int(f.get('pop_residencial'))
        emp.pop_nao_residencial = _int(f.get('pop_nao_residencial'))
        emp.pop_total = _int(f.get('pop_total'))
        emp.vagas = _int(f.get('vagas'))
        emp.padrao_impacto = f.get('padrao_impacto')
        p.atualizado_em = datetime.utcnow()
        db.session.commit()
        flash('Processo atualizado.', 'success')
        return redirect(url_for('processos_detail', pid=pid))

    return render_template('processos/form.html', processo=p, prop=None, emp=emp,
                           zoneamentos=zoneamentos, situacoes=SITUACOES_PROCESSO,
                           usos=USOS, padroes=PADROES_IMPACTO, pessoas=pessoas)


# ─── Impactos ────────────────────────────────────────────────────────────────

@app.route('/processos/<int:pid>/impactos', methods=['GET', 'POST'])
@login_required
@tecnico_required
def processos_impactos(pid):
    p = Processo.query.get_or_404(pid)
    if request.method == 'POST':
        f = request.form
        Impacto.query.filter_by(processo_id=pid).delete()
        for chave, descricao in IMPACTOS_SOCIAIS + IMPACTOS_VIARIOS:
            tipo = 'social' if (chave, descricao) in IMPACTOS_SOCIAIS else 'viario'
            imp = Impacto(
                processo_id=pid,
                tipo=tipo,
                chave=chave,
                descricao=descricao,
                classificacao=f.get(f'class_{chave}', 'Inexistente'),
                justificativa=f.get(f'just_{chave}'),
                medida_proposta=f.get(f'medida_{chave}'),
            )
            db.session.add(imp)
        if p.empreendimento:
            p.empreendimento.padrao_impacto = f.get('padrao_geral')
        db.session.commit()
        flash('Avaliação de impactos salva.', 'success')
        return redirect(url_for('processos_detail', pid=pid))

    imp_map = {i.chave: i for i in p.impactos}
    return render_template('processos/impactos.html', processo=p, imp_map=imp_map,
                           impactos_sociais=IMPACTOS_SOCIAIS,
                           impactos_viarios=IMPACTOS_VIARIOS,
                           classificacoes=CLASSIFICACOES_IMPACTO,
                           padroes=PADROES_IMPACTO)


# ─── Cálculos ────────────────────────────────────────────────────────────────

@app.route('/processos/<int:pid>/calculos', methods=['GET', 'POST'])
@login_required
@tecnico_required
def processos_calculos(pid):
    p = Processo.query.get_or_404(pid)
    emp = p.empreendimento
    cubs = CUB.query.order_by(CUB.ano.desc(), CUB.mes.desc()).all()
    params = {par.chave: par.valor_float for par in Parametro.query.all()}

    if request.method == 'POST':
        f = request.form
        errors = []
        cub_id = _int(f.get('cub_id'))
        cub_obj = CUB.query.get(cub_id) if cub_id else None
        if not cub_obj:
            errors.append('Selecione um CUB válido.')
        pop = _int(f.get('populacao'))
        if not pop or pop <= 0:
            errors.append('População total deve ser maior que zero.')

        nivel = f.get('nivel_selecionado', '')
        if not nivel:
            errors.append('Selecione o nível de compensação ou marque como dispensado.')
        if nivel == 'dispensado' and not f.get('justificativa_dispensa', '').strip():
            errors.append('A dispensa exige justificativa escrita.')

        zon = emp.zoneamento if emp else None

        # Solo Criado data is now read-only (calculated in solo criado module)
        # Set to 0 as these are no longer inputs in this form
        perc_on = 0
        perc_inf = 0
        perc_cap = 0
        area_on = 0
        area_inf = 0
        area_cap = 0

        if errors:
            for e in errors:
                flash(e, 'danger')
            return redirect(url_for('processos_calculos', pid=pid))

        # Solo Criado is no longer calculated here (only displayed as reference)
        ab = 0
        ae = 0
        vu = 0
        vo = 0
        vi = 0
        va = 0

        fc = params.get('fator_base_compensacao', 0.33)
        valor_base = pop * cub_obj.valor * fc
        nivel_pcts = {'dispensado': 0, '25': 0.25, '50': 0.50, '75': 0.75, '100': 1.00}
        valor_comp = valor_base * nivel_pcts.get(nivel, 0)

        calc = Calculo(
            processo_id=pid,
            cub_id=cub_obj.id,
            cub_valor=cub_obj.valor,
            cub_mes_ref=cub_obj.mes_ano_str,
            populacao=pop,
            fator_base=fc,
            nivel_selecionado=nivel,
            valor_compensacao=valor_comp,
            justificativa_dispensa=f.get('justificativa_dispensa'),
            area_basica=ab,
            area_excedente=ae,
            perc_oneroso=perc_on,
            area_onerosa=area_on,
            valor_oneroso=vo,
            perc_infra=perc_inf,
            area_infra=area_inf,
            valor_infra=vi,
            desc_infra=f.get('desc_infra'),
            loc_infra=f.get('loc_infra'),
            perc_captacao=perc_cap,
            area_captacao=area_cap,
            valor_captacao=va,
            desc_captacao=f.get('desc_captacao'),
            cap_reservatorio=_float(f.get('cap_reservatorio')),
            uso_agua=f.get('uso_agua'),
            padrao_impacto=f.get('padrao_impacto'),
            usuario_id=current_user.id,
        )
        db.session.add(calc)
        db.session.commit()
        flash('Cálculo realizado e salvo com sucesso.', 'success')
        return redirect(url_for('processos_detail', pid=pid))

    calc = p.ultimo_calculo
    return render_template('processos/calculos.html', processo=p, emp=emp,
                           cubs=cubs, calc=calc, params=params,
                           niveis=NIVEIS_COMPENSACAO, padroes=PADROES_IMPACTO)


# ─── Relatório ───────────────────────────────────────────────────────────────

@app.route('/processos/<int:pid>/relatorio', methods=['GET', 'POST'])
@login_required
def processos_relatorio(pid):
    p = Processo.query.get_or_404(pid)
    calc = p.ultimo_calculo
    integrantes = Integrante.query.filter_by(ativo=True).all()

    if request.method == 'POST' and current_user.is_tecnico:
        f = request.form
        numero = f.get('numero_relatorio') or _gerar_numero_relatorio(p)
        rel = Relatorio(
            processo_id=pid,
            numero=numero,
            data=_parse_date(f.get('data_relatorio')) or date.today(),
            versao=(p.ultimo_relatorio.versao + 1 if p.ultimo_relatorio else 1),
            usuario_id=current_user.id,
            deliberacao=f.get('deliberacao'),
            medidas=f.get('medidas'),
            obs_deliberacao=f.get('obs_deliberacao'),
        )
        db.session.add(rel)
        db.session.commit()
        flash('Relatório gerado com sucesso.', 'success')
        return redirect(url_for('processos_relatorio', pid=pid))

    rel = p.ultimo_relatorio
    # Force eager loading of Obra and its SoloCriado to avoid lazy loading issues in template
    if p.empreendimento and p.empreendimento.obra:
        _ = p.empreendimento.obra.solos_criados_vinculados

    # Filter impactos to show only valid ones (with description and not 'Inexistente')
    impactos_validos = [imp for imp in (p.impactos or [])
                        if imp.descricao and imp.classificacao != 'Inexistente']

    return render_template('processos/relatorio.html', processo=p, calc=calc,
                           rel=rel, integrantes=integrantes, impactos_validos=impactos_validos)


@app.route('/processos/<int:pid>/relatorio/pdf')
@login_required
def processos_relatorio_pdf(pid):
    p = Processo.query.get_or_404(pid)
    calc = p.ultimo_calculo
    rel = p.ultimo_relatorio
    integrantes = Integrante.query.filter_by(ativo=True).all()

    # Force eager loading of Obra and its SoloCriado to avoid lazy loading issues in template
    if p.empreendimento and p.empreendimento.obra:
        _ = p.empreendimento.obra.solos_criados_vinculados

    # Filter impactos to show only valid ones (with description and not 'Inexistente')
    impactos_validos = [imp for imp in (p.impactos or [])
                        if imp.descricao and imp.classificacao != 'Inexistente']

    # Load logo as base64
    import base64
    logo_path = os.path.join(app.static_folder, 'img', 'smpu_logo.jpg')
    logo_base64 = ''
    try:
        with open(logo_path, 'rb') as f:
            logo_base64 = base64.b64encode(f.read()).decode('utf-8')
    except (FileNotFoundError, IOError):
        pass

    html = render_template('relatorio/pdf.html', processo=p, calc=calc,
                           rel=rel, integrantes=integrantes, impactos_validos=impactos_validos,
                           data_emissao=date.today(), logo_base64=logo_base64)
    try:
        from xhtml2pdf import pisa
        buf = io.BytesIO()
        result = pisa.CreatePDF(html.encode('utf-8'), dest=buf, encoding='utf-8')

        if result.err:
            raise Exception(f'Erro ao gerar PDF: {result.err}')

        buf.seek(0)
        if buf.getbuffer().nbytes == 0:
            raise Exception('PDF gerado vazio')

        nome = f"CMAIU_{p.num_processo or p.id}.pdf".replace('/', '-')
        return send_file(buf, mimetype='application/pdf',
                         as_attachment=True, download_name=nome)
    except Exception as e:
        app.logger.error(f'Erro ao gerar PDF para processo {pid}: {str(e)}')
        flash(f'Erro ao gerar PDF: {str(e)}', 'danger')
        return redirect(url_for('processos_relatorio', pid=pid))


@app.route('/processos/<int:pid>/exportar-excel')
@login_required
def processos_exportar_excel(pid):
    p = Processo.query.get_or_404(pid)
    calc = p.ultimo_calculo
    emp = p.empreendimento
    prop = p.proprietario
    pessoas_proc = p.pessoas_vinculadas if p.pessoas_vinculadas else []
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Processo'

        def row(label, value):
            r = ws.max_row + 1
            ws.cell(r, 1, label).font = Font(bold=True)
            ws.cell(r, 2, value)

        row('Processo Administrativo', p.num_processo)
        row('Protocolo de Aprovação', p.protocolo_aprovacao)
        row('Situação', p.situacao)
        row('Data de Entrada', str(p.data_entrada or ''))
        nomes_prop = ', '.join(pv.pessoa.nome for pv in pessoas_proc) if pessoas_proc else (prop.nome if prop else '')
        row('Proprietário / Empreendedor', nomes_prop)
        row('Empreendimento', emp.nome if emp else '')
        row('Endereço', emp.endereco if emp else '')
        row('Bairro', emp.bairro if emp else '')
        row('Zoneamento', emp.zoneamento.codigo if emp and emp.zoneamento else '')
        row('Área do Terreno (m²)', emp.area_terreno if emp else '')
        row('Área Construída (m²)', emp.area_construida if emp else '')
        row('Área Computável (m²)', emp.area_computavel if emp else '')
        row('Unidades Habitacionais', emp.num_uh if emp else '')
        row('Unidades Comerciais', emp.num_uc if emp else '')
        row('População Total', emp.pop_total if emp else '')
        if calc:
            row('CUB Referência (R$/m²)', calc.cub_valor)
            row('Mês de Referência CUB', calc.cub_mes_ref)
            row('Valor-Base Compensação', calc.valor_base)
            row('Nível Selecionado', calc.nivel_label)
            row('Valor da Compensação (R$)', calc.valor_compensacao)
            row('Área Básica (m²)', calc.area_basica)
            row('Área Excedente (m²)', calc.area_excedente)
            row('Solo Oneroso – %', calc.perc_oneroso)
            row('Solo Oneroso – Área (m²)', calc.area_onerosa)
            row('Solo Oneroso – Valor (R$)', calc.valor_oneroso)
            row('Solo Infra – %', calc.perc_infra)
            row('Solo Infra – Área (m²)', calc.area_infra)
            row('Solo Infra – Valor (R$)', calc.valor_infra)
            row('Solo Captação – %', calc.perc_captacao)
            row('Solo Captação – Área (m²)', calc.area_captacao)
            row('Solo Captação – Valor (R$)', calc.valor_captacao)

        ws.column_dimensions['A'].width = 35
        ws.column_dimensions['B'].width = 30
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        nome = f"CMAIU_{p.num_processo or p.id}.xlsx".replace('/', '-')
        return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name=nome)
    except Exception as e:
        flash(f'Erro ao exportar Excel: {e}', 'danger')
        return redirect(url_for('processos_detail', pid=pid))


# ─── CUB ─────────────────────────────────────────────────────────────────────

@app.route('/cub')
@login_required
def cub_index():
    cubs = CUB.query.order_by(CUB.ano.desc(), CUB.mes.desc()).all()
    return render_template('cub/index.html', cubs=cubs)


@app.route('/cub/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def cub_novo():
    if request.method == 'POST':
        f = request.form
        c = CUB(
            mes=_int(f.get('mes')),
            ano=_int(f.get('ano')),
            valor=_float(f.get('valor')),
            categoria=f.get('categoria', 'R8-N (Residencial 8 pav. - Normal)'),
            fonte=f.get('fonte', 'SINDUSCON-SC'),
            data_publicacao=_parse_date(f.get('data_publicacao')),
            observacoes=f.get('observacoes'),
            usuario_id=current_user.id,
        )
        db.session.add(c)
        try:
            db.session.commit()
            flash('CUB cadastrado com sucesso.', 'success')
            return redirect(url_for('cub_index'))
        except Exception:
            db.session.rollback()
            flash('Já existe CUB cadastrado para esse mês/ano/categoria.', 'danger')
    return render_template('cub/form.html', cub=None, meses=MESES)


@app.route('/cub/<int:cid>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def cub_editar(cid):
    c = CUB.query.get_or_404(cid)
    if request.method == 'POST':
        f = request.form
        c.mes = _int(f.get('mes'))
        c.ano = _int(f.get('ano'))
        c.valor = _float(f.get('valor'))
        c.categoria = f.get('categoria')
        c.fonte = f.get('fonte')
        c.data_publicacao = _parse_date(f.get('data_publicacao'))
        c.observacoes = f.get('observacoes')
        db.session.commit()
        flash('CUB atualizado.', 'success')
        return redirect(url_for('cub_index'))
    return render_template('cub/form.html', cub=c, meses=MESES)


# ─── Zoneamentos ─────────────────────────────────────────────────────────────

@app.route('/zoneamentos')
@login_required
def zoneamentos_index():
    zoneamentos = Zoneamento.query.order_by(Zoneamento.codigo).all()
    return render_template('zoneamentos/index.html', zoneamentos=zoneamentos)


@app.route('/zoneamentos/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def zoneamentos_novo():
    if request.method == 'POST':
        f = request.form
        z = Zoneamento(
            codigo=f.get('codigo', '').strip().upper(),
            descricao=f.get('descricao'),
            cab=_float(f.get('cab')) or 1.0,
            cmax=_float(f.get('cmax')) or 4.0,
            permite_solo_criado=bool(f.get('permite_solo_criado')),
            limite_oneroso=_float(f.get('limite_oneroso')) or 40.0,
            limite_infra=_float(f.get('limite_infra')) or 5.0,
            limite_captacao=_float(f.get('limite_captacao')) or 5.0,
            norma=f.get('norma'),
            observacoes=f.get('observacoes'),
        )
        db.session.add(z)
        try:
            db.session.commit()
            flash('Zoneamento cadastrado.', 'success')
            return redirect(url_for('zoneamentos_index'))
        except Exception:
            db.session.rollback()
            flash('Código de zoneamento já existe.', 'danger')
    return render_template('zoneamentos/form.html', z=None)


@app.route('/zoneamentos/<int:zid>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def zoneamentos_editar(zid):
    z = Zoneamento.query.get_or_404(zid)
    if request.method == 'POST':
        f = request.form
        z.codigo = f.get('codigo', '').strip().upper()
        z.descricao = f.get('descricao')
        z.cab = _float(f.get('cab')) or z.cab
        z.cmax = _float(f.get('cmax')) or z.cmax
        z.permite_solo_criado = bool(f.get('permite_solo_criado'))
        z.limite_oneroso = _float(f.get('limite_oneroso')) or z.limite_oneroso
        z.limite_infra = _float(f.get('limite_infra')) or z.limite_infra
        z.limite_captacao = _float(f.get('limite_captacao')) or z.limite_captacao
        z.norma = f.get('norma')
        z.observacoes = f.get('observacoes')
        z.ativo = bool(f.get('ativo'))
        db.session.commit()
        flash('Zoneamento atualizado.', 'success')
        return redirect(url_for('zoneamentos_index'))
    return render_template('zoneamentos/form.html', z=z)


# ─── Admin – Usuários ─────────────────────────────────────────────────────────

@app.route('/admin/usuarios')
@login_required
@admin_required
def admin_usuarios():
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    return render_template('admin/usuarios.html', usuarios=usuarios)


@app.route('/admin/usuarios/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_usuarios_novo():
    if request.method == 'POST':
        f = request.form
        email = f.get('email', '').strip().lower()
        senha = f.get('senha', '').strip()

        if not email or not f.get('nome'):
            flash('Nome e e-mail são obrigatórios.', 'danger')
        elif Usuario.query.filter_by(email=email).first():
            flash('E-mail já cadastrado.', 'danger')
        elif not senha:
            flash('Senha é obrigatória.', 'danger')
        elif len(senha) < 8:
            flash('Senha deve ter no mínimo 8 caracteres.', 'danger')
        else:
            u = Usuario(nome=f.get('nome'), email=email,
                        perfil=f.get('perfil', 'consulta'))
            u.set_senha(senha)
            db.session.add(u)
            db.session.commit()
            flash('Usuário cadastrado com sucesso.', 'success')
            return redirect(url_for('admin_usuarios'))
    return render_template('admin/usuario_form.html', u=None)


@app.route('/admin/usuarios/<int:uid>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_usuarios_editar(uid):
    u = Usuario.query.get_or_404(uid)
    if request.method == 'POST':
        f = request.form
        u.nome = f.get('nome')
        u.perfil = f.get('perfil', u.perfil)
        u.situacao = f.get('situacao', u.situacao)
        nova_senha = f.get('senha', '').strip()
        if nova_senha:
            u.set_senha(nova_senha)
        db.session.commit()
        flash('Usuário atualizado.', 'success')
        return redirect(url_for('admin_usuarios'))
    return render_template('admin/usuario_form.html', u=u)


# ─── Admin – Parâmetros ───────────────────────────────────────────────────────

@app.route('/admin/parametros', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_parametros():
    params = Parametro.query.all()
    if request.method == 'POST':
        f = request.form
        just = f.get('justificativa', '').strip()
        if not just:
            flash('Informe a justificativa para alterar parâmetros.', 'danger')
            return redirect(url_for('admin_parametros'))
        for p in params:
            novo_val = f.get(p.chave, '').strip()
            if novo_val and novo_val != p.valor:
                h = HistoricoParametro(
                    parametro_id=p.id,
                    valor_anterior=p.valor,
                    valor_novo=novo_val,
                    usuario_id=current_user.id,
                    justificativa=just,
                )
                db.session.add(h)
                p.valor = novo_val
        db.session.commit()
        flash('Parâmetros atualizados.', 'success')
        return redirect(url_for('admin_parametros'))
    historico = HistoricoParametro.query.order_by(HistoricoParametro.data_alteracao.desc()).limit(20).all()
    return render_template('admin/parametros.html', params=params, historico=historico)


# ─── Admin – Integrantes ──────────────────────────────────────────────────────

@app.route('/admin/integrantes', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_integrantes():
    if request.method == 'POST':
        f = request.form
        action = f.get('action')
        if action == 'add':
            i = Integrante(nome=f.get('nome'), cargo=f.get('cargo'), orgao=f.get('orgao'))
            db.session.add(i)
        elif action == 'toggle':
            i = Integrante.query.get(_int(f.get('id')))
            if i:
                i.ativo = not i.ativo
        elif action == 'delete':
            i = Integrante.query.get(_int(f.get('id')))
            if i:
                db.session.delete(i)
        db.session.commit()
        flash('Integrantes atualizados.', 'success')
        return redirect(url_for('admin_integrantes'))
    integrantes = Integrante.query.order_by(Integrante.nome).all()
    return render_template('admin/integrantes.html', integrantes=integrantes)


# ─── API ─────────────────────────────────────────────────────────────────────

@app.route('/api/cub/<int:cid>')
@login_required
def api_cub(cid):
    c = CUB.query.get_or_404(cid)
    return jsonify({'valor': c.valor, 'mes_ano': c.mes_ano_str,
                    'categoria': c.categoria})


@app.route('/api/cep/<cep>')
@login_required
def api_cep(cep):
    """Proxy para ViaCEP — evita bloqueios CORS no browser."""
    import re, urllib.request, urllib.error
    limpo = re.sub(r'\D', '', cep)
    if len(limpo) != 8:
        return jsonify({'erro': True, 'msg': 'CEP inválido'}), 400
    try:
        url = f'https://viacep.com.br/ws/{limpo}/json/'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            import json as _json
            data = _json.loads(resp.read().decode('utf-8'))
        return jsonify(data)
    except Exception as e:
        return jsonify({'erro': True, 'msg': str(e)}), 502


@app.route('/api/zoneamento/<int:zid>')
@login_required
def api_zoneamento(zid):
    z = Zoneamento.query.get_or_404(zid)
    return jsonify({'cab': z.cab, 'cmax': z.cmax,
                    'permite_solo_criado': z.permite_solo_criado,
                    'limite_oneroso': z.limite_oneroso,
                    'limite_infra': z.limite_infra,
                    'limite_captacao': z.limite_captacao})


# ─── Erros ───────────────────────────────────────────────────────────────────

@app.errorhandler(403)
def e403(e):
    return render_template('erro.html', codigo=403,
                           msg='Acesso não autorizado.'), 403


@app.errorhandler(404)
def e404(e):
    return render_template('erro.html', codigo=404,
                           msg='Página não encontrada.'), 404


# ─── Utilitários ─────────────────────────────────────────────────────────────

def _parse_date(s):
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None


def _float(v):
    if v is None:
        return None
    try:
        return float(str(v).replace(',', '.'))
    except Exception:
        return None


def _int(v):
    if v is None:
        return None
    try:
        return int(str(v).strip())
    except Exception:
        return None


def _gerar_numero_relatorio(processo):
    ano = date.today().year
    count = Relatorio.query.filter(
        db.extract('year', Relatorio.emitido_em) == ano
    ).count() + 1
    return f"CMAIU-{ano}-{count:04d}"


# ─── Init ────────────────────────────────────────────────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        if not Usuario.query.first():
            admin = Usuario(nome='Administrador', email='admin@cmaiu.palhoca.sc.gov.br',
                            perfil='administrador')
            # Gerar senha temporária segura
            senha_temporaria = _gerar_senha_temporaria()
            admin.set_senha(senha_temporaria)
            db.session.add(admin)
            print(f"\n{'='*70}")
            print(f"✓ Banco de dados inicializado")
            print(f"{'='*70}")
            print(f"Admin criado: admin@cmaiu.palhoca.sc.gov.br")
            print(f"Senha temporária: {senha_temporaria}")
            print(f"⚠️  ALTERE ESTA SENHA NO PRIMEIRO LOGIN!")
            print(f"{'='*70}\n")

        if not Parametro.query.first():
            for chave, desc, valor, unidade in PARAMS_INICIAIS:
                db.session.add(Parametro(chave=chave, descricao=desc,
                                         valor=valor, unidade=unidade))

        if not Zoneamento.query.first():
            zons = [
                ('AMC-7', 'Área Mista Central 7', 4.0, 6.0, True, 40, 5, 5),
                ('ZR-2', 'Zona Residencial 2', 2.0, 4.0, True, 40, 5, 5),
                ('ZR-3', 'Zona Residencial 3', 2.5, 5.0, True, 40, 5, 5),
                ('ZC-1', 'Zona Comercial 1', 3.0, 6.0, True, 40, 5, 5),
                ('ZI',   'Zona Industrial', 1.5, 2.0, False, 0, 0, 0),
            ]
            for cod, desc, cab, cmax, psc, lo, li, lc in zons:
                db.session.add(Zoneamento(
                    codigo=cod, descricao=desc, cab=cab, cmax=cmax,
                    permite_solo_criado=psc, limite_oneroso=lo,
                    limite_infra=li, limite_captacao=lc,
                    norma='Lei Municipal de Zoneamento'))

        if not CUB.query.first():
            dados_cub = [
                (1, 2025, 3012.64), (2, 2025, 3019.26), (3, 2025, 3028.45),
                (4, 2025, 3037.72), (5, 2025, 3048.90), (6, 2025, 3061.15),
            ]
            for mes, ano, valor in dados_cub:
                db.session.add(CUB(mes=mes, ano=ano, valor=valor,
                                   categoria='R8-N (Residencial 8 pav. - Normal)',
                                   fonte='SINDUSCON-SC'))

        db.session.commit()
        _importar_planilha_existente()


def _importar_planilha_existente():
    """Importa os dados da planilha original se existir e o banco estiver vazio."""
    if Processo.query.count() > 0:
        return
    xlsx_path = os.path.join(os.path.dirname(__file__),
                              'banco_cmaiu.xlsx')
    upload_path = '/root/.claude/uploads/7fb32126-5b03-5692-b37a-3453fd67a6c3/dd0885bf-CMAIU.xlsx'
    path = upload_path if os.path.exists(upload_path) else (xlsx_path if os.path.exists(xlsx_path) else None)
    if not path:
        return
    try:
        import openpyxl as xl
        wb = xl.load_workbook(path, read_only=True, data_only=True)
        ws3 = wb['Planilha3']
        ws2 = wb['Planilha2']

        # Importar CUBs adicionais
        for row in ws2.iter_rows(min_row=2, max_col=2, values_only=True):
            if row[0] and row[1]:
                dt = row[0]
                if hasattr(dt, 'month'):
                    if not CUB.query.filter_by(mes=dt.month, ano=dt.year,
                                               categoria='R8-N (Residencial 8 pav. - Normal)').first():
                        db.session.add(CUB(mes=dt.month, ano=dt.year, valor=float(row[1]),
                                           categoria='R8-N (Residencial 8 pav. - Normal)',
                                           fonte='SINDUSCON-SC'))

        admin_user = Usuario.query.first()
        for row in ws3.iter_rows(min_row=2, max_col=27, values_only=True):
            if not row[0]:
                continue
            proprietario = str(row[0]) if row[0] else ''
            nome_emp = str(row[1]) if row[1] else ''
            data_entrada = row[2].date() if hasattr(row[2], 'date') else None
            prot_cmaiu = str(row[3]) if row[3] else ''
            prot_aprov = str(row[4]) if row[4] else ''
            bairro = str(row[5]) if row[5] else ''
            padrao = str(row[6]) if row[6] else ''
            zona_cod = str(row[7]) if row[7] else ''
            area_construida = _parse_area(row[8])
            num_uh = _safe_int(row[9])
            num_uc = _safe_int(row[10])
            populacao = _safe_int(row[11])
            area_terreno = _parse_area(row[12])

            p = Processo(num_processo='', protocolo_cmaiu=prot_cmaiu,
                         protocolo_aprovacao=prot_aprov, data_entrada=data_entrada,
                         situacao='Em análise', criado_por=admin_user.id if admin_user else None)
            db.session.add(p)
            db.session.flush()

            db.session.add(Proprietario(processo_id=p.id, nome=proprietario))

            zon = Zoneamento.query.filter_by(codigo=zona_cod).first()
            emp = Empreendimento(
                processo_id=p.id, nome=nome_emp, bairro=bairro,
                zoneamento_id=zon.id if zon else None,
                area_terreno=area_terreno, area_construida=area_construida,
                num_uh=num_uh, num_uc=num_uc, pop_total=populacao,
                padrao_impacto=padrao,
            )
            db.session.add(emp)

            # Importar cálculo se houver valor de compensação
            v25 = _safe_float(row[23])
            if v25 and v25 > 0:
                perc_on = _safe_float(row[13]) or 0
                area_on = _parse_area(row[14]) or 0
                val_on = _safe_float(row[15]) or 0
                perc_inf = _safe_float(row[17]) or 0
                area_inf = _parse_area(row[18]) or 0
                val_inf = _safe_float(row[19]) or 0
                perc_cap = _safe_float(row[20]) or 0
                area_cap = _parse_area(row[21]) or 0
                val_cap = _safe_float(row[22]) or 0
                v50 = _safe_float(row[24]) or 0
                v75 = _safe_float(row[25]) or 0
                v100 = _safe_float(row[26]) or 0
                pop = populacao or 0
                cub_val = (v100 / (pop * 0.33)) if pop > 0 and v100 else 3012.64
                calc = Calculo(
                    processo_id=p.id,
                    cub_valor=round(cub_val, 2),
                    cub_mes_ref='Import',
                    populacao=pop,
                    fator_base=0.33,
                    nivel_selecionado=None,
                    valor_compensacao=0,
                    area_basica=(area_terreno or 0) * (zon.cab if zon else 4),
                    perc_oneroso=perc_on * 100 if perc_on <= 1 else perc_on,
                    area_onerosa=area_on,
                    valor_oneroso=val_on,
                    perc_infra=perc_inf * 100 if perc_inf <= 1 else perc_inf,
                    area_infra=area_inf,
                    valor_infra=val_inf,
                    perc_captacao=perc_cap * 100 if perc_cap <= 1 else perc_cap,
                    area_captacao=area_cap,
                    valor_captacao=val_cap,
                    usuario_id=admin_user.id if admin_user else None,
                )
                db.session.add(calc)

        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        print(f'Aviso: importação da planilha falhou: {ex}')


def _parse_area(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace('m²', '').replace(' ', '').replace('.', '').replace(',', '.')
    try:
        return float(s)
    except Exception:
        return None


def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


def _safe_int(v):
    try:
        return int(v)
    except Exception:
        return None


# ─── Cadastro de Pessoas ─────────────────────────────────────────────────────

@app.route('/pessoas')
@login_required
def pessoas_index():
    q = request.args.get('q', '').strip()
    query = Pessoa.query.order_by(Pessoa.nome)
    if q:
        query = query.filter(
            db.or_(Pessoa.nome.ilike(f'%{q}%'), Pessoa.cpf_cnpj.ilike(f'%{q}%'))
        )
    pessoas = query.all()
    # Build a map of cpf_cnpj → legacy process count from Proprietario table
    from sqlalchemy import func
    legacy_counts = {
        row.cpf_cnpj: row.cnt
        for row in db.session.query(Proprietario.cpf_cnpj, func.count(Proprietario.id).label('cnt'))
            .filter(Proprietario.cpf_cnpj.isnot(None), Proprietario.cpf_cnpj != '')
            .group_by(Proprietario.cpf_cnpj).all()
    }
    for p in pessoas:
        join_count = len(p.vinculos_processo)
        legacy = legacy_counts.get(p.cpf_cnpj, 0) if p.cpf_cnpj else 0
        p._processos_count = join_count + legacy
        p._sc_count = len(p.solos_criados)
    return render_template('pessoas/index.html', pessoas=pessoas, q=q)


@app.route('/pessoas/nova', methods=['GET', 'POST'])
@login_required
@tecnico_required
def pessoas_nova():
    if request.method == 'POST':
        f = request.form
        p = Pessoa(
            nome=f.get('nome', '').strip(),
            cpf_cnpj=f.get('cpf_cnpj', '').strip(),
            tipo=f.get('tipo', 'Pessoa Física'),
            cep=f.get('cep', '').strip(),
            endereco=f.get('endereco', '').strip(),
            numero=f.get('numero', '').strip(),
            complemento=f.get('complemento', '').strip(),
            bairro=f.get('bairro', '').strip(),
            cidade=f.get('cidade', '').strip(),
            estado=f.get('estado', '').strip(),
            telefone=f.get('telefone', '').strip(),
            email=f.get('email', '').strip(),
            observacoes=f.get('observacoes', '').strip(),
        )
        db.session.add(p)
        db.session.commit()
        flash('Pessoa cadastrada com sucesso.', 'success')
        next_url = request.args.get('next')
        if next_url:
            return redirect(next_url)
        return redirect(url_for('pessoas_index'))
    return render_template('pessoas/form.html', pessoa=None)


@app.route('/pessoas/<int:pid>/editar', methods=['GET', 'POST'])
@login_required
@tecnico_required
def pessoas_editar(pid):
    p = Pessoa.query.get_or_404(pid)
    if request.method == 'POST':
        f = request.form
        p.nome        = f.get('nome', '').strip()
        p.cpf_cnpj    = f.get('cpf_cnpj', '').strip()
        p.tipo        = f.get('tipo', p.tipo)
        p.cep         = f.get('cep', '').strip()
        p.endereco    = f.get('endereco', '').strip()
        p.numero      = f.get('numero', '').strip()
        p.complemento = f.get('complemento', '').strip()
        p.bairro      = f.get('bairro', '').strip()
        p.cidade      = f.get('cidade', '').strip()
        p.estado      = f.get('estado', '').strip()
        p.telefone    = f.get('telefone', '').strip()
        p.email       = f.get('email', '').strip()
        p.observacoes = f.get('observacoes', '').strip()
        db.session.commit()
        flash('Dados atualizados.', 'success')
        return redirect(url_for('pessoas_index'))
    return render_template('pessoas/form.html', pessoa=p)


@app.route('/pessoas/<int:pid>/excluir', methods=['POST'])
@login_required
@tecnico_required
def pessoas_excluir(pid):
    p = Pessoa.query.get_or_404(pid)
    if p.vinculos_processo or p.vinculos_tac:
        flash('Não é possível excluir: pessoa vinculada a processos ou TACs.', 'danger')
        return redirect(url_for('pessoas_index'))
    db.session.delete(p)
    db.session.commit()
    flash('Pessoa excluída.', 'success')
    return redirect(url_for('pessoas_index'))


@app.route('/api/pessoas/buscar')
@login_required
def api_pessoas_buscar():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return {'results': []}
    pessoas = Pessoa.query.filter(
        db.or_(Pessoa.nome.ilike(f'%{q}%'), Pessoa.cpf_cnpj.ilike(f'%{q}%'))
    ).order_by(Pessoa.nome).limit(10).all()
    return {'results': [{'id': p.id, 'text': f'{p.nome} ({p.doc_formatado})', 'nome': p.nome,
                         'cpf_cnpj': p.cpf_cnpj or '', 'endereco': p.endereco or '',
                         'telefone': p.telefone or '', 'email': p.email or '',
                         'tipo': p.tipo} for p in pessoas]}


@app.route('/api/pessoas/lista')
@login_required
def api_pessoas_lista():
    pessoas = Pessoa.query.order_by(Pessoa.nome).all()
    return jsonify([{'id': p.id, 'nome': p.nome} for p in pessoas])


@app.route('/api/cubs/lista')
@login_required
def api_cubs_lista():
    cubs = CUB.query.order_by(CUB.ano.desc(), CUB.mes.desc()).all()
    return jsonify([{'id': c.id, 'label': f'{c.mes_ano_str} – R$ {c.valor:,.2f}/m²'} for c in cubs])


# ─── TAC – Vínculos de Pessoas ────────────────────────────────────────────────

@app.route('/tac/<int:tid>/pessoas', methods=['GET', 'POST'])
@login_required
@tecnico_required
def tac_pessoas(tid):
    tac = TAC.query.get_or_404(tid)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'vincular':
            pessoa_id = _int(request.form.get('pessoa_id'))
            papel     = request.form.get('papel', 'Compromissário')
            if pessoa_id and not TACPessoa.query.filter_by(tac_id=tid, pessoa_id=pessoa_id).first():
                db.session.add(TACPessoa(tac_id=tid, pessoa_id=pessoa_id, papel=papel))
                db.session.commit()
                flash('Pessoa vinculada ao TAC.', 'success')
            else:
                flash('Pessoa já vinculada ou não encontrada.', 'warning')
        elif action == 'desvincular':
            vid = _int(request.form.get('vinculo_id'))
            v = TACPessoa.query.get(vid)
            if v and v.tac_id == tid:
                db.session.delete(v)
                db.session.commit()
                flash('Vínculo removido.', 'success')
        elif action == 'alterar_papel':
            vid = _int(request.form.get('vinculo_id'))
            v = TACPessoa.query.get(vid)
            if v and v.tac_id == tid:
                v.papel = request.form.get('papel', v.papel)
                db.session.commit()
                flash('Papel atualizado.', 'success')
        return redirect(url_for('tac_pessoas', tid=tid))
    return render_template('tac/pessoas.html', tac=tac, papeis=PAPEIS_TAC)


# ─── Processo – Vínculos de Pessoas ──────────────────────────────────────────

@app.route('/processos/<int:pid>/pessoas', methods=['GET', 'POST'])
@login_required
@tecnico_required
def processo_pessoas(pid):
    p = Processo.query.get_or_404(pid)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'vincular':
            pessoa_id = _int(request.form.get('pessoa_id'))
            papel     = request.form.get('papel', 'Proprietário')
            if pessoa_id and not ProcessoPessoa.query.filter_by(processo_id=pid, pessoa_id=pessoa_id).first():
                db.session.add(ProcessoPessoa(processo_id=pid, pessoa_id=pessoa_id, papel=papel))
                db.session.commit()
                flash('Pessoa vinculada ao processo.', 'success')
            else:
                flash('Pessoa já vinculada ou não encontrada.', 'warning')
        elif action == 'desvincular':
            vid = _int(request.form.get('vinculo_id'))
            v = ProcessoPessoa.query.get(vid)
            if v and v.processo_id == pid:
                db.session.delete(v)
                db.session.commit()
                flash('Vínculo removido.', 'success')
        elif action == 'alterar_papel':
            vid = _int(request.form.get('vinculo_id'))
            v = ProcessoPessoa.query.get(vid)
            if v and v.processo_id == pid:
                v.papel = request.form.get('papel', v.papel)
                db.session.commit()
                flash('Papel atualizado.', 'success')
        return redirect(url_for('processo_pessoas', pid=pid))
    return render_template('processos/pessoas.html', processo=p, papeis=PAPEIS_PROCESSO)


# ─── API – Obras unificadas ──────────────────────────────────────────────────

@app.route('/api/obras/buscar')
@login_required
def api_obras_buscar():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    obras = Obra.query.filter(
        db.or_(
            Obra.nome.ilike(f'%{q}%'),
            Obra.endereco.ilike(f'%{q}%'),
            Obra.inscricao_imobiliaria.ilike(f'%{q}%'),
            Obra.bairro.ilike(f'%{q}%'),
        )
    ).order_by(Obra.nome).limit(10).all()
    return jsonify([{
        'id': o.id,
        'nome': o.nome or '',
        'cep': o.cep or '',
        'endereco': o.endereco or '',
        'numero': o.numero or '',
        'complemento': o.complemento or '',
        'bairro': o.bairro or '',
        'cidade': o.cidade or '',
        'inscricao_imobiliaria': o.inscricao_imobiliaria or '',
        'matricula': o.matricula or '',
        'zoneamento_id': o.zoneamento_id or '',
        'zoneamento_codigo': o.zoneamento.codigo if o.zoneamento else '',
        'area_terreno': o.area_terreno or '',
        'area_construida': o.area_construida or '',
        'num_pavimentos': o.num_pavimentos or '',
        'label': o.label,
        'proprietario_id': o.proprietario_id or '',
        'proprietario_nome': o.proprietario.nome if o.proprietario else '',
        'proprietario_cpf_cnpj': o.proprietario.cpf_cnpj if o.proprietario else '',
        'proprietario_telefone': o.proprietario.telefone if o.proprietario else '',
        'proprietario_email': o.proprietario.email if o.proprietario else '',
    } for o in obras])


@app.route('/api/pessoas/<int:pessoa_id>/obras')
@login_required
def api_pessoas_obras(pessoa_id):
    """Retorna obras vinculadas a um proprietário"""
    obras = Obra.query.filter_by(proprietario_id=pessoa_id).order_by(Obra.nome).all()
    return jsonify([{
        'id': o.id,
        'nome': o.nome or '',
        'inscricao_imobiliaria': o.inscricao_imobiliaria or '',
        'endereco': o.endereco or '',
        'bairro': o.bairro or '',
        'label': o.label,
    } for o in obras])


@app.route('/api/obras/<int:obra_id>')
@login_required
def api_obra_detalhes(obra_id):
    """Retorna dados completos de uma obra específica"""
    obra = Obra.query.get(obra_id)
    if not obra:
        return jsonify({'error': 'Obra não encontrada'}), 404
    return jsonify({
        'id': obra.id,
        'nome': obra.nome or '',
        'cep': obra.cep or '',
        'endereco': obra.endereco or '',
        'numero': obra.numero or '',
        'complemento': obra.complemento or '',
        'bairro': obra.bairro or '',
        'cidade': obra.cidade or '',
        'inscricao_imobiliaria': obra.inscricao_imobiliaria or '',
        'matricula': obra.matricula or '',
        'zoneamento_id': obra.zoneamento_id or '',
        'zoneamento_codigo': obra.zoneamento.codigo if obra.zoneamento else '',
        'area_terreno': obra.area_terreno or '',
        'area_construida': obra.area_construida or '',
        'num_pavimentos': obra.num_pavimentos or '',
        'label': obra.label,
        'proprietario_id': obra.proprietario_id or '',
        'proprietario_nome': obra.proprietario.nome if obra.proprietario else '',
        'proprietario_cpf_cnpj': obra.proprietario.cpf_cnpj if obra.proprietario else '',
        'proprietario_telefone': obra.proprietario.telefone if obra.proprietario else '',
        'proprietario_email': obra.proprietario.email if obra.proprietario else '',
    })


@app.route('/api/obras/<int:obra_id>/solo-criado')
@login_required
def api_obra_solo_criado(obra_id):
    """Retorna dados de outorga onerosa do registro de Solo Criado associado à obra, se existir"""
    sc = SoloCriado.query.filter_by(obra_id=obra_id).first()
    if not sc:
        return jsonify(None), 200
    return jsonify({
        'id': sc.id,
        'numero': sc.numero or '',
        # Outorga Onerosa (Pagamento ao Município)
        'pon': sc.pon or 0,
        'aon': sc.aon or 0,
        'von': sc.von or 0,
        # Infraestrutura (Investimento em bem público)
        'pin': sc.pin or 0,
        'ain': sc.ain or 0,
        'vin': sc.vin or 0,
        # Águas Pluviais (Investimento no empreendimento)
        'pag': sc.pag or 0,
        'aag': sc.aag or 0,
        'vag': sc.vag or 0,
    })


def _get_or_create_obra(f, criado_por, existing_obra_id=None):
    """Retorna obra_id sem criar duplicatas.

    Prioridade:
    1. Seleção explícita pelo widget de busca (campo obra_id no form).
    2. Vínculo já existente no registro — preserva sem alterar.
    3. Busca por inscrição imobiliária — reutiliza se já cadastrada.
    4. Cria nova obra somente se não há vínculo prévio e há dados suficientes.
    """
    # 1. Usuário selecionou obra pelo widget
    oid = _int(f.get('obra_id'))
    if oid:
        return oid

    # 2. Registro já vinculado — não cria duplicata ao editar
    if existing_obra_id:
        return existing_obra_id

    # 3. Busca por inscrição imobiliária (todos os nomes possíveis por módulo)
    inscricao = (
        f.get('emp_inscricao') or f.get('inscricao') or
        f.get('inscricao_imobiliaria') or f.get('inscricao_imob') or ''
    ).strip()
    if inscricao:
        existing = Obra.query.filter_by(inscricao_imobiliaria=inscricao).first()
        if existing:
            return existing.id

    # 4. Cria nova obra somente se há dados mínimos de identificação
    nome     = (f.get('emp_nome') or f.get('descricao') or f.get('nome_empreendimento') or '').strip()
    endereco = (f.get('emp_endereco') or f.get('endereco') or f.get('endereco_imovel') or '').strip()
    if not inscricao and not nome and not endereco:
        return None
    o = Obra(
        nome=nome,
        cep=f.get('emp_cep') or f.get('cep_imovel') or '',
        endereco=endereco,
        numero=f.get('numero_imovel') or '',
        complemento=f.get('complemento_imovel') or '',
        bairro=f.get('emp_bairro') or f.get('bairro') or f.get('bairro_imovel') or '',
        cidade=f.get('cidade_imovel') or '',
        inscricao_imobiliaria=inscricao,
        matricula=f.get('emp_matricula') or f.get('matricula') or '',
        zoneamento_id=_int(f.get('zoneamento_id')),
        area_terreno=_float(f.get('area_terreno')),
        area_construida=_float(f.get('area_construida') or f.get('area_construida_total')),
        num_pavimentos=_int(f.get('num_pavimentos')),
        criado_por=criado_por,
    )
    db.session.add(o)
    db.session.flush()
    return o.id


# ─── TAC – Termo de Ajustamento de Conduta ───────────────────────────────────

@app.route('/tac')
@login_required
def tac_index():
    q   = request.args.get('q', '').strip()
    qp  = request.args.get('qp', '').strip()
    sit = request.args.get('situacao', '')
    qs  = TAC.query.order_by(TAC.criado_em.desc())
    if q:
        qs = qs.filter(db.or_(
            TAC.num_processo_adm.ilike(f'%{q}%'),
            TAC.numero.ilike(f'%{q}%'),
        ))
    if qp:
        qs = qs.join(TAC.pessoas_vinculadas).join(TACPessoa.pessoa).filter(
            Pessoa.nome.ilike(f'%{qp}%')
        ).distinct()
    if sit:
        qs = qs.filter(TAC.situacao == sit)
    tacs = qs.all()
    situacoes_tac = ['Rascunho','Em análise','Cálculo concluído',
                     'Aguardando parecer jurídico','Pronto para assinatura',
                     'Assinado','Publicado','Cancelado']
    ano_atual = date.today().year
    tacs_ano  = [t for t in tacs if t.criado_em and t.criado_em.year == ano_atual]
    totais_ano = {
        'vtot': sum(t.calculo.vf_total for t in tacs_ano if t.calculo),
        'qtd':  len(tacs_ano),
        'ano':  ano_atual,
    }
    return render_template('tac/index.html', tacs=tacs, q=q, qp=qp, sit=sit,
                           situacoes=situacoes_tac, totais_ano=totais_ano)


@app.route('/tac/novo', methods=['GET', 'POST'])
@login_required
@tecnico_required
def tac_novo():
    cubs = CUB.query.order_by(CUB.ano.desc(), CUB.mes.desc()).all()
    if request.method == 'POST':
        f = request.form
        tac = TAC(
            numero=f.get('numero', '').strip() or None,
            num_processo_adm=f.get('num_processo_adm', '').strip(),
            data_abertura=_parse_date(f.get('data_abertura')) or date.today(),
            cub_id=_int(f.get('cub_id')) or None,
            observacoes=f.get('observacoes', '').strip(),
            criado_por=current_user.id,
        )
        db.session.add(tac)
        db.session.commit()
        flash('TAC criado. Cadastre os compromissários e obras.', 'success')
        return redirect(url_for('tac_detail', tid=tac.id))
    from datetime import date as _date
    return render_template('tac/form.html', tac=None, cubs=cubs, today=_date.today().isoformat())


@app.route('/tac/<int:tid>')
@login_required
def tac_detail(tid):
    tac = TAC.query.get_or_404(tid)
    return render_template('tac/detail.html', tac=tac)


@app.route('/tac/<int:tid>/editar', methods=['GET', 'POST'])
@login_required
@tecnico_required
def tac_editar(tid):
    tac = TAC.query.get_or_404(tid)
    if tac.bloqueado:
        flash('TAC assinado/publicado não pode ser editado. Crie uma nova versão.', 'danger')
        return redirect(url_for('tac_detail', tid=tid))
    cubs = CUB.query.order_by(CUB.ano.desc(), CUB.mes.desc()).all()
    if request.method == 'POST':
        f = request.form
        tac.numero = f.get('numero', '').strip() or tac.numero
        tac.num_processo_adm = f.get('num_processo_adm', '').strip()
        tac.data_abertura = _parse_date(f.get('data_abertura')) or tac.data_abertura
        tac.data_assinatura = _parse_date(f.get('data_assinatura'))
        tac.data_publicacao = _parse_date(f.get('data_publicacao'))
        tac.cub_id = _int(f.get('cub_id')) or tac.cub_id
        tac.situacao = f.get('situacao', tac.situacao)
        tac.observacoes = f.get('observacoes', '').strip()
        db.session.commit()
        flash('TAC atualizado.', 'success')
        return redirect(url_for('tac_detail', tid=tid))
    from datetime import date as _date
    return render_template('tac/form.html', tac=tac, cubs=cubs, today=_date.today().isoformat())


@app.route('/tac/<int:tid>/compromissarios', methods=['GET', 'POST'])
@login_required
@tecnico_required
def tac_compromissarios(tid):
    tac = TAC.query.get_or_404(tid)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add' and not tac.bloqueado:
            f = request.form
            c = CompromissarioTAC(
                tac_id=tid,
                nome=f.get('nome', '').strip(),
                cpf_cnpj=f.get('cpf_cnpj', '').strip(),
                endereco=f.get('endereco', '').strip(),
                telefone=f.get('telefone', '').strip(),
                email=f.get('email', '').strip(),
                tipo=f.get('tipo', 'Proprietário'),
            )
            db.session.add(c)
            db.session.commit()
            flash('Compromissário adicionado.', 'success')
        elif action == 'delete' and not tac.bloqueado:
            cid = _int(request.form.get('id'))
            c = CompromissarioTAC.query.get(cid)
            if c and c.tac_id == tid:
                db.session.delete(c)
                db.session.commit()
        return redirect(url_for('tac_compromissarios', tid=tid))
    return render_template('tac/compromissarios.html', tac=tac)


@app.route('/tac/<int:tid>/obras', methods=['GET', 'POST'])
@login_required
@tecnico_required
def tac_obras(tid):
    tac = TAC.query.get_or_404(tid)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add' and not tac.bloqueado:
            f = request.form
            obra = ObraTAC(
                tac_id=tid,
                obra_id=_get_or_create_obra(f, current_user.id),
                descricao=f.get('descricao', '').strip(),
                endereco=f.get('endereco', '').strip(),
                bairro=f.get('bairro', '').strip(),
                inscricao_imobiliaria=f.get('inscricao', '').strip(),
                grupo=f.get('grupo', 'G1'),
                area_construida=_float(f.get('area_construida')) or 0.0,
                is_unifamiliar_ate150=bool(f.get('is_unifamiliar_ate150')),
                data_construcao=_parse_date(f.get('data_construcao')),
                observacoes=f.get('observacoes', '').strip(),
            )
            db.session.add(obra)
            db.session.flush()
            # Auto-link obra's proprietário as compromissário if not already linked
            if obra.obra_id:
                obra_obj = Obra.query.get(obra.obra_id)
                if obra_obj and obra_obj.proprietario_id:
                    pid = obra_obj.proprietario_id
                    if not TACPessoa.query.filter_by(tac_id=tid, pessoa_id=pid).first():
                        db.session.add(TACPessoa(tac_id=tid, pessoa_id=pid, papel='Compromissário'))
            db.session.commit()
            flash('Obra adicionada.', 'success')
        elif action == 'edit':
            oid = _int(request.form.get('id'))
            o = ObraTAC.query.get(oid)
            if o and o.tac_id == tid:
                f = request.form
                o.obra_id = _get_or_create_obra(f, current_user.id, existing_obra_id=o.obra_id)
                o.descricao = f.get('descricao', '').strip()
                o.endereco = f.get('endereco', '').strip()
                o.bairro = f.get('bairro', '').strip()
                o.inscricao_imobiliaria = f.get('inscricao', '').strip()
                o.grupo = f.get('grupo', o.grupo)
                o.area_construida = _float(f.get('area_construida')) or o.area_construida
                o.is_unifamiliar_ate150 = bool(f.get('is_unifamiliar_ate150'))
                o.data_construcao = _parse_date(f.get('data_construcao'))
                o.observacoes = f.get('observacoes', '').strip()
                db.session.commit()
                flash('Obra atualizada.', 'success')
        elif action == 'delete' and not tac.bloqueado:
            oid = _int(request.form.get('id'))
            o = ObraTAC.query.get(oid)
            if o and o.tac_id == tid:
                db.session.delete(o)
                db.session.commit()
        return redirect(url_for('tac_obras', tid=tid))
    obra_editar_id = _int(request.args.get('editar'))
    return render_template('tac/obras.html', tac=tac, grupos=GRUPOS_OBRA,
                           obra_editar_id=obra_editar_id)


@app.route('/tac/<int:tid>/obras/<int:oid>/irregularidades', methods=['GET', 'POST'])
@login_required
@tecnico_required
def tac_irregularidades(tid, oid):
    tac = TAC.query.get_or_404(tid)
    obra = ObraTAC.query.get_or_404(oid)
    if obra.tac_id != tid:
        abort(404)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_ireg' and not tac.bloqueado:
            tipo = request.form.get('tipo', '').strip()
            qty = max(1, _int(request.form.get('quantidade')) or 1)
            irr = IrregularidadeTAC(obra_id=oid, tipo=tipo, quantidade=qty)
            db.session.add(irr)
            db.session.commit()
            flash('Irregularidade adicionada.', 'success')
        elif action == 'del_ireg' and not tac.bloqueado:
            iid = _int(request.form.get('id'))
            irr = IrregularidadeTAC.query.get(iid)
            if irr and irr.obra_id == oid:
                db.session.delete(irr)
                db.session.commit()
        elif action == 'save_vagas' and not tac.bloqueado:
            f = request.form
            if not obra.vagas:
                v = VagasTAC(obra_id=oid)
                db.session.add(v)
            else:
                v = obra.vagas

            exigidas = max(0, _int(f.get('vagas_exigidas')) or 0)
            regulares = max(0, _int(f.get('vagas_regulares_executadas')) or 0)
            qvd = max(0, _int(f.get('vagas_dimensao_irregular')) or 0)

            # Vagas computáveis = regulares executadas (podendo ser ajustado manualmente)
            computaveis = max(0, _int(f.get('vagas_computaveis')) or regulares)
            # QVF automático, podendo ser substituído pelo campo manual + justificativa
            qvf_manual = f.get('vagas_faltantes_manual', '').strip()
            just = f.get('justificativa_tecnica', '').strip()
            if qvf_manual and just:
                qvf = max(0, _int(qvf_manual) or 0)
            else:
                qvf = max(0, exigidas - computaveis)

            # Validações anti-duplicidade (seção 9)
            erros = []
            if exigidas <= 0:
                erros.append('Informe o número de vagas exigidas.')
            if regulares < 0 or qvd < 0:
                erros.append('Quantidades não podem ser negativas.')
            if erros:
                for e in erros:
                    flash(e, 'danger')
                return redirect(url_for('tac_irregularidades', tid=tid, oid=oid))

            v.vagas_exigidas = exigidas
            v.vagas_regulares_executadas = regulares
            v.vagas_computaveis = computaveis
            v.vagas_faltantes = qvf
            v.vagas_dimensao_irregular = qvd
            v.largura_exigida = _float(f.get('largura_exigida'))
            v.comprimento_exigido = _float(f.get('comprimento_exigido'))
            v.largura_executada = _float(f.get('largura_executada'))
            v.comprimento_executado = _float(f.get('comprimento_executado'))
            v.justificativa_tecnica = just or None
            v.usuario_id = current_user.id
            v.data_calculo = datetime.utcnow()
            db.session.commit()
            flash('Vagas atualizadas.', 'success')
        return redirect(url_for('tac_irregularidades', tid=tid, oid=oid))
    tipos = TIPOS_IRREGULARIDADE
    perc_tac = PERC_TAC
    return render_template('tac/irregularidades.html',
                           tac=tac, obra=obra, tipos=tipos, perc_tac=perc_tac)


@app.route('/tac/<int:tid>/calcular', methods=['GET', 'POST'])
@login_required
@tecnico_required
def tac_calcular(tid):
    tac = TAC.query.get_or_404(tid)
    if tac.bloqueado:
        flash('TAC assinado/publicado. Não é possível recalcular.', 'danger')
        return redirect(url_for('tac_detail', tid=tid))
    if not tac.cub_id:
        flash('Selecione o CUB antes de calcular.', 'warning')
        return redirect(url_for('tac_editar', tid=tid))
    cubs = CUB.query.order_by(CUB.ano.desc(), CUB.mes.desc()).all()

    cub_val = tac.cub.valor
    data_ref = tac.data_assinatura or tac.data_abertura or date.today()

    resultados = []
    vf_total = 0.0
    for obra in tac.obras:
        r = obra.calcular(cub_val, data_ref)
        r['obra_id'] = obra.id
        r['obra_desc'] = obra.descricao or obra.endereco or f'Obra {obra.id}'
        r['proprietario_nome'] = obra.proprietario.nome if obra.proprietario else None
        r['proprietario_cpf_cnpj'] = obra.proprietario.cpf_cnpj if obra.proprietario else None
        resultados.append(r)
        vf_total += r['vf']

    if request.method == 'POST':
        num_parcelas = max(1, min(6, _int(request.form.get('num_parcelas')) or 1))
        valor_parcela = vf_total / num_parcelas if num_parcelas else 0

        if tac.calculo:
            c = tac.calculo
        else:
            c = CalculoTAC(tac_id=tid)
            db.session.add(c)

        c.cub_valor = cub_val
        c.cub_mes_ref = tac.cub.mes_ano_str
        c.vf_total = vf_total
        c.num_parcelas = num_parcelas
        c.valor_parcela = valor_parcela
        c.resultado_json = json.dumps(resultados, ensure_ascii=False)
        c.data_calculo = datetime.utcnow()
        c.usuario_id = current_user.id

        if tac.situacao == 'Rascunho' or tac.situacao == 'Em análise':
            tac.situacao = 'Cálculo concluído'

        db.session.commit()
        flash('Cálculo concluído.', 'success')
        return redirect(url_for('tac_relatorio', tid=tid))

    return render_template('tac/calcular.html',
                           tac=tac, resultados=resultados,
                           vf_total=vf_total, cubs=cubs)


@app.route('/tac/<int:tid>/relatorio')
@login_required
def tac_relatorio(tid):
    tac = TAC.query.get_or_404(tid)
    c = tac.calculo
    resultados = json.loads(c.resultado_json) if c and c.resultado_json else []
    integrantes = Integrante.query.filter_by(ativo=True).all()
    return render_template('tac/relatorio.html',
                           tac=tac, c=c, resultados=resultados,
                           integrantes=integrantes)


def _gerar_numero_tac(tac):
    """Gera número sequencial TAC-AAAA-NNN na primeira emissão de qualquer PDF."""
    from datetime import date
    ano = date.today().year
    ultimo = (db.session.query(db.func.max(TAC.numero))
              .filter(TAC.numero.like(f'TAC-{ano}-%'))
              .scalar())
    if ultimo:
        try:
            seq = int(ultimo.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f'TAC-{ano}-{seq:03d}'


def _garantir_numero_tac(tac):
    if not tac.numero:
        tac.numero = _gerar_numero_tac(tac)
        db.session.commit()


@app.route('/tac/<int:tid>/relatorio/pdf')
@login_required
def tac_relatorio_pdf(tid):
    tac = TAC.query.get_or_404(tid)
    c = tac.calculo
    if not c:
        flash('Realize o cálculo antes de gerar PDF.', 'warning')
        return redirect(url_for('tac_relatorio', tid=tid))
    _garantir_numero_tac(tac)
    import os as _os, base64 as _b64
    _logo_file = _os.path.join(_os.path.dirname(__file__), 'static', 'img', 'smpu_logo.jpg')
    with open(_logo_file, 'rb') as _lf:
        logo_path = 'data:image/jpeg;base64,' + _b64.b64encode(_lf.read()).decode()
    resultados = json.loads(c.resultado_json) if c.resultado_json else []
    integrantes = Integrante.query.filter_by(ativo=True).all()
    html = render_template('tac/relatorio_pdf.html',
                           tac=tac, c=c, resultados=resultados,
                           integrantes=integrantes, logo_path=logo_path)
    from xhtml2pdf import pisa
    buf = io.BytesIO()
    pisa.CreatePDF(html, dest=buf)
    buf.seek(0)
    nome = f"TAC_{tac.numero or tac.id}_Relatorio.pdf"
    return send_file(buf, mimetype='application/pdf', download_name=nome)


@app.route('/tac/<int:tid>/termo/pdf')
@login_required
def tac_termo_pdf(tid):
    tac = TAC.query.get_or_404(tid)
    c = tac.calculo
    if not c:
        flash('Realize o cálculo antes de gerar o Termo.', 'warning')
        return redirect(url_for('tac_relatorio', tid=tid))
    _garantir_numero_tac(tac)
    import os as _os, base64 as _b64
    _logo_file = _os.path.join(_os.path.dirname(__file__), 'static', 'img', 'smpu_logo.jpg')
    with open(_logo_file, 'rb') as _lf:
        logo_path = 'data:image/jpeg;base64,' + _b64.b64encode(_lf.read()).decode()
    resultados = json.loads(c.resultado_json) if c.resultado_json else []
    integrantes = Integrante.query.filter_by(ativo=True).all()
    html = render_template('tac/termo_pdf.html',
                           tac=tac, c=c, resultados=resultados,
                           integrantes=integrantes, logo_path=logo_path)
    from xhtml2pdf import pisa
    buf = io.BytesIO()
    pisa.CreatePDF(html, dest=buf)
    buf.seek(0)
    nome = f"TAC_{tac.numero or tac.id}_Termo.pdf"
    return send_file(buf, mimetype='application/pdf', download_name=nome)


@app.route('/tac/<int:tid>/extrato/pdf')
@login_required
def tac_extrato_pdf(tid):
    tac = TAC.query.get_or_404(tid)
    c = tac.calculo
    if not c:
        flash('Realize o cálculo antes de gerar o Extrato.', 'warning')
        return redirect(url_for('tac_relatorio', tid=tid))
    _garantir_numero_tac(tac)
    import os as _os, base64 as _b64
    _logo_file = _os.path.join(_os.path.dirname(__file__), 'static', 'img', 'smpu_logo.jpg')
    with open(_logo_file, 'rb') as _lf:
        logo_path = 'data:image/jpeg;base64,' + _b64.b64encode(_lf.read()).decode()
    html = render_template('tac/extrato_pdf.html', tac=tac, c=c, logo_path=logo_path)
    from xhtml2pdf import pisa
    buf = io.BytesIO()
    pisa.CreatePDF(html, dest=buf)
    buf.seek(0)
    nome = f"TAC_{tac.numero or tac.id}_Extrato.pdf"
    return send_file(buf, mimetype='application/pdf', download_name=nome)


# ─── Responsáveis Técnicos ───────────────────────────────────────────────────

@app.route('/responsaveis-tecnicos')
@login_required
@tecnico_required
def rt_index():
    rts = ResponsavelTecnico.query.order_by(ResponsavelTecnico.nome).all()
    return render_template('resp_tecnico/index.html', rts=rts)


@app.route('/responsaveis-tecnicos/novo', methods=['GET', 'POST'])
@login_required
@tecnico_required
def rt_novo():
    if request.method == 'POST':
        f = request.form
        rt = ResponsavelTecnico(
            nome=f.get('nome', '').strip(),
            registro_prof=f.get('registro_prof', '').strip() or None,
            especialidade=f.get('especialidade', '').strip() or None,
            telefone=f.get('telefone', '').strip() or None,
            email=f.get('email', '').strip() or None,
            ativo=True,
        )
        db.session.add(rt)
        db.session.commit()
        flash('Responsável técnico cadastrado.', 'success')
        return redirect(url_for('rt_index'))
    return render_template('resp_tecnico/form.html', rt=None)


@app.route('/responsaveis-tecnicos/<int:rid>/editar', methods=['GET', 'POST'])
@login_required
@tecnico_required
def rt_editar(rid):
    rt = ResponsavelTecnico.query.get_or_404(rid)
    if request.method == 'POST':
        f = request.form
        rt.nome          = f.get('nome', '').strip()
        rt.registro_prof = f.get('registro_prof', '').strip() or None
        rt.especialidade = f.get('especialidade', '').strip() or None
        rt.telefone      = f.get('telefone', '').strip() or None
        rt.email         = f.get('email', '').strip() or None
        rt.ativo         = f.get('ativo') == '1'
        db.session.commit()
        flash('Responsável técnico atualizado.', 'success')
        return redirect(url_for('rt_index'))
    return render_template('resp_tecnico/form.html', rt=rt)


# ─── Obras unificadas – CRUD público ────────────────────────────────────────

@app.route('/obras')
@login_required
def obras_index():
    q  = request.args.get('q', '').strip()
    qp = request.args.get('qp', '').strip()
    qs = Obra.query.order_by(Obra.nome, Obra.endereco)
    if q:
        qs = qs.filter(db.or_(
            Obra.nome.ilike(f'%{q}%'),
            Obra.endereco.ilike(f'%{q}%'),
            Obra.bairro.ilike(f'%{q}%'),
            Obra.inscricao_imobiliaria.ilike(f'%{q}%'),
        ))
    if qp:
        qs = qs.join(Obra.proprietario).filter(Pessoa.nome.ilike(f'%{qp}%'))
    obras = qs.all()
    return render_template('obras/index.html', obras=obras, q=q, qp=qp)


@app.route('/obras/nova', methods=['GET', 'POST'])
@login_required
@tecnico_required
def obras_nova():
    if request.method == 'POST':
        f = request.form
        erros = []
        if not f.get('proprietario_id'):
            erros.append('Proprietário é obrigatório.')
        if not f.get('nome', '').strip():
            erros.append('Nome / Descrição da Obra é obrigatório.')
        if erros:
            for e in erros:
                flash(e, 'danger')
            return render_template('obras/form.html', obra=None,
                                   zoneamentos=Zoneamento.query.filter_by(ativo=True).order_by(Zoneamento.codigo).all(),
                                   pessoas=Pessoa.query.order_by(Pessoa.nome).all(),
                                   form_data=f)
        o = Obra(
            nome=f.get('nome', '').strip() or None,
            cep=f.get('cep', '').strip() or None,
            endereco=f.get('endereco', '').strip() or None,
            numero=f.get('numero', '').strip() or None,
            complemento=f.get('complemento', '').strip() or None,
            bairro=f.get('bairro', '').strip() or None,
            cidade=f.get('cidade', '').strip() or None,
            inscricao_imobiliaria=f.get('inscricao_imobiliaria', '').strip() or None,
            matricula=f.get('matricula', '').strip() or None,
            zoneamento_id=_int(f.get('zoneamento_id')),
            proprietario_id=_int(f.get('proprietario_id')),
            area_terreno=_float(f.get('area_terreno')),
            area_construida=_float(f.get('area_construida')),
            num_pavimentos=_int(f.get('num_pavimentos')),
            observacoes=f.get('observacoes', '').strip() or None,
            criado_por=current_user.id,
        )
        db.session.add(o)
        db.session.commit()
        flash('Obra cadastrada com sucesso.', 'success')
        next_url = request.args.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect(url_for('obras_index'))
    return render_template('obras/form.html', obra=None,
                           zoneamentos=Zoneamento.query.filter_by(ativo=True).order_by(Zoneamento.codigo).all(),
                           pessoas=Pessoa.query.order_by(Pessoa.nome).all())


@app.route('/obras/<int:oid>/editar', methods=['GET', 'POST'])
@login_required
@tecnico_required
def obras_editar(oid):
    o = Obra.query.get_or_404(oid)
    if request.method == 'POST':
        f = request.form
        erros = []
        if not f.get('proprietario_id'):
            erros.append('Proprietário é obrigatório.')
        if not f.get('nome', '').strip():
            erros.append('Nome / Descrição da Obra é obrigatório.')
        if erros:
            for e in erros:
                flash(e, 'danger')
            return render_template('obras/form.html', obra=o,
                                   zoneamentos=Zoneamento.query.filter_by(ativo=True).order_by(Zoneamento.codigo).all(),
                                   pessoas=Pessoa.query.order_by(Pessoa.nome).all())
        o.nome                = f.get('nome', '').strip() or None
        o.cep                 = f.get('cep', '').strip() or None
        o.endereco            = f.get('endereco', '').strip() or None
        o.numero              = f.get('numero', '').strip() or None
        o.complemento         = f.get('complemento', '').strip() or None
        o.bairro              = f.get('bairro', '').strip() or None
        o.cidade              = f.get('cidade', '').strip() or None
        o.inscricao_imobiliaria = f.get('inscricao_imobiliaria', '').strip() or None
        o.matricula           = f.get('matricula', '').strip() or None
        o.zoneamento_id       = _int(f.get('zoneamento_id'))
        o.proprietario_id     = _int(f.get('proprietario_id'))
        o.area_terreno        = _float(f.get('area_terreno'))
        o.area_construida     = _float(f.get('area_construida'))
        o.num_pavimentos      = _int(f.get('num_pavimentos'))
        o.observacoes         = f.get('observacoes', '').strip() or None
        db.session.commit()
        flash('Obra atualizada.', 'success')
        return redirect(url_for('obras_index'))
    return render_template('obras/form.html', obra=o,
                           zoneamentos=Zoneamento.query.filter_by(ativo=True).order_by(Zoneamento.codigo).all(),
                           pessoas=Pessoa.query.order_by(Pessoa.nome).all())


@app.route('/obras/<int:oid>/excluir', methods=['POST'])
@login_required
@tecnico_required
def obras_excluir(oid):
    o = Obra.query.get_or_404(oid)
    vinculada = (
        bool(o.empreendimentos_vinculados) or
        bool(o.tacs_vinculadas) or
        bool(o.solos_criados_vinculados)
    )
    if vinculada:
        flash('Esta obra está vinculada a processos existentes e não pode ser excluída.', 'danger')
    else:
        db.session.delete(o)
        db.session.commit()
        flash('Obra excluída.', 'success')
    return redirect(url_for('obras_index'))


# ─── Solo Criado ─────────────────────────────────────────────────────────────

@app.route('/solo-criado')
@login_required
def sc_index():
    q   = request.args.get('q', '').strip()
    qp  = request.args.get('qp', '').strip()
    sit = request.args.get('situacao', '')
    qs  = SoloCriado.query.order_by(SoloCriado.criado_em.desc())
    if q:
        qs = qs.filter(db.or_(
            SoloCriado.nome_empreendimento.ilike(f'%{q}%'),
            SoloCriado.endereco_imovel.ilike(f'%{q}%'),
            SoloCriado.num_processo.ilike(f'%{q}%'),
        ))
    if qp:
        qs = qs.join(SoloCriado.pessoa).filter(Pessoa.nome.ilike(f'%{qp}%'))
    if sit:
        qs = qs.filter(SoloCriado.situacao == sit)
    registros = qs.all()
    ano_atual = date.today().year
    registros_ano = [r for r in registros if r.criado_em and r.criado_em.year == ano_atual]
    totais_ano = {
        'von':  sum(r.von or 0 for r in registros_ano),
        'vin':  sum(r.vin or 0 for r in registros_ano),
        'vtot': sum((r.von or 0) + (r.vin or 0) for r in registros_ano),
        'ano':  ano_atual,
    }
    return render_template('solo_criado/index.html', registros=registros,
                           q=q, qp=qp, sit=sit, situacoes=SITUACOES_SC, totais_ano=totais_ano)


@app.route('/solo-criado/novo', methods=['GET', 'POST'])
@login_required
@tecnico_required
def sc_novo():
    if request.method == 'POST':
        sc = SoloCriado()
        _sc_fill(sc, request.form)
        sc.criado_por = current_user.id
        db.session.add(sc)
        db.session.commit()
        flash('Registro criado com sucesso.', 'success')
        return redirect(url_for('sc_detail', sid=sc.id))
    return render_template('solo_criado/form.html', sc=None,
                           situacoes=SITUACOES_SC,
                           zoneamentos=Zoneamento.query.order_by('codigo').all(),
                           cubs=CUB.query.order_by(CUB.ano.desc(), CUB.mes.desc()).limit(24).all(),
                           pessoas=Pessoa.query.order_by(Pessoa.nome).all(),
                           resp_tecnicos=ResponsavelTecnico.query.filter_by(ativo=True).order_by(ResponsavelTecnico.nome).all())


@app.route('/solo-criado/<int:sid>')
@login_required
def sc_detail(sid):
    sc = SoloCriado.query.get_or_404(sid)
    return render_template('solo_criado/detail.html', sc=sc)


@app.route('/solo-criado/<int:sid>/editar', methods=['GET', 'POST'])
@login_required
@tecnico_required
def sc_editar(sid):
    sc = SoloCriado.query.get_or_404(sid)
    if request.method == 'POST':
        _sc_fill(sc, request.form)
        db.session.commit()
        flash('Registro atualizado.', 'success')
        return redirect(url_for('sc_detail', sid=sc.id))
    return render_template('solo_criado/form.html', sc=sc,
                           situacoes=SITUACOES_SC,
                           zoneamentos=Zoneamento.query.order_by('codigo').all(),
                           cubs=CUB.query.order_by(CUB.ano.desc(), CUB.mes.desc()).limit(24).all(),
                           pessoas=Pessoa.query.order_by(Pessoa.nome).all(),
                           resp_tecnicos=ResponsavelTecnico.query.filter_by(ativo=True).order_by(ResponsavelTecnico.nome).all())


@app.route('/solo-criado/<int:sid>/calcular', methods=['GET', 'POST'])
@login_required
@tecnico_required
def sc_calcular(sid):
    sc = SoloCriado.query.get_or_404(sid)
    erros, alertas = [], []
    if request.method == 'POST':
        # Entrada: áreas em m² — percentuais são derivados pela model
        sc.aon = _float(request.form.get('aon')) or sc.aon
        sc.ain = _float(request.form.get('ain')) or sc.ain
        sc.aag = _float(request.form.get('aag')) or sc.aag
        erros, alertas = sc.validar()
        if not erros:
            sc.calcular()
            sc.calculado_por = current_user.id
            _now = datetime.utcnow()
            sc.data_calculo = _now
            sc.atualizado_em = _now
            if sc.situacao in ('Rascunho', 'Em preenchimento', 'Com pendências'):
                sc.situacao = 'Aguardando parecer técnico'
            db.session.commit()
            flash('Cálculo realizado com sucesso.', 'success')
            return redirect(url_for('sc_detail', sid=sc.id))
        else:
            flash('Corrija os erros antes de calcular.', 'danger')
    else:
        erros, alertas = sc.validar()
    return render_template('solo_criado/calcular.html', sc=sc, erros=erros, alertas=alertas)


@app.route('/solo-criado/<int:sid>/relatorio')
@login_required
def sc_relatorio(sid):
    sc = SoloCriado.query.get_or_404(sid)
    return render_template('solo_criado/relatorio.html', sc=sc)


def _gerar_numero_sc(sc):
    """Gera número sequencial SC-AAAA-NNN no momento da primeira emissão de PDF."""
    from datetime import date
    ano = date.today().year
    ultimo = (db.session.query(db.func.max(SoloCriado.numero))
              .filter(SoloCriado.numero.like(f'SC-{ano}-%'))
              .scalar())
    if ultimo:
        try:
            seq = int(ultimo.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f'SC-{ano}-{seq:03d}'


@app.route('/solo-criado/<int:sid>/relatorio.pdf')
@login_required
def sc_relatorio_pdf(sid):
    sc = SoloCriado.query.get_or_404(sid)
    # Gera o número sequencial na primeira emissão do PDF
    if not sc.numero:
        sc.numero = _gerar_numero_sc(sc)
        db.session.commit()
    import os as _os, base64 as _b64
    from xhtml2pdf import pisa
    _logo_file = _os.path.join(_os.path.dirname(__file__), 'static', 'img', 'smpu_logo.jpg')
    with open(_logo_file, 'rb') as _lf:
        logo_path = 'data:image/jpeg;base64,' + _b64.b64encode(_lf.read()).decode()
    html = render_template('solo_criado/relatorio_pdf.html', sc=sc, logo_path=logo_path)
    buf = io.BytesIO()
    pisa.CreatePDF(html, dest=buf)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf',
                     download_name=f'SoloCriado_{sc.numero}.pdf')


def _sc_fill(sc, f):
    def s(k): return f.get(k, '').strip() or None
    def fi(k): return _float(f.get(k))
    # Obra unificada — preserva vínculo existente; nunca cria duplicata ao editar
    from flask_login import current_user as _cu
    sc.obra_id = _get_or_create_obra(f, _cu.id, existing_obra_id=sc.obra_id)
    sc.situacao              = f.get('situacao', 'Rascunho')
    if not sc.numero:                        # número imutável após gerado
        sc.numero            = s('numero')
    sc.num_processo          = s('num_processo_adm')
    sc.cep_imovel            = s('cep_imovel')
    sc.endereco_imovel       = s('endereco_imovel')
    sc.numero_imovel         = s('numero_imovel')
    sc.complemento_imovel    = s('complemento_imovel')
    sc.bairro_imovel         = s('bairro')
    sc.cidade_imovel         = s('cidade_imovel')
    sc.inscricao_imob        = s('inscricao_imobiliaria')
    sc.matricula             = s('matricula')
    sc.area_terreno          = fi('area_terreno')
    sc.area_construida_total = fi('area_construida_total')
    sc.area_computavel       = fi('area_computavel')
    sc.taxa_ocupacao         = fi('taxa_ocupacao')
    sc.pessoa_id             = _int(f.get('pessoa_id'))
    sc.resp_tecnico_id       = _int(f.get('resp_tecnico_id'))
    sc.zoneamento_id         = _int(f.get('zoneamento_id'))
    # IAB vem do zoneamento; IAM = IAB × 1,50
    zid = _int(f.get('zoneamento_id'))
    if zid:
        zon = Zoneamento.query.get(zid)
        if zon:
            sc.iab = zon.cab
            sc.iam = round(zon.cab * 1.50, 4)
            sc.permite_solo_criado = zon.permite_solo_criado
        else:
            sc.iab = fi('iab')
            sc.iam = fi('iam')
            sc.permite_solo_criado = bool(f.get('permite_solo_criado'))
    else:
        sc.iab = fi('iab')
        sc.iam = fi('iam')
        sc.permite_solo_criado = bool(f.get('permite_solo_criado'))
    sc.aon                   = fi('aon')
    sc.ain                   = fi('ain')
    sc.aag                   = fi('aag')
    sc.cub_id                = _int(f.get('cub_id'))
    sc.cub_valor             = fi('cub_valor')
    sc.cub_mes_ref           = s('cub_mes_ref')
    sc.justificativa_cub     = s('justificativa_cub')
    sc.parecer_tecnico       = s('parecer_tecnico')
    sc.decisao_comissao      = s('decisao_comissao')
    sc.condicionantes        = s('condicionantes')
    sc.observacoes           = s('observacoes')
    # Fill CUB from selected id
    if sc.cub_id and not sc.cub_valor:
        cub = CUB.query.get(sc.cub_id)
        if cub:
            sc.cub_valor   = cub.valor
            sc.cub_mes_ref = cub.mes_ano_str



# ─── Cabeçalhos de segurança HTTP ────────────────────────────────────────────

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Content-Security-Policy: permite Bootstrap CDN + ícones
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
        "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "connect-src 'self' https://viacep.com.br; "
        "frame-ancestors 'self';"
    )
    return response


if __name__ == '__main__':
    init_db()
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug, host='127.0.0.1', port=5000)
