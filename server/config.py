"""Configuração externa; segredos pertencem somente ao servidor."""

import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def configuracao(overrides=None):
    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
    ambiente = (overrides or {}).get('APP_ENV', os.environ.get('APP_ENV', 'development'))
    producao = ambiente == 'production'
    chave = os.environ.get('SECRET_KEY', '')
    origens = os.environ.get('ALLOWED_ORIGINS', '')
    config = {
        'APP_ENV': ambiente,
        'SECRET_KEY': chave or (None if producao else secrets.token_hex(32)),
        'ALLOWED_ORIGINS': origens or (() if producao else (
            'http://127.0.0.1:8081', 'http://localhost:8081',
        )),
        'SESSION_TOKEN_MAX_AGE': 86400,
        'MAX_CONTENT_LENGTH': 1024 * 1024,
        'STORAGE_BACKEND': os.environ.get('STORAGE_BACKEND', 'postgresql'),
        'DATABASE_URL': os.environ.get('DATABASE_URL', '' if producao else
            'postgresql+psycopg://entrelinhas:entrelinhas-local@127.0.0.1:5433/entrelinhas'),
    }
    config.update(overrides or {})
    producao = config['APP_ENV'] == 'production'
    if producao and (not isinstance(config['SECRET_KEY'], str) or len(config['SECRET_KEY']) < 32):
        raise ValueError('Produção exige SECRET_KEY estável com pelo menos 32 caracteres.')
    origens = config['ALLOWED_ORIGINS']
    if isinstance(origens, str):
        origens = [origem.strip() for origem in origens.split(',') if origem.strip()]
    if not origens:
        raise ValueError('Informe ALLOWED_ORIGINS explicitamente.')
    for origem in origens:
        url = urlsplit(origem)
        if (url.scheme not in {'http', 'https'} or not url.netloc or url.path
                or url.query or url.fragment or url.username or url.password):
            raise ValueError('ALLOWED_ORIGINS aceita origens exatas, sem caminho ou curingas.')
        if '*' in origem:
            raise ValueError('Não use curingas em ALLOWED_ORIGINS.')
    config['ALLOWED_ORIGINS'] = tuple(origens)
    if config['STORAGE_BACKEND'] not in {'memory', 'postgresql'}:
        raise ValueError('STORAGE_BACKEND deve ser postgresql ou memory.')
    if producao and config['STORAGE_BACKEND'] != 'postgresql':
        raise ValueError('Produção exige armazenamento PostgreSQL persistente.')
    if config['STORAGE_BACKEND'] == 'postgresql':
        try:
            url = make_url(config['DATABASE_URL'])
            valida = url.drivername in {'postgresql', 'postgresql+psycopg'} and url.host and url.database and url.username
        except (ArgumentError, TypeError, ValueError):
            valida = False
        if not valida:
            raise ValueError('Informe DATABASE_URL PostgreSQL válida apenas no servidor.') from None
        if producao and url.query.get('sslmode') not in {'require', 'verify-ca', 'verify-full'}:
            raise ValueError('Produção exige conexão PostgreSQL com TLS.')
    return config
