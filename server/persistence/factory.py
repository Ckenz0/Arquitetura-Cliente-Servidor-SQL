"""Composição de PostgreSQL, esquema relacional, migrações e serviço."""

from sqlalchemy import create_engine, make_url
from sqlalchemy.exc import SQLAlchemyError

from server.persistence.migrations import migrar
from server.persistence.postgres import BancoIndisponivel, PostgresStore
from server.services import Livraria


def criar_livraria_postgres(config):
    engine = None
    try:
        url = make_url(config['DATABASE_URL']).set(drivername='postgresql+psycopg')
        engine = create_engine(url, pool_size=4, max_overflow=2, pool_timeout=4,
                               pool_pre_ping=True, pool_recycle=120, hide_parameters=True,
                               connect_args={'connect_timeout': 4, 'options': '-c timezone=UTC'})
        loja = Livraria()
        store = PostgresStore(loja, engine)
        store.criar_schema()
        migrar(loja)
        return loja, store
    except (SQLAlchemyError, BancoIndisponivel):
        if engine is not None:
            engine.dispose()
        raise RuntimeError('Não foi possível iniciar o PostgreSQL. Confira a configuração e a disponibilidade do banco.') from None
