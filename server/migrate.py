"""Aplica migrações idempotentes e verifica o catálogo do banco configurado."""

from server.config import configuracao
from server.persistence.factory import criar_livraria_postgres
from sqlalchemy import text


def main():
    config = configuracao()
    if config['STORAGE_BACKEND'] != 'postgresql':
        raise SystemExit('A migração exige STORAGE_BACKEND=postgresql.')
    try:
        loja, store = criar_livraria_postgres(config)
        try:
            quantidade = len(loja.buscar())
            if quantidade < 10:
                raise SystemExit('O catálogo deve conter pelo menos dez livros.')
            with store.engine.connect() as connection:
                usuarios = connection.scalar(text('SELECT count(*) FROM usuarios WHERE nome IS NOT NULL AND email IS NOT NULL'))
            if usuarios < 4:
                raise SystemExit('O banco deve conter pelo menos quatro perfis cadastrados.')
            print(f'Migrações aplicadas: {quantidade} livros e {usuarios} perfis cadastrados.')
        finally:
            store.fechar()
    except RuntimeError as erro:
        raise SystemExit(str(erro)) from None


if __name__ == '__main__':
    main()
