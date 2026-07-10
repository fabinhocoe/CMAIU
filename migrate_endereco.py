#!/usr/bin/env python3
"""
Script de migração para adicionar novos campos de endereço à tabela usuarios.
"""

import sys
from app import app, db
from sqlalchemy import text

def migrate_endereco():
    """Adiciona campos de endereço detalhado à tabela usuarios."""
    with app.app_context():
        try:
            # Verificar quais colunas já existem
            inspector = db.inspect(db.engine)
            usuario_columns = [c['name'] for c in inspector.get_columns('usuarios')]

            new_columns = {
                'cep': "ALTER TABLE usuarios ADD COLUMN cep VARCHAR(10)",
                'numero': "ALTER TABLE usuarios ADD COLUMN numero VARCHAR(20)",
                'bairro': "ALTER TABLE usuarios ADD COLUMN bairro VARCHAR(200)",
                'cidade': "ALTER TABLE usuarios ADD COLUMN cidade VARCHAR(200)",
                'estado': "ALTER TABLE usuarios ADD COLUMN estado VARCHAR(2)",
            }

            print("Verificando colunas de endereço...")
            for col_name, sql in new_columns.items():
                if col_name in usuario_columns:
                    print(f"  ✓ Coluna '{col_name}' já existe")
                else:
                    try:
                        print(f"  Adicionando coluna '{col_name}'...")
                        db.session.execute(text(sql))
                        db.session.commit()
                        print(f"    ✓ Coluna '{col_name}' adicionada com sucesso")
                    except Exception as e:
                        print(f"    ✗ Erro ao adicionar '{col_name}': {e}")
                        db.session.rollback()

            print("\n✓ Migração de endereço concluída!")
            return True

        except Exception as e:
            print(f"✗ Erro durante migração: {e}")
            return False

if __name__ == '__main__':
    success = migrate_endereco()
    sys.exit(0 if success else 1)
