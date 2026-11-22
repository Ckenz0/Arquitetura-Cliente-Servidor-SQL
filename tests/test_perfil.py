"""Cadastro de informações pessoais restrito à própria sessão."""

import pytest
from sqlalchemy import text
from playwright.sync_api import expect

from server.app import create_app
from tests.helpers import cliente_identificado
from tests.test_config_sql import config_sql
from tests.test_persistencia_sql import banco_sql


def test_perfil_normaliza_dados_e_isola_sessoes():
    app = create_app()
    ana, bia = cliente_identificado(app), cliente_identificado(app)
    assert ana.get('/api/perfil').status_code == 200
    resposta = ana.patch('/api/perfil', json={'nome': "  Ana D'Ávila  ", 'email': ' ANA@EXAMPLE.COM ', 'telefone': '+55 11 99999-0000'})
    assert resposta.status_code == 200
    assert resposta.json['nome'] == "Ana D'Ávila"
    assert resposta.json['email'] == 'ana@example.com'
    assert bia.get('/api/perfil').json['email'] == ''
    assert app.test_client().get('/api/perfil').status_code == 401
    assert app.test_client().get('/api/usuarios').status_code == 404
    assert ana.get('/api/estado').json['cliente']['nome'] == "Ana D'Ávila"


@pytest.mark.parametrize('dados', [
    {'nome': '', 'email': 'a@example.com'},
    {'nome': 'A' * 121, 'email': 'a@example.com'},
    {'nome': 'Ana', 'email': 'invalido'},
    {'nome': 'Ana', 'email': 'a\x00@example.com'},
    {'nome': 'Ana', 'email': 'a@example.com', 'telefone': 'DROP TABLE'},
    {'nome': 'Ana', 'email': 'a@example.com', 'telefone': None},
    {'nome': 'Ana', 'email': 'a@example.com', 'cliente_id': 'outra-pessoa'},
])
def test_perfil_invalido_nao_altera_dados(dados):
    cliente = cliente_identificado(create_app())
    antes = cliente.get('/api/perfil').json
    assert cliente.patch('/api/perfil', json=dados).status_code == 400
    assert cliente.get('/api/perfil').json == antes


def test_email_duplicado_e_recusado_sem_alteracao():
    app = create_app()
    ana, bia = cliente_identificado(app), cliente_identificado(app)
    assert ana.patch('/api/perfil', json={'nome': 'Ana', 'email': 'ana@example.com'}).status_code == 200
    assert bia.patch('/api/perfil', json={'nome': 'Bia', 'email': 'ANA@example.com'}).status_code == 409
    assert bia.get('/api/perfil').json['nome'] == ''


def test_preflight_patch_encontra_metodo_quando_get_compartilha_rota():
    resposta = create_app().test_client().options('/api/perfil', headers={
        'Origin': 'http://127.0.0.1:8081',
        'Access-Control-Request-Method': 'PATCH',
        'Access-Control-Request-Headers': 'authorization, content-type',
    })
    assert resposta.status_code == 204
    assert 'PATCH' in resposta.headers['Access-Control-Allow-Methods']


@pytest.mark.postgres
def test_perfil_esta_em_colunas_sql_e_sobrevive_reinicio(banco_sql):
    config = config_sql(banco_sql)
    app = create_app(config=config)
    cliente = cliente_identificado(app)
    try:
        assert cliente.patch('/api/perfil', json={'nome': 'Nova Leitora', 'email': 'nova@example.com', 'telefone': '11999990000'}).status_code == 200
        outra = create_app(config=config)
        novo = outra.test_client()
        novo.environ_base['HTTP_AUTHORIZATION'] = cliente.environ_base['HTTP_AUTHORIZATION']
        assert novo.get('/api/perfil').json['nome'] == 'Nova Leitora'
        with banco_sql.connect() as connection:
            row = connection.execute(text("SELECT nome,email,telefone FROM usuarios WHERE email='nova@example.com'")).mappings().one()
            assert dict(row) == {'nome': 'Nova Leitora', 'email': 'nova@example.com', 'telefone': '11999990000'}
    finally:
        app.extensions['postgres'].fechar()
        if 'outra' in locals():
            outra.extensions['postgres'].fechar()


@pytest.mark.interface
@pytest.mark.postgres
@pytest.mark.parametrize('servidores', ['postgresql'], indirect=True)
@pytest.mark.parametrize('largura,altura', [(1366, 900), (390, 844)])
def test_formulario_de_perfil_salva_preserva_rascunho_e_limpa_ao_trocar_sessao(page, servidores, largura, altura):
    page.set_viewport_size({'width': largura, 'height': altura})
    page.goto(servidores.cliente_url)
    expect(page.locator('.book-card')).to_have_count(12)
    page.locator('nav [data-tab="perfil"]').click()
    nome = page.get_by_label('Nome completo', exact=True)
    email = page.get_by_label('E-mail', exact=True)
    telefone = page.get_by_label('Telefone (opcional)', exact=True)
    nome.fill('Rascunho da leitora')
    email.fill('leitora@example.com')
    telefone.fill('11999990000')
    page.evaluate("async () => {await livrariaApi('/api/desejos','POST',{livro_id:'hobbit'}); await atualizar();}")
    expect(nome).to_have_value('Rascunho da leitora')
    page.get_by_role('button', name='Salvar meus dados', exact=True).click()
    expect(page.locator('#toast')).to_have_text('Seus dados foram salvos.')
    page.reload()
    page.locator('nav [data-tab="perfil"]').click()
    expect(nome).to_have_value('Rascunho da leitora')
    expect(email).to_have_value('leitora@example.com')
    page.evaluate('async () => {await novaSessaoLivraria(); await atualizar();}')
    expect(nome).to_have_value('')
    expect(email).to_have_value('')
