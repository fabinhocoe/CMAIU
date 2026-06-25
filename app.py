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
                    Integrante, Processo, Proprietario, Empreendimento,
                    Impacto, Calculo, Relatorio,
                    SITUACOES_PROCESSO, USOS, PADROES_IMPACTO,
                    CLASSIFICACOES_IMPACTO, IMPACTOS_SOCIAIS, IMPACTOS_VIARIOS,
                    NIVEIS_COMPENSACAO, PARAMS_INICIAIS, MESES,
                    TAC, CompromissarioTAC, ObraTAC, IrregularidadeTAC,
                    VagasTAC, CalculoTAC,
                    SITUACOES_TAC, GRUPOS_OBRA, TIPOS_IRREGULARIDADE, PERC_TAC)

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
    total = Processo.query.count()
    em_analise = Processo.query.filter_by(situacao='Em análise').count()
    aprovados = Processo.query.filter_by(situacao='Aprovado').count()
    recentes = Processo.query.order_by(Processo.criado_em.desc()).limit(10).all()
    cub_atual = CUB.query.order_by(CUB.ano.desc(), CUB.mes.desc()).first()
    return render_template('dashboard.html', total=total, em_analise=em_analise,
                           aprovados=aprovados, recentes=recentes, cub_atual=cub_atual)


# ─── Processos ───────────────────────────────────────────────────────────────

@app.route('/processos')
@login_required
def processos_index():
    q = request.args.get('q', '')
    sit = request.args.get('situacao', '')
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
    processos = query.order_by(Processo.criado_em.desc()).all()
    return render_template('processos/index.html', processos=processos,
                           q=q, sit=sit, situacoes=SITUACOES_PROCESSO)


@app.route('/processos/novo', methods=['GET', 'POST'])
@login_required
@tecnico_required
def processos_novo():
    zoneamentos = Zoneamento.query.filter_by(ativo=True).order_by(Zoneamento.codigo).all()
    if request.method == 'POST':
        f = request.form
        p = Processo(
            num_processo=f.get('num_processo'),
            protocolo_cmaiu=f.get('protocolo_cmaiu'),
            protocolo_aprovacao=f.get('protocolo_aprovacao'),
            data_entrada=_parse_date(f.get('data_entrada')),
            data_analise=_parse_date(f.get('data_analise')),
            situacao=f.get('situacao', 'Em análise'),
            observacoes=f.get('observacoes'),
            criado_por=current_user.id,
        )
        db.session.add(p)
        db.session.flush()

        prop = Proprietario(
            processo_id=p.id,
            nome=f.get('prop_nome'),
            cpf_cnpj=f.get('prop_cpf_cnpj'),
            endereco=f.get('prop_endereco'),
            telefone=f.get('prop_telefone'),
            email=f.get('prop_email'),
        )
        db.session.add(prop)

        zon_id = _int(f.get('zoneamento_id'))
        zon = Zoneamento.query.get(zon_id) if zon_id else None
        emp = Empreendimento(
            processo_id=p.id,
            nome=f.get('emp_nome'),
            endereco=f.get('emp_endereco'),
            bairro=f.get('emp_bairro'),
            inscricao=f.get('emp_inscricao'),
            matricula=f.get('emp_matricula'),
            zoneamento_id=zon_id,
            uso_predominante=f.get('emp_uso_predominante'),
            uso_secundario=f.get('emp_uso_secundario'),
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
                           usos=USOS, padroes=PADROES_IMPACTO)


@app.route('/processos/<int:pid>')
@login_required
def processos_detail(pid):
    p = Processo.query.get_or_404(pid)
    return render_template('processos/detail.html', processo=p)


@app.route('/processos/<int:pid>/editar', methods=['GET', 'POST'])
@login_required
@tecnico_required
def processos_editar(pid):
    p = Processo.query.get_or_404(pid)
    prop = p.proprietario or Proprietario(processo_id=pid)
    emp = p.empreendimento or Empreendimento(processo_id=pid)
    zoneamentos = Zoneamento.query.filter_by(ativo=True).order_by(Zoneamento.codigo).all()

    if request.method == 'POST':
        f = request.form
        p.num_processo = f.get('num_processo')
        p.protocolo_cmaiu = f.get('protocolo_cmaiu')
        p.protocolo_aprovacao = f.get('protocolo_aprovacao')
        p.data_entrada = _parse_date(f.get('data_entrada'))
        p.data_analise = _parse_date(f.get('data_analise'))
        p.situacao = f.get('situacao', p.situacao)
        p.observacoes = f.get('observacoes')

        if not p.proprietario:
            prop.processo_id = pid
            db.session.add(prop)
        prop.nome = f.get('prop_nome')
        prop.cpf_cnpj = f.get('prop_cpf_cnpj')
        prop.endereco = f.get('prop_endereco')
        prop.telefone = f.get('prop_telefone')
        prop.email = f.get('prop_email')

        if not p.empreendimento:
            emp.processo_id = pid
            db.session.add(emp)
        zon_id = _int(f.get('zoneamento_id'))
        zon = Zoneamento.query.get(zon_id) if zon_id else None
        emp.nome = f.get('emp_nome')
        emp.endereco = f.get('emp_endereco')
        emp.bairro = f.get('emp_bairro')
        emp.inscricao = f.get('emp_inscricao')
        emp.matricula = f.get('emp_matricula')
        emp.zoneamento_id = zon_id
        emp.uso_predominante = f.get('emp_uso_predominante')
        emp.uso_secundario = f.get('emp_uso_secundario')
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

    return render_template('processos/form.html', processo=p, prop=prop, emp=emp,
                           zoneamentos=zoneamentos, situacoes=SITUACOES_PROCESSO,
                           usos=USOS, padroes=PADROES_IMPACTO)


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

        at = _float(f.get('area_terreno')) or (emp.area_terreno if emp else None)
        cab = _float(f.get('cab')) or (emp.cab if emp else None)
        ac = _float(f.get('area_computavel')) or (emp.area_computavel if emp else None)
        if not at:
            errors.append('Informe a área do terreno.')
        if not cab:
            errors.append('Informe o coeficiente de aproveitamento básico.')
        if not ac:
            errors.append('Informe a área computável do projeto.')

        zon = emp.zoneamento if emp else None

        perc_on = _float(f.get('perc_oneroso', 0)) or 0
        perc_inf = _float(f.get('perc_infra', 0)) or 0
        perc_cap = _float(f.get('perc_captacao', 0)) or 0
        area_on = _float(f.get('area_onerosa', 0)) or 0
        area_inf = _float(f.get('area_infra', 0)) or 0
        area_cap = _float(f.get('area_captacao', 0)) or 0

        lim_on = params.get('limite_oneroso', 40)
        lim_inf = params.get('limite_infra', 5)
        lim_cap = params.get('limite_captacao', 5)
        lim_tot = params.get('limite_total', 50)

        if zon and not zon.permite_solo_criado and (area_on > 0 or area_inf > 0 or area_cap > 0):
            errors.append(f'O zoneamento {zon.codigo} não permite solo criado.')

        if perc_on > lim_on:
            errors.append(f'Percentual oneroso ({perc_on:.2f}%) excede o limite de {lim_on:.0f}%.')
        if perc_inf > lim_inf:
            errors.append(f'Percentual de infraestrutura ({perc_inf:.2f}%) excede o limite de {lim_inf:.0f}%.')
        if perc_cap > lim_cap:
            errors.append(f'Percentual de captação ({perc_cap:.2f}%) excede o limite de {lim_cap:.0f}%.')
        if (perc_on + perc_inf + perc_cap) > lim_tot:
            errors.append(f'Percentual total ({perc_on+perc_inf+perc_cap:.2f}%) excede o limite de {lim_tot:.0f}%.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return redirect(url_for('processos_calculos', pid=pid))

        ab = (at * cab) if at and cab else 0
        ae = max(0, (ac - ab)) if ac and ab else 0
        vu = cub_obj.valor * params.get('perc_cub_solo_criado', 0.06)
        vo = area_on * vu
        vi = area_inf * vu
        va = area_cap * vu

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
    return render_template('processos/relatorio.html', processo=p, calc=calc,
                           rel=rel, integrantes=integrantes)


@app.route('/processos/<int:pid>/relatorio/pdf')
@login_required
def processos_relatorio_pdf(pid):
    p = Processo.query.get_or_404(pid)
    calc = p.ultimo_calculo
    rel = p.ultimo_relatorio
    integrantes = Integrante.query.filter_by(ativo=True).all()

    html = render_template('relatorio/pdf.html', processo=p, calc=calc,
                           rel=rel, integrantes=integrantes,
                           data_emissao=date.today())
    try:
        from xhtml2pdf import pisa
        buf = io.BytesIO()
        pisa.CreatePDF(html.encode('utf-8'), dest=buf, encoding='utf-8')
        buf.seek(0)
        nome = f"CMAIU_{p.protocolo_cmaiu or p.id}.pdf".replace('/', '-')
        return send_file(buf, mimetype='application/pdf',
                         as_attachment=True, download_name=nome)
    except Exception as e:
        flash(f'Erro ao gerar PDF: {e}', 'danger')
        return redirect(url_for('processos_relatorio', pid=pid))


@app.route('/processos/<int:pid>/exportar-excel')
@login_required
def processos_exportar_excel(pid):
    p = Processo.query.get_or_404(pid)
    calc = p.ultimo_calculo
    emp = p.empreendimento
    prop = p.proprietario
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

        row('Protocolo CMAIU', p.protocolo_cmaiu)
        row('Processo Administrativo', p.num_processo)
        row('Protocolo de Aprovação', p.protocolo_aprovacao)
        row('Situação', p.situacao)
        row('Data de Entrada', str(p.data_entrada or ''))
        row('Proprietário', prop.nome if prop else '')
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
        nome = f"CMAIU_{p.protocolo_cmaiu or p.id}.xlsx".replace('/', '-')
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
        if Usuario.query.filter_by(email=email).first():
            flash('E-mail já cadastrado.', 'danger')
        else:
            u = Usuario(nome=f.get('nome'), email=email,
                        perfil=f.get('perfil', 'consulta'))
            u.set_senha(f.get('senha', 'cmaiu@2025'))
            db.session.add(u)
            db.session.commit()
            flash('Usuário cadastrado.', 'success')
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
            admin.set_senha('cmaiu@2025')
            db.session.add(admin)

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


# ─── TAC – Termo de Ajustamento de Conduta ───────────────────────────────────

@app.route('/tac')
@login_required
def tac_index():
    tacs = TAC.query.order_by(TAC.criado_em.desc()).all()
    return render_template('tac/index.html', tacs=tacs)


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
    return render_template('tac/form.html', tac=None, cubs=cubs)


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
    return render_template('tac/form.html', tac=tac, cubs=cubs)


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
            db.session.commit()
            flash('Obra adicionada.', 'success')
        elif action == 'delete' and not tac.bloqueado:
            oid = _int(request.form.get('id'))
            o = ObraTAC.query.get(oid)
            if o and o.tac_id == tid:
                db.session.delete(o)
                db.session.commit()
        return redirect(url_for('tac_obras', tid=tid))
    return render_template('tac/obras.html', tac=tac, grupos=GRUPOS_OBRA)


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


@app.route('/tac/<int:tid>/relatorio/pdf')
@login_required
def tac_relatorio_pdf(tid):
    tac = TAC.query.get_or_404(tid)
    c = tac.calculo
    if not c:
        flash('Realize o cálculo antes de gerar PDF.', 'warning')
        return redirect(url_for('tac_relatorio', tid=tid))
    resultados = json.loads(c.resultado_json) if c.resultado_json else []
    integrantes = Integrante.query.filter_by(ativo=True).all()
    html = render_template('tac/relatorio_pdf.html',
                           tac=tac, c=c, resultados=resultados,
                           integrantes=integrantes)
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
    resultados = json.loads(c.resultado_json) if c.resultado_json else []
    integrantes = Integrante.query.filter_by(ativo=True).all()
    html = render_template('tac/termo_pdf.html',
                           tac=tac, c=c, resultados=resultados,
                           integrantes=integrantes)
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
    html = render_template('tac/extrato_pdf.html', tac=tac, c=c)
    from xhtml2pdf import pisa
    buf = io.BytesIO()
    pisa.CreatePDF(html, dest=buf)
    buf.seek(0)
    nome = f"TAC_{tac.numero or tac.id}_Extrato.pdf"
    return send_file(buf, mimetype='application/pdf', download_name=nome)


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
        "frame-ancestors 'self';"
    )
    return response


if __name__ == '__main__':
    init_db()
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug, host='127.0.0.1', port=5000)
