"""Persistência relacional e consistência com PostgreSQL real."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import IntegrityError, OperationalError

from server.domain.regras import ErroLivraria
from server.services import Livraria

pytestmark = pytest.mark.postgres


@pytest.fixture
def banco_sql():
    uri = os.environ.get('TEST_DATABASE_URL')
    if not uri:
        pytest.skip('Defina TEST_DATABASE_URL para testar PostgreSQL real.')
    url = make_url(uri).set(drivername='postgresql+psycopg')
    nome = 'entrelinhas_test_' + uuid4().hex
    admin = create_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT')
    with admin.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{nome}"')
    engine = create_engine(url.set(database=nome), hide_parameters=True, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()
        assert nome.startswith('entrelinhas_test_')
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE "{nome}" WITH (FORCE)')
        admin.dispose()


def loja_persistente(engine):
    from server.persistence.postgres import PostgresStore
    loja = Livraria()
    store = PostgresStore(loja, engine)
    store.criar_schema()
    return loja


def preparar(engine):
    from server.persistence.migrations import migrar
    loja = loja_persistente(engine)
    migrar(loja)
    return loja


def prazo():
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


def test_carga_inicial_tem_quatro_perfis_e_doze_livros(banco_sql):
    loja = preparar(banco_sql)
    with banco_sql.connect() as connection:
        usuarios = connection.execute(text('SELECT nome, email, telefone FROM usuarios ORDER BY email')).mappings().all()
        assert len(usuarios) == 4
        assert len({u['email'] for u in usuarios}) == 4
        assert all(u['nome'] and u['email'].endswith('@example.com') and u['telefone'] for u in usuarios)
        assert connection.scalar(text('SELECT count(*) FROM livros')) == 12
    assert len(loja.buscar()) == 12


def test_todos_os_dados_sobrevivem_nova_instancia(banco_sql):
    loja = preparar(banco_sql)
    evento = loja.eventos()[0]['id']
    clube = loja.clubes('ana')[0]['id']
    horario = loja.estado('ana')['horarios'][0]['id']
    loja.preferencias('ana', ['Fantasia'], ['reservas', 'estoque', 'fidelidade'])
    loja.adicionar_desejo('ana', 'hobbit')
    reserva = loja.reservar('ana', '1984', prazo(), True)
    loja.marcar_pronta(reserva['id'])
    loja.acompanhar_estoque('ana', 'esgotado')
    loja.atualizar_estoque('esgotado', 2)
    loja.registrar_compra('ana', 'hobbit', 42)
    loja.conceder_cupom('ana', 'LEITURA', 'Na loja')
    loja.entrar_fila('ana')
    loja.agendar('ana', horario)
    loja.inscrever('ana', evento)
    loja.participar_clube('ana', clube)
    loja.publicar_opiniao('ana', clube, 'Vamos ler juntos.')
    loja.publicar_avaliacao('ana', '1984', 5, 'Uma ótima leitura.')
    loja.configurar_loja('Todos os dias', 25)
    outra = loja_persistente(banco_sql)
    estado = outra.estado('ana')
    assert estado['cliente']['generos'] == ['Fantasia']
    assert estado['cliente']['temas_notificacao'] == ['reservas', 'estoque', 'fidelidade']
    assert estado['reservas'][0]['status'] == 'pronta'
    assert estado['reservas'][0]['embrulho'] is True
    assert outra.livro('1984', 'ana')['estoque'] == 2
    assert outra.livro('1984', 'ana')['ja_avaliou'] is True
    assert outra.livro('1984')['avaliacoes'][-1]['nota'] == 5
    assert estado['desejos'][0]['id'] == 'hobbit'
    assert estado['fidelidade']['saldo'] == 42
    assert estado['fidelidade']['cupons'][0]['codigo'] == 'LEITURA'
    assert estado['historico'][0]['livro']['id'] == 'hobbit'
    assert estado['fila']['posicao'] == 1
    assert estado['agendamentos'][0]['id'] == horario
    assert estado['eventos'][0]['inscrito'] is True
    assert estado['clubes'][0]['participando'] is True
    assert estado['clubes'][0]['opinioes'][0]['texto'] == 'Vamos ler juntos.'
    assert estado['loja'] == {'horario': 'Todos os dias', 'lotacao': 25}
    assert {n['tema'] for n in estado['notificacoes']} == {'reservas', 'estoque', 'fidelidade'}
    assert outra.estado('bia')['reservas'] == []
    assert outra.estado('bia')['desejos'] == []
    with pytest.raises(ErroLivraria, match='já publicou'):
        outra.publicar_avaliacao('ana', '1984', 3, 'Repetida.')
    outra.cancelar_reserva('ana', reserva['id'])
    loja.cancelar_reserva('ana', reserva['id'])
    assert outra.livro('1984')['estoque'] == 3


def test_excecao_aborta_todas_as_alteracoes(banco_sql):
    loja = preparar(banco_sql)
    def operacao():
        loja.reservar('ana', '1984', prazo())
        loja.conceder_cupom('ana', 'ERRO', 'Não persistir')
        raise ValueError('interrompido')
    with pytest.raises(ValueError, match='interrompido'):
        loja.persistencia.executar(operacao)
    outra = loja_persistente(banco_sql)
    assert outra.livro('1984')['estoque'] == 3
    assert outra.reservas('ana') == []
    assert outra.fidelidade('ana')['cupons'] == []


@pytest.mark.parametrize('recurso', ['estoque', 'evento', 'horario', 'avaliacao'])
def test_concorrencia_entre_instancias(banco_sql, recurso):
    inicial = preparar(banco_sql)
    inicial.atualizar_estoque('1984', 1)
    evento = inicial.cadastrar_evento('Uma vaga', prazo(), 'Loja', capacidade=1)['id']
    horario = inicial.estado('a')['horarios'][0]['id']
    barreira = Barrier(2)
    def executar(numero):
        loja = loja_persistente(banco_sql)
        barreira.wait(timeout=10)
        try:
            if recurso == 'estoque':
                loja.reservar(str(numero), '1984', prazo())
            elif recurso == 'evento':
                loja.inscrever(str(numero), evento)
            elif recurso == 'horario':
                loja.agendar(str(numero), horario)
            else:
                loja.publicar_avaliacao('mesmo-cliente', '1984', 5, 'Uma leitura.')
            return 201
        except ErroLivraria as erro:
            return erro.status
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(executar, [1, 2])) == [201, 409]
    if recurso == 'estoque':
        assert inicial.livro('1984')['estoque'] == 0
        with banco_sql.connect() as connection:
            assert connection.scalar(text('SELECT count(*) FROM reservas')) == 1


def test_constraints_estoque_e_referencia_de_usuario(banco_sql):
    preparar(banco_sql)
    with pytest.raises(IntegrityError):
        with banco_sql.begin() as connection:
            connection.execute(text("UPDATE livros SET estoque=-1 WHERE id='1984'"))
    with pytest.raises(IntegrityError) as erro:
        with banco_sql.begin() as connection:
            connection.execute(text("INSERT INTO desejos(usuario_id,livro_id,ordem) VALUES ('inexistente','1984',0)"))
    assert erro.value.orig.sqlstate == '23503'


def test_migracao_repetida_preserva_estoque_usuarios_e_calendario(banco_sql):
    loja = preparar(banco_sql)
    loja.atualizar_estoque('1984', 9)
    eventos = loja.eventos()
    outra = preparar(banco_sql)
    assert outra.livro('1984')['estoque'] == 9
    assert outra.eventos() == eventos
    with banco_sql.connect() as connection:
        assert connection.scalar(text('SELECT count(*) FROM usuarios')) == 4
        assert connection.scalar(text('SELECT count(*) FROM schema_migrations')) == 1


def test_consulta_nao_regrava_livros(banco_sql):
    loja = preparar(banco_sql)
    with banco_sql.connect() as connection:
        antes = connection.execute(text('SELECT id, xmin::text FROM livros ORDER BY id')).all()
    loja.buscar()
    with banco_sql.connect() as connection:
        depois = connection.execute(text('SELECT id, xmin::text FROM livros ORDER BY id')).all()
    assert antes == depois


def test_commit_incerto_nao_repete_reserva(banco_sql, monkeypatch):
    from server.persistence.postgres import BancoIndisponivel
    loja = preparar(banco_sql)
    confirmar = loja.persistencia._commit
    def resposta_perdida(transaction):
        confirmar(transaction)
        raise OperationalError('commit', {}, Exception('conexão perdida'), connection_invalidated=True)
    monkeypatch.setattr(loja.persistencia, '_commit', resposta_perdida)
    with pytest.raises(BancoIndisponivel):
        loja.reservar('ana', '1984', prazo())
    outra = loja_persistente(banco_sql)
    assert outra.livro('1984')['estoque'] == 2
    assert len(outra.reservas('ana')) == 1


@pytest.mark.parametrize('recupera', [True, False])
def test_deadlock_aborta_e_repete_sem_duplicar(banco_sql, monkeypatch, recupera):
    from psycopg.errors import DeadlockDetected
    from server.persistence.postgres import BancoIndisponivel
    loja = preparar(banco_sql)
    confirmar = loja.persistencia._commit
    tentativas = []
    def confirmar_com_conflito(transaction):
        tentativas.append(1)
        if not recupera or len(tentativas) == 1:
            raise OperationalError('commit', {}, DeadlockDetected('conflito'))
        confirmar(transaction)
    monkeypatch.setattr(loja.persistencia, '_commit', confirmar_com_conflito)
    if recupera:
        loja.reservar('ana', '1984', prazo())
    else:
        with pytest.raises(BancoIndisponivel):
            loja.reservar('ana', '1984', prazo())
    monkeypatch.setattr(loja.persistencia, '_commit', confirmar)
    assert loja.livro('1984')['estoque'] == (2 if recupera else 3)
    assert len(loja.reservas('ana')) == (1 if recupera else 0)
    if not recupera:
        assert len(tentativas) == 3


def test_email_concorrente_entre_instancias(banco_sql):
    preparar(banco_sql)
    barreira = Barrier(2)
    def cadastrar(numero):
        loja = loja_persistente(banco_sql)
        barreira.wait(timeout=10)
        try:
            loja.atualizar_perfil(f'cliente-{numero}', 'Leitor', 'mesmo@example.com')
            return 200
        except ErroLivraria as erro:
            return erro.status
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(cadastrar, [1, 2])) == [200, 409]
    with banco_sql.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM usuarios WHERE email='mesmo@example.com'")) == 1


def test_instancia_se_recupera_apos_erro_de_escrita(banco_sql, monkeypatch):
    from server.persistence.postgres import BancoIndisponivel
    loja = preparar(banco_sql)
    confirmar = loja.persistencia._commit
    def falhar(transaction):
        raise IntegrityError('write', {}, Exception('falha de escrita'))
    monkeypatch.setattr(loja.persistencia, '_commit', falhar)
    with pytest.raises(BancoIndisponivel):
        loja.reservar('ana', '1984', prazo())
    monkeypatch.setattr(loja.persistencia, '_commit', confirmar)
    assert loja.livro('1984')['estoque'] == 3
    assert loja.reservas('ana') == []
    assert loja.reservar('ana', '1984', prazo())['status'] == 'pendente'
