"""Composição da API. O cliente estático é servido por outro processo."""

import os
import logging

from flask import Flask

from server.controllers import registrar_controladores
from server.demonstracao import criar_demonstracao
from server.config import configuracao
from server.http import registrar_http
from server.documentation import registrar_documentacao


def create_app(livraria=None, config=None):
    app = Flask(__name__, static_folder=None, template_folder=None)
    app.config.update(configuracao(config))
    app.logger.setLevel(logging.INFO)
    app.json.ensure_ascii = False
    demonstracao = livraria is None
    if demonstracao and app.config['STORAGE_BACKEND'] == 'postgresql':
        from server.persistence.factory import criar_livraria_postgres
        loja, store = criar_livraria_postgres(app.config)
        app.extensions['postgres'] = store
    else:
        loja = criar_demonstracao() if demonstracao else livraria
    app.extensions["livraria"] = loja

    registrar_http(app)
    registrar_controladores(app, demonstracao=demonstracao)
    registrar_documentacao(app)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    app = create_app()
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', '5001')), debug=False)
