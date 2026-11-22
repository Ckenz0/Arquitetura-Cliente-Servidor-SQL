"""Composição e configuração segura da aplicação PostgreSQL."""

import pytest
from sqlalchemy import text

from server.app import create_app
from server.config import configuracao
from tests.helpers import cliente_identificado
from tests.test_persistencia_sql import banco_sql
from server.persistence.postgres import LOCK_ID


def test_postgresql_e_padrao_sem_fallback(monkeypatch):
    monkeypatch.delenv('STORAGE_BACKEND', raising=False)
    assert configuracao()['STORAGE_BACKEND'] == 'postgresql'


@pytest.mark.parametrize('backend,uri', [('memory', ''), ('postgresql', ''), ('mongodb', 'mongodb://localhost'), ('postgresql', 'postgresql://user:secret@localhost/livraria')])
def test_producao_exige_postgresql_e_tls(monkeypatch, backend, uri):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('SECRET_KEY', 'x' * 32)
    monkeypatch.setenv('ALLOWED_ORIGINS', 'https://livraria.example')
    monkeypatch.setenv('STORAGE_BACKEND', backend)
    monkeypatch.setenv('DATABASE_URL', uri)
    with pytest.raises(ValueError):
        configuracao()


@pytest.mark.parametrize('uri', ['https://servidor', 'postgresql://', 'postgresql://user:segredo@localhost'])
def test_url_invalida_nao_expoe_credenciais(uri):
    with pytest.raises(ValueError) as erro:
        configuracao({'STORAGE_BACKEND': 'postgresql', 'DATABASE_URL': uri})
    assert 'segredo' not in str(erro.value)


def config_sql(engine):
    return {'STORAGE_BACKEND': 'postgresql',
            'DATABASE_URL': engine.url.render_as_string(hide_password=False),
            'SECRET_KEY': 'chave-estavel-para-teste-de-reinicio'}


@pytest.mark.postgres
def test_api_reiniciada_preserva_dados_e_sessao(banco_sql):
    config = config_sql(banco_sql)
    app = create_app(config=config)
    cliente = cliente_identificado(app)
    token = cliente.environ_base['HTTP_AUTHORIZATION']
    assert len(cliente.get('/api/livros').json) == 12
    reserva = cliente.post('/api/reservas', json={'livro_id': '1984', 'prazo': '2099-01-01T12:00:00Z'})
    assert reserva.status_code == 201
    cliente.patch('/api/preferencias', json={'generos': ['Fantasia']})
    try:
        outra = create_app(config=config)
        novo = outra.test_client()
        novo.environ_base['HTTP_AUTHORIZATION'] = token
        estado = novo.get('/api/estado')
        assert estado.status_code == 200
        assert estado.json['cliente']['generos'] == ['Fantasia']
        assert estado.json['reservas'][0]['id'] == reserva.json['id']
        assert novo.get('/api/livros/1984').json['estoque'] == 2
        assert estado.json['fidelidade']['saldo'] == 20
        with banco_sql.connect() as connection:
            assert connection.scalar(text('SELECT count(*) FROM schema_migrations')) == 1
    finally:
        app.extensions['postgres'].fechar()
        if 'outra' in locals():
            outra.extensions['postgres'].fechar()


@pytest.mark.postgres
def test_sessao_nao_deixa_compra_parcial(banco_sql, monkeypatch):
    app = create_app(config=config_sql(banco_sql))
    def falhar(*args):
        raise RuntimeError('falha no cupom')
    monkeypatch.setattr(app.extensions['livraria'], 'conceder_cupom', falhar)
    try:
        assert app.test_client().post('/api/sessoes', json={}).status_code == 500
        with banco_sql.connect() as connection:
            assert connection.scalar(text('SELECT count(*) FROM usuarios')) == 4
    finally:
        app.extensions['postgres'].fechar()


@pytest.mark.postgres
def test_banco_indisponivel_retorna_503_sem_credenciais(banco_sql, monkeypatch):
    from sqlalchemy.exc import OperationalError
    app = create_app(config=config_sql(banco_sql))
    cliente = cliente_identificado(app)
    store = app.extensions['postgres']
    def falhar(*args, **kwargs):
        raise OperationalError('postgresql://usuario:segredo@banco', {}, Exception('falha'))
    monkeypatch.setattr(store.engine, 'connect', falhar)
    try:
        resposta = cliente.get('/api/livros')
        assert resposta.status_code == 503
        assert 'segredo' not in resposta.get_data(as_text=True)
        assert 'postgresql://' not in resposta.get_data(as_text=True)
    finally:
        store.fechar()


@pytest.mark.postgres
def test_transacao_ociosa_libera_bloqueio_apos_interrupcao_do_processo(banco_sql):
    app = create_app(config=config_sql(banco_sql))
    store = app.extensions['postgres']
    interrompida = store.engine.connect()
    try:
        interrompida.execute(text('SELECT pg_advisory_xact_lock(:lock)'), {'lock': LOCK_ID})
        reiniciada = create_app(config=config_sql(banco_sql))
        try:
            assert reiniciada.test_client().get('/api/health').status_code == 200
            cliente = cliente_identificado(reiniciada)
            assert len(cliente.get('/api/livros').json) == 12
        finally:
            reiniciada.extensions['postgres'].fechar()
    finally:
        interrompida.invalidate()
        interrompida.close()
        store.fechar()
