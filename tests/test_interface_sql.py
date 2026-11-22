"""Interface original acessando a API persistente por HTTP real."""

import pytest
from playwright.sync_api import expect

from server.app import create_app
from tests.test_persistencia_sql import banco_sql


@pytest.mark.interface
@pytest.mark.postgres
@pytest.mark.parametrize('servidores', ['postgresql'], indirect=True)
@pytest.mark.parametrize('largura,altura', [(1366, 900), (390, 844)])
def test_interface_preserva_dados_apos_recriar_api(page, servidores, largura, altura):
    page.set_viewport_size({'width': largura, 'height': altura})
    erros = []
    page.on('pageerror', lambda erro: erros.append(str(erro)))
    page.goto(servidores.cliente_url)
    expect(page.locator('.book-card')).to_have_count(12)
    page.locator('#busca').fill('Duna')
    expect(page.locator('.book-card')).to_have_count(1)
    page.locator('#busca').fill('')
    page.evaluate('''async () => {
      await livrariaApi('/api/desejos', 'POST', {livro_id:'hobbit'});
      await livrariaApi('/api/preferencias', 'PATCH', {generos:['Fantasia']});
      await livrariaApi('/api/reservas', 'POST', {livro_id:'1984',prazo:'2099-01-01T12:00:00Z'});
    }''')
    nova = create_app(config=dict(servidores.app.config))
    servidores.api.app = nova
    try:
        page.reload()
        expect(page.locator('.book-card')).to_have_count(12)
        estado = page.evaluate("async () => livrariaApi('/api/estado')")
        assert estado['cliente']['generos'] == ['Fantasia']
        assert estado['desejos'][0]['id'] == 'hobbit'
        assert estado['reservas'][0]['livro_id'] == '1984'
        assert next(l for l in estado['livros'] if l['id'] == '1984')['estoque'] == 2
        assert not erros
    finally:
        nova.extensions['postgres'].fechar()
