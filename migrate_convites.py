#!/usr/bin/env python3
"""
Script de migração para criar a tabela de convites de registro.
"""

import os
import sys
from app import app, db

def migrate_convites():
    """Cria a tabela de convites de registro."""
    with app.app_context():
        try:
            # Verificar se a tabela já existe
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()

            if 'convite_registro' in existing_tables:
                print("✓ Tabela 'convite_registro' já existe. Nenhuma migração necessária.")
                return True

            print("Criando tabela 'convite_registro'...")

            # Criar todas as tabelas definidas nos modelos
            db.create_all()

            print("✓ Tabela 'convite_registro' criada com sucesso!")
            return True

        except Exception as e:
            print(f"\n✗ Erro durante migração: {e}")
            return False

if __name__ == '__main__':
    success = migrate_convites()
    sys.exit(0 if success else 1)
