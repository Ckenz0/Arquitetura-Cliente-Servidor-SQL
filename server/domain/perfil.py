"""Validação dos dados do perfil, sem alterar identidade ou autenticação."""

import re

from server.domain.regras import ErroLivraria, texto_obrigatorio


def validar_nome_email(nome, email):
    nome = texto_obrigatorio(nome, 'o nome completo')
    email = texto_obrigatorio(email, 'o e-mail').casefold()
    if len(nome) > 120 or any(ord(c) < 32 for c in nome):
        raise ErroLivraria('Informe um nome com até 120 caracteres.')
    if len(email) > 254 or not re.fullmatch(r'[^@\s\x00]+@[^@\s\x00]+\.[^@\s\x00]+', email):
        raise ErroLivraria('Informe um e-mail válido com até 254 caracteres.')
    return nome, email


def validar_telefone(telefone):
    if not isinstance(telefone, str) or not re.fullmatch(r'[\d +().-]{0,32}', telefone):
        raise ErroLivraria('Informe um telefone válido com até 32 caracteres.')
    return telefone.strip()
