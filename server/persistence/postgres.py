"""Unidade de trabalho PostgreSQL; confirma alterações relacionais juntas."""

from time import sleep

from sqlalchemy import and_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from server.domain.regras import ErroLivraria
from server.persistence.relational import exportar, restaurar
from server.persistence.schema import metadata, TABLES

LOCK_ID = 694517318


class BancoIndisponivel(ErroLivraria):
    def __init__(self):
        super().__init__('O banco de dados está indisponível. Consulte o estado antes de repetir a operação.', 503)


class PostgresStore:
    def __init__(self, loja, engine):
        self.loja = loja
        self.engine = engine
        self._executando = False
        loja.persistencia = self

    def _lock(self, connection):
        connection.exec_driver_sql("SET LOCAL lock_timeout = '4s'")
        connection.exec_driver_sql("SET LOCAL statement_timeout = '8s'")
        connection.execute(text('SELECT pg_advisory_xact_lock(:lock)'), {'lock': LOCK_ID})

    def criar_schema(self):
        try:
            with self.engine.begin() as connection:
                self._lock(connection)
                metadata.create_all(connection)
        except SQLAlchemyError:
            raise BancoIndisponivel() from None

    def health(self):
        try:
            with self.engine.connect() as connection:
                connection.execute(select(1))
        except SQLAlchemyError:
            raise BancoIndisponivel() from None

    def fechar(self):
        self.engine.dispose()

    def _commit(self, transaction):
        transaction.commit()

    def executar(self, operacao):
        with self.loja._lock:
            if self._executando:
                return operacao()
            self._executando = True
            try:
                for tentativa in range(3):
                    try:
                        with self.engine.connect() as connection:
                            transaction = connection.begin()
                            try:
                                self._lock(connection)
                                antes = {}
                                for nome, tabela in TABLES.items():
                                    registros = connection.execute(select(tabela)).mappings()
                                    antes[nome] = {tuple(r[c.name] for c in tabela.primary_key): dict(r) for r in registros}
                                restaurar(self.loja, antes)
                                resultado = operacao()
                                depois = exportar(self.loja)
                                for nome, tabela in reversed(list(TABLES.items())):
                                    for chave in antes[nome].keys() - depois[nome].keys():
                                        condicao = and_(*(c == valor for c, valor in zip(tabela.primary_key, chave)))
                                        connection.execute(tabela.delete().where(condicao))
                                for nome, tabela in TABLES.items():
                                    for chave, registro in depois[nome].items():
                                        if antes[nome].get(chave) != registro:
                                            comando = insert(tabela).values(**registro)
                                            campos = {c.name: comando.excluded[c.name] for c in tabela.columns if not c.primary_key}
                                            comando = (comando.on_conflict_do_update(index_elements=list(tabela.primary_key), set_=campos)
                                                       if campos else comando.on_conflict_do_nothing())
                                            connection.execute(comando)
                                self._commit(transaction)
                                return resultado
                            except Exception:
                                if transaction.is_active:
                                    transaction.rollback()
                                raise
                    except SQLAlchemyError as erro:
                        codigo = getattr(getattr(erro, 'orig', None), 'sqlstate', None)
                        if codigo in {'40001', '40P01'} and tentativa < 2:
                            sleep(0.025 * (tentativa + 1))
                            continue
                        raise BancoIndisponivel() from None
            finally:
                self._executando = False
