#!/usr/bin/env python3
"""
Script de migração para adicionar novos campos à tabela usuarios.
Execute este script para atualizar a estrutura do banco de dados.
"""

import os
import sys
from datetime import datetime, date
from app import app, db, Usuario

def migrate_usuarios():
    """Adiciona novos campos à tabela usuarios."""
    with app.app_context():
        # Verificar se as colunas já existem
        inspector = db.inspect(db.engine)
        usuario_columns = [c['name'] for c in inspector.get_columns('usuarios')]

        new_columns = ['cpf', 'telefone', 'data_nascimento', 'cargo', 'setor', 'supervisor_id',
                       'data_admissao', 'endereco', 'observacoes', 'assinatura_digital']

        missing_columns = [col for col in new_columns if col not in usuario_columns]

        if not missing_columns:
            print("✓ Todas as colunas já existem. Nenhuma migração necessária.")
            return True

        print(f"Adicionando {len(missing_columns)} nova(s) coluna(s): {', '.join(missing_columns)}")

        try:
            # Para banco SQLite, precisamos fazer alterações individuais
            from sqlalchemy import text

            alteracoes = [
                "ALTER TABLE usuarios ADD COLUMN cpf VARCHAR(14) UNIQUE",
                "ALTER TABLE usuarios ADD COLUMN telefone VARCHAR(20)",
                "ALTER TABLE usuarios ADD COLUMN data_nascimento DATE",
                "ALTER TABLE usuarios ADD COLUMN cargo VARCHAR(200)",
                "ALTER TABLE usuarios ADD COLUMN setor VARCHAR(200)",
                "ALTER TABLE usuarios ADD COLUMN supervisor_id INTEGER",
                "ALTER TABLE usuarios ADD COLUMN data_admissao DATE",
                "ALTER TABLE usuarios ADD COLUMN endereco VARCHAR(300)",
                "ALTER TABLE usuarios ADD COLUMN observacoes TEXT",
                "ALTER TABLE usuarios ADD COLUMN assinatura_digital VARCHAR(500)",
            ]

            for sql in alteracoes:
                try:
                    db.session.execute(text(sql))
                    db.session.commit()
                    print(f"  ✓ {sql[:50]}...")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"  ℹ Coluna já existe (ignorado)")
                    else:
                        print(f"  ✗ Erro: {e}")

            print("\n✓ Migração concluída com sucesso!")
            return True

        except Exception as e:
            print(f"\n✗ Erro durante migração: {e}")
            return False

if __name__ == '__main__':
    success = migrate_usuarios()
    sys.exit(0 if success else 1)
