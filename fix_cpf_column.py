#!/usr/bin/env python3
"""
Script simples para adicionar a coluna cpf sem UNIQUE constraint.
"""

import sys
from app import app, db
from sqlalchemy import text

def fix_cpf():
    """Adiciona coluna cpf sem UNIQUE."""
    with app.app_context():
        try:
            # Verificar se coluna já existe
            inspector = db.inspect(db.engine)
            usuario_columns = [c['name'] for c in inspector.get_columns('usuarios')]

            if 'cpf' in usuario_columns:
                print("✓ Coluna 'cpf' já existe. Nenhuma ação necessária.")
                return True

            print("Adicionando coluna 'cpf'...")
            db.session.execute(text("ALTER TABLE usuarios ADD COLUMN cpf VARCHAR(14)"))
            db.session.commit()
            print("✓ Coluna 'cpf' adicionada com sucesso!")
            return True

        except Exception as e:
            print(f"✗ Erro: {e}")
            return False

if __name__ == '__main__':
    success = fix_cpf()
    sys.exit(0 if success else 1)
