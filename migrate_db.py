"""
Script de migração do banco de dados.
Execute sempre que atualizar o código com git pull:
    python migrate_db.py
"""
from app import app, db
import sqlalchemy as sa

MIGRATIONS = [
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

def get_columns(conn, table):
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return {row[1] for row in result}

def run():
    with app.app_context():
        conn = db.engine.connect()
        ok = skipped = errors = 0
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
        conn.close()
        print(f"\nMigração concluída: {ok} adicionadas, {skipped} já existiam, {errors} erros.")

if __name__ == '__main__':
    print("Executando migrações...")
    run()
