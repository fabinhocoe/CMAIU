"""
Script de migração do banco de dados.
Execute sempre que atualizar o código com git pull:
    python migrate_db.py
"""
from app import app, db
import sqlalchemy as sa

MIGRATIONS = [
    # empreendimentos – CEP, padrão e obra unificada
    ("empreendimentos", "cep",                  "ALTER TABLE empreendimentos ADD COLUMN cep VARCHAR(10)"),
    ("empreendimentos", "padrao_empreendimento","ALTER TABLE empreendimentos ADD COLUMN padrao_empreendimento VARCHAR(50)"),
    ("empreendimentos", "obra_id",              "ALTER TABLE empreendimentos ADD COLUMN obra_id INTEGER REFERENCES obras(id)"),
    # obras_tac – vínculo com obra unificada
    ("obras_tac", "obra_id", "ALTER TABLE obras_tac ADD COLUMN obra_id INTEGER REFERENCES obras(id)"),
    # solo_criado – vínculo com obra unificada
    ("solo_criado", "obra_id", "ALTER TABLE solo_criado ADD COLUMN obra_id INTEGER REFERENCES obras(id)"),
    # obras – área construída
    ("obras", "area_construida", "ALTER TABLE obras ADD COLUMN area_construida FLOAT"),
    # solo_criado – novos campos
    ("solo_criado", "versao",               "ALTER TABLE solo_criado ADD COLUMN versao INTEGER DEFAULT 1"),
    ("solo_criado", "versao_anterior",      "ALTER TABLE solo_criado ADD COLUMN versao_anterior INTEGER REFERENCES solo_criado(id)"),
    ("solo_criado", "numero",               "ALTER TABLE solo_criado ADD COLUMN numero VARCHAR(30)"),
    ("solo_criado", "num_processo",         "ALTER TABLE solo_criado ADD COLUMN num_processo VARCHAR(100)"),
    ("solo_criado", "ano_processo",         "ALTER TABLE solo_criado ADD COLUMN ano_processo VARCHAR(10)"),
    ("solo_criado", "protocolo",            "ALTER TABLE solo_criado ADD COLUMN protocolo VARCHAR(100)"),
    ("solo_criado", "data_requerimento",    "ALTER TABLE solo_criado ADD COLUMN data_requerimento DATE"),
    ("solo_criado", "resp_tecnico_id",      "ALTER TABLE solo_criado ADD COLUMN resp_tecnico_id INTEGER REFERENCES responsaveis_tecnicos(id)"),
    ("solo_criado", "cep_imovel",           "ALTER TABLE solo_criado ADD COLUMN cep_imovel VARCHAR(10)"),
    ("solo_criado", "numero_imovel",        "ALTER TABLE solo_criado ADD COLUMN numero_imovel VARCHAR(20)"),
    ("solo_criado", "complemento_imovel",   "ALTER TABLE solo_criado ADD COLUMN complemento_imovel VARCHAR(200)"),
    ("solo_criado", "bairro_imovel",        "ALTER TABLE solo_criado ADD COLUMN bairro_imovel VARCHAR(200)"),
    ("solo_criado", "cidade_imovel",        "ALTER TABLE solo_criado ADD COLUMN cidade_imovel VARCHAR(200)"),
    ("solo_criado", "inscricao_imob",       "ALTER TABLE solo_criado ADD COLUMN inscricao_imob VARCHAR(100)"),
    ("solo_criado", "matricula",            "ALTER TABLE solo_criado ADD COLUMN matricula VARCHAR(200)"),
    ("solo_criado", "macrozona_turistica",  "ALTER TABLE solo_criado ADD COLUMN macrozona_turistica BOOLEAN DEFAULT 0"),
    ("solo_criado", "nome_empreendimento",  "ALTER TABLE solo_criado ADD COLUMN nome_empreendimento VARCHAR(300)"),
    ("solo_criado", "uso_empreendimento",   "ALTER TABLE solo_criado ADD COLUMN uso_empreendimento VARCHAR(100)"),
    ("solo_criado", "area_construida_total","ALTER TABLE solo_criado ADD COLUMN area_construida_total FLOAT"),
    ("solo_criado", "num_pavimentos",       "ALTER TABLE solo_criado ADD COLUMN num_pavimentos INTEGER"),
    ("solo_criado", "art_rrt_trt",          "ALTER TABLE solo_criado ADD COLUMN art_rrt_trt VARCHAR(100)"),
    ("solo_criado", "num_proc_aprovacao",   "ALTER TABLE solo_criado ADD COLUMN num_proc_aprovacao VARCHAR(100)"),
    ("solo_criado", "limite_zoneamento",    "ALTER TABLE solo_criado ADD COLUMN limite_zoneamento FLOAT"),
    ("solo_criado", "fundamento_legal",     "ALTER TABLE solo_criado ADD COLUMN fundamento_legal VARCHAR(300)"),
    ("solo_criado", "atualizado_em",        "ALTER TABLE solo_criado ADD COLUMN atualizado_em DATETIME"),
    # vagas_tac – expansão para Lei 5.410/2024
    ("vagas_tac", "vagas_exigidas",            "ALTER TABLE vagas_tac ADD COLUMN vagas_exigidas INTEGER DEFAULT 0"),
    ("vagas_tac", "vagas_regulares_executadas", "ALTER TABLE vagas_tac ADD COLUMN vagas_regulares_executadas INTEGER DEFAULT 0"),
    ("vagas_tac", "vagas_computaveis",          "ALTER TABLE vagas_tac ADD COLUMN vagas_computaveis INTEGER DEFAULT 0"),
    ("vagas_tac", "vagas_dimensao_irregular",   "ALTER TABLE vagas_tac ADD COLUMN vagas_dimensao_irregular INTEGER DEFAULT 0"),
    ("vagas_tac", "largura_exigida",            "ALTER TABLE vagas_tac ADD COLUMN largura_exigida FLOAT"),
    ("vagas_tac", "comprimento_exigido",        "ALTER TABLE vagas_tac ADD COLUMN comprimento_exigido FLOAT"),
    ("vagas_tac", "largura_executada",          "ALTER TABLE vagas_tac ADD COLUMN largura_executada FLOAT"),
    ("vagas_tac", "comprimento_executado",      "ALTER TABLE vagas_tac ADD COLUMN comprimento_executado FLOAT"),
    ("vagas_tac", "justificativa_tecnica",      "ALTER TABLE vagas_tac ADD COLUMN justificativa_tecnica TEXT"),
    ("vagas_tac", "usuario_id",                 "ALTER TABLE vagas_tac ADD COLUMN usuario_id INTEGER REFERENCES usuarios(id)"),
    ("vagas_tac", "data_calculo",               "ALTER TABLE vagas_tac ADD COLUMN data_calculo DATETIME"),
]

CREATE_TABLES = [
    # Cadastro unificado de obras/imóveis
    """CREATE TABLE IF NOT EXISTS obras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome VARCHAR(300),
        cep VARCHAR(10),
        endereco VARCHAR(400),
        numero VARCHAR(20),
        complemento VARCHAR(200),
        bairro VARCHAR(200),
        cidade VARCHAR(200),
        inscricao_imobiliaria VARCHAR(100),
        matricula VARCHAR(200),
        zoneamento_id INTEGER REFERENCES zoneamentos(id),
        area_terreno FLOAT,
        area_construida FLOAT,
        num_pavimentos INTEGER,
        observacoes TEXT,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        criado_por INTEGER REFERENCES usuarios(id)
    )""",
    # Cadastro unificado de pessoas
    """CREATE TABLE IF NOT EXISTS pessoas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome VARCHAR(300) NOT NULL,
        cpf_cnpj VARCHAR(30),
        tipo VARCHAR(20) DEFAULT 'Pessoa Física',
        endereco VARCHAR(400),
        telefone VARCHAR(50),
        email VARCHAR(200),
        observacoes TEXT,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",
    # Vínculo Processo ↔ Pessoa
    """CREATE TABLE IF NOT EXISTS processo_pessoas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        processo_id INTEGER NOT NULL REFERENCES processos(id),
        pessoa_id   INTEGER NOT NULL REFERENCES pessoas(id),
        papel VARCHAR(60) DEFAULT 'Proprietário'
    )""",
    # Vínculo TAC ↔ Pessoa
    """CREATE TABLE IF NOT EXISTS tac_pessoas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tac_id    INTEGER NOT NULL REFERENCES tacs(id),
        pessoa_id INTEGER NOT NULL REFERENCES pessoas(id),
        papel VARCHAR(60) DEFAULT 'Compromissário'
    )""",
    # Responsáveis Técnicos
    """CREATE TABLE IF NOT EXISTS responsaveis_tecnicos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome VARCHAR(300) NOT NULL,
        registro_prof VARCHAR(100),
        especialidade VARCHAR(200),
        telefone VARCHAR(50),
        email VARCHAR(200),
        ativo BOOLEAN DEFAULT 1,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",
    # Solo Criado – LC 109/2011
    """CREATE TABLE IF NOT EXISTS solo_criado (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        situacao VARCHAR(60) DEFAULT 'Rascunho',
        num_processo_adm VARCHAR(100),
        protocolo_cmaiu VARCHAR(60),
        requerente VARCHAR(300),
        endereco_imovel VARCHAR(400),
        bairro VARCHAR(100),
        inscricao_imobiliaria VARCHAR(60),
        responsavel_tecnico VARCHAR(200),
        area_terreno FLOAT,
        area_computavel FLOAT,
        iab FLOAT,
        iam FLOAT,
        taxa_ocupacao FLOAT,
        gabarito FLOAT,
        permite_solo_criado BOOLEAN DEFAULT 1,
        pon FLOAT,
        pin FLOAT,
        pag FLOAT,
        cub_id INTEGER REFERENCES cubs(id),
        cub_valor FLOAT,
        cub_mes_ref VARCHAR(20),
        justificativa_cub TEXT,
        abp FLOAT, aex FLOAT, pn FLOAT, pt FLOAT,
        ion FLOAT, iin FLOAT, iag FLOAT, iat FLOAT,
        aon FLOAT, ain FLOAT, aag FLOAT, aat FLOAT,
        vu FLOAT, von FLOAT, vin FLOAT, vag FLOAT,
        indice_final FLOAT,
        infra_descricao TEXT,
        infra_localizacao VARCHAR(300),
        infra_orcamento FLOAT,
        infra_orgao VARCHAR(200),
        infra_decisao TEXT,
        aguas_tipo VARCHAR(200),
        aguas_capacidade FLOAT,
        aguas_area_atendida FLOAT,
        aguas_finalidade TEXT,
        aguas_parecer TEXT,
        aguas_decisao TEXT,
        parecer_tecnico TEXT,
        decisao_comissao TEXT,
        condicionantes TEXT,
        observacoes TEXT,
        processo_id INTEGER REFERENCES processos(id),
        pessoa_id   INTEGER REFERENCES pessoas(id),
        zoneamento_id INTEGER REFERENCES zoneamentos(id),
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        data_calculo DATETIME,
        criado_por INTEGER REFERENCES usuarios(id),
        calculado_por INTEGER REFERENCES usuarios(id)
    )""",
]


def get_columns(conn, table):
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return {row[1] for row in result}


def get_tables(conn):
    result = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'"))
    return {row[0] for row in result}


def migrate_compromissarios(conn):
    """Migra CompromissarioTAC existentes para Pessoa + TACPessoa."""
    tables = get_tables(conn)
    if 'compromissarios_tac' not in tables or 'tac_pessoas' not in tables:
        return
    rows = conn.execute(sa.text(
        "SELECT c.tac_id, c.nome, c.cpf_cnpj, c.endereco, c.telefone, c.email, c.tipo "
        "FROM compromissarios_tac c "
        "WHERE NOT EXISTS (SELECT 1 FROM tac_pessoas tp WHERE tp.tac_id = c.tac_id "
        "  AND tp.pessoa_id IN (SELECT id FROM pessoas WHERE nome = c.nome))"
    )).fetchall()
    count = 0
    for row in rows:
        tac_id, nome, cpf_cnpj, endereco, telefone, email, tipo = row
        # Verificar se já existe pessoa com mesmo CPF/CNPJ
        if cpf_cnpj:
            p = conn.execute(sa.text("SELECT id FROM pessoas WHERE cpf_cnpj = :c"), {'c': cpf_cnpj}).fetchone()
        else:
            p = conn.execute(sa.text("SELECT id FROM pessoas WHERE nome = :n"), {'n': nome}).fetchone()
        if p:
            pid = p[0]
        else:
            conn.execute(sa.text(
                "INSERT INTO pessoas (nome, cpf_cnpj, tipo, endereco, telefone, email) "
                "VALUES (:nome, :cpf, :tipo, :end, :tel, :email)"
            ), {'nome': nome, 'cpf': cpf_cnpj, 'tipo': tipo or 'Pessoa Física',
                'end': endereco, 'tel': telefone, 'email': email})
            pid = conn.execute(sa.text("SELECT last_insert_rowid()")).scalar()
        conn.execute(sa.text(
            "INSERT INTO tac_pessoas (tac_id, pessoa_id, papel) VALUES (:tid, :pid, 'Compromissário')"
        ), {'tid': tac_id, 'pid': pid})
        count += 1
    conn.commit()
    if count:
        print(f"  → {count} compromissário(s) migrado(s) para cadastro unificado.")


def migrate_proprietarios(conn):
    """Migra Proprietario existentes para Pessoa + ProcessoPessoa."""
    tables = get_tables(conn)
    if 'proprietarios' not in tables or 'processo_pessoas' not in tables:
        return
    rows = conn.execute(sa.text(
        "SELECT p.processo_id, p.nome, p.cpf_cnpj, p.endereco, p.telefone, p.email "
        "FROM proprietarios p "
        "WHERE p.nome IS NOT NULL AND NOT EXISTS "
        "(SELECT 1 FROM processo_pessoas pp WHERE pp.processo_id = p.processo_id)"
    )).fetchall()
    count = 0
    for row in rows:
        processo_id, nome, cpf_cnpj, endereco, telefone, email = row
        if not nome:
            continue
        if cpf_cnpj:
            p = conn.execute(sa.text("SELECT id FROM pessoas WHERE cpf_cnpj = :c"), {'c': cpf_cnpj}).fetchone()
        else:
            p = conn.execute(sa.text("SELECT id FROM pessoas WHERE nome = :n"), {'n': nome}).fetchone()
        if p:
            pid = p[0]
        else:
            conn.execute(sa.text(
                "INSERT INTO pessoas (nome, cpf_cnpj, tipo, endereco, telefone, email) "
                "VALUES (:nome, :cpf, 'Pessoa Física', :end, :tel, :email)"
            ), {'nome': nome, 'cpf': cpf_cnpj, 'end': endereco, 'tel': telefone, 'email': email})
            pid = conn.execute(sa.text("SELECT last_insert_rowid()")).scalar()
        conn.execute(sa.text(
            "INSERT INTO processo_pessoas (processo_id, pessoa_id, papel) VALUES (:pid_proc, :pid, 'Proprietário')"
        ), {'pid_proc': processo_id, 'pid': pid})
        count += 1
    conn.commit()
    if count:
        print(f"  → {count} proprietário(s) migrado(s) para cadastro unificado.")


def run():
    with app.app_context():
        conn = db.engine.connect()
        ok = skipped = errors = 0

        # 1. Criar novas tabelas
        print("Criando tabelas...")
        for sql in CREATE_TABLES:
            try:
                conn.execute(sa.text(sql))
                conn.commit()
            except Exception as e:
                print(f"  ERRO ao criar tabela: {e}")

        # 2. Adicionar colunas faltantes
        print("Adicionando colunas...")
        for table, col, sql in MIGRATIONS:
            existing = get_columns(conn, table)
            if col in existing:
                skipped += 1
                continue
            try:
                conn.execute(sa.text(sql))
                conn.commit()
                print(f"  + {table}.{col}")
                ok += 1
            except Exception as e:
                print(f"  ERRO {table}.{col}: {e}")
                errors += 1

        # 3. Migrar dados legados
        print("Migrando dados existentes...")
        migrate_compromissarios(conn)
        migrate_proprietarios(conn)

        conn.close()
        print(f"\nMigração concluída: {ok} colunas adicionadas, {skipped} já existiam, {errors} erros.")


if __name__ == '__main__':
    print("Executando migrações...")
    run()
