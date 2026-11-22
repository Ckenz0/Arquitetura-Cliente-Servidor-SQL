"""Conversão entre as linhas relacionais e a visão de trabalho do domínio."""

from copy import deepcopy
from datetime import datetime
from decimal import Decimal

from server.repositories import RepositorioEstado, RepositorioLivros
from server.persistence.schema import TABLES


def data(valor):
    return datetime.fromisoformat(valor) if valor else None


def iso(valor):
    return valor.isoformat() if valor else None


def exportar(loja):
    linhas = {nome: {} for nome in TABLES}

    def inserir(tabela, **valores):
        chave = tuple(valores[c.name] for c in TABLES[tabela].primary_key)
        linhas[tabela][chave] = deepcopy(valores)

    for ordem, livro in enumerate(loja.repositorio.todos()):
        valores = {c.name: livro[c.name] for c in TABLES['livros'].columns if c.name != 'ordem'}
        valores['preco'] = Decimal(str(livro['preco'])).quantize(Decimal('0.01'))
        inserir('livros', **valores, ordem=ordem)
        for posicao, avaliacao in enumerate(livro.get('avaliacoes', [])):
            inserir('avaliacoes_iniciais', livro_id=livro['id'], ordem=posicao,
                    cliente=avaliacao['cliente'], texto=avaliacao['texto'],
                    nota=avaliacao.get('nota'), data=data(avaliacao.get('data')))
    dados = loja.dados
    for ordem, cliente in enumerate(dados.listar('clientes')):
        usuario = cliente['id']
        inserir('usuarios', id=usuario, nome=cliente.get('nome') or None,
                email=cliente.get('email') or None, telefone=cliente.get('telefone') or None,
                notificacoes_todos=cliente['temas_notificacao'] is None, ordem=ordem)
        for posicao, genero in enumerate(cliente['generos']):
            inserir('preferencias_generos', usuario_id=usuario, genero=genero, ordem=posicao)
        for posicao, tema in enumerate(cliente['temas_notificacao'] or []):
            inserir('preferencias_temas', usuario_id=usuario, tema=tema, ordem=posicao)
        for posicao, livro in enumerate(cliente['desejos']):
            inserir('desejos', usuario_id=usuario, livro_id=livro, ordem=posicao)
        for posicao, compra in enumerate(cliente['compras']):
            inserir('compras', id=compra['id'], usuario_id=usuario, livro_id=compra['livro']['id'],
                    livro_snapshot=compra['livro'], pontos=compra['pontos'], data=data(compra['data']),
                    expira_em=data(compra['expira_em']), avisar_em=data(compra['avisar_em']),
                    avisado=compra['_avisado'], ordem=posicao)
        for posicao, cupom in enumerate(cliente['cupons']):
            inserir('cupons', usuario_id=usuario, ordem=posicao, **cupom)
        for posicao, aviso in enumerate(cliente['notificacoes']):
            inserir('notificacoes', usuario_id=usuario, ordem=posicao,
                    **(aviso | {'data': data(aviso['data'])}))
    for posicao, reserva in enumerate(dados.listar('reservas')):
        valores = dict(reserva)
        valores['usuario_id'] = valores.pop('cliente_id')
        valores['prazo'] = data(valores['prazo'])
        inserir('reservas', **valores, ordem=posicao)
    for livro, interessados in dados._colecoes['acompanhamentos'].items():
        for usuario in interessados:
            inserir('avisos_estoque', livro_id=livro, usuario_id=usuario)
    for posicao, horario in enumerate(dados.listar('horarios')):
        inserir('horarios', id=horario['id'], livreiro=horario['livreiro'],
                quando=data(horario['quando']), usuario_id=horario['cliente_id'], ordem=posicao)
    for posicao, evento in enumerate(dados.listar('eventos')):
        inserir('eventos', id=evento['id'], titulo=evento['titulo'], quando=data(evento['quando']),
                local=evento['local'], capacidade=evento['capacidade'],
                lembrar_em=data(evento['lembrar_em']), ordem=posicao)
        for usuario in evento['inscritos']:
            inserir('inscricoes_eventos', evento_id=evento['id'], usuario_id=usuario,
                    avisado=usuario in evento['avisados'])
    for posicao, clube in enumerate(dados.listar('clubes')):
        inserir('clubes', id=clube['id'], nome=clube['nome'], ordem=posicao)
        for usuario in clube['membros']:
            inserir('membros_clubes', clube_id=clube['id'], usuario_id=usuario)
        for indice, opiniao in enumerate(clube['opinioes']):
            inserir('opinioes_clubes', clube_id=clube['id'], usuario_id=opiniao['cliente'],
                    texto=opiniao['texto'], ordem=indice)
    for posicao, usuario in enumerate(dados.fila()):
        inserir('fila', usuario_id=usuario, ordem=posicao)
    inserir('loja', id=1, **dados.informacoes_loja())
    for ordem, ((livro, usuario), avaliacao) in enumerate(dados._avaliacoes.items()):
        inserir('avaliacoes', livro_id=livro, usuario_id=usuario, ordem=ordem,
                **(avaliacao | {'data': data(avaliacao['data'])}))
    for versao, migracao in getattr(dados, '_migracoes', {}).items():
        inserir('schema_migrations', versao=versao, nome=migracao['nome'],
                aplicada_em=data(migracao['aplicada_em']))
    return linhas


def restaurar(loja, linhas):
    estado = RepositorioEstado()
    estado.lock = loja._lock
    estado._migracoes = {}

    def registros(nome):
        return sorted(linhas[nome].values(), key=lambda r: r.get('ordem', 0))

    livros = []
    for registro in registros('livros'):
        livro = {k: v for k, v in registro.items() if k != 'ordem'}
        livro['preco'] = float(livro['preco'])
        livro['avaliacoes'] = []
        for avaliacao in registros('avaliacoes_iniciais'):
            if avaliacao['livro_id'] == livro['id']:
                item = {'cliente': avaliacao['cliente'], 'texto': avaliacao['texto']}
                if avaliacao['nota'] is not None:
                    item['nota'] = avaliacao['nota']
                if avaliacao['data'] is not None:
                    item['data'] = iso(avaliacao['data'])
                livro['avaliacoes'].append(item)
        livros.append(livro)
    for usuario in registros('usuarios'):
        estado.salvar('clientes', usuario['id'], {
            'id': usuario['id'], 'nome': usuario['nome'] or '', 'email': usuario['email'] or '',
            'telefone': usuario['telefone'] or '', 'generos': [],
            'temas_notificacao': None if usuario['notificacoes_todos'] else [],
            'desejos': [], 'compras': [], 'cupons': [], 'notificacoes': [],
        })
    for tabela, campo, valor in [('preferencias_generos', 'generos', 'genero'),
                                 ('preferencias_temas', 'temas_notificacao', 'tema'),
                                 ('desejos', 'desejos', 'livro_id')]:
        for registro in registros(tabela):
            estado.obter('clientes', registro['usuario_id'])[campo].append(registro[valor])
    for registro in registros('compras'):
        estado.obter('clientes', registro['usuario_id'])['compras'].append({
            'id': registro['id'], 'livro': registro['livro_snapshot'], 'pontos': registro['pontos'],
            'data': iso(registro['data']), 'expira_em': iso(registro['expira_em']),
            'avisar_em': iso(registro['avisar_em']), '_avisado': registro['avisado'],
        })
    for registro in registros('cupons'):
        estado.obter('clientes', registro['usuario_id'])['cupons'].append({
            'codigo': registro['codigo'], 'termos': registro['termos'],
        })
    for registro in registros('notificacoes'):
        estado.obter('clientes', registro['usuario_id'])['notificacoes'].append({
            k: iso(v) if k == 'data' else v for k, v in registro.items() if k not in {'ordem', 'usuario_id'}
        })
    for registro in registros('reservas'):
        reserva = {k: v for k, v in registro.items() if k not in {'ordem', 'usuario_id'}}
        reserva.update(cliente_id=registro['usuario_id'], prazo=iso(registro['prazo']))
        estado.salvar('reservas', reserva['id'], reserva)
    for registro in registros('avisos_estoque'):
        estado.obter_ou_criar('acompanhamentos', registro['livro_id'], set()).add(registro['usuario_id'])
    for registro in registros('horarios'):
        estado.salvar('horarios', registro['id'], {
            'id': registro['id'], 'livreiro': registro['livreiro'],
            'quando': iso(registro['quando']), 'cliente_id': registro['usuario_id'],
        })
    for registro in registros('eventos'):
        evento = {k: v for k, v in registro.items() if k != 'ordem'}
        evento.update(quando=iso(registro['quando']), lembrar_em=iso(registro['lembrar_em']),
                      inscritos=set(), avisados=set())
        estado.salvar('eventos', evento['id'], evento)
    for registro in registros('inscricoes_eventos'):
        evento = estado.obter('eventos', registro['evento_id'])
        evento['inscritos'].add(registro['usuario_id'])
        if registro['avisado']:
            evento['avisados'].add(registro['usuario_id'])
    for registro in registros('clubes'):
        estado.salvar('clubes', registro['id'], {
            'id': registro['id'], 'nome': registro['nome'], 'membros': set(), 'opinioes': [],
        })
    for registro in registros('membros_clubes'):
        estado.obter('clubes', registro['clube_id'])['membros'].add(registro['usuario_id'])
    for registro in registros('opinioes_clubes'):
        estado.obter('clubes', registro['clube_id'])['opinioes'].append({
            'cliente': registro['usuario_id'], 'texto': registro['texto'],
        })
    estado._fila = [registro['usuario_id'] for registro in registros('fila')]
    for registro in registros('loja'):
        estado.configurar_loja(registro['horario'], registro['lotacao'])
    for registro in registros('avaliacoes'):
        avaliacao = {k: iso(v) if k == 'data' else v for k, v in registro.items()
                     if k not in {'livro_id', 'usuario_id', 'ordem'}}
        estado.salvar_avaliacao(registro['livro_id'], registro['usuario_id'], avaliacao)
    for registro in registros('schema_migrations'):
        estado._migracoes[registro['versao']] = {
            'nome': registro['nome'], 'aplicada_em': iso(registro['aplicada_em']),
        }
    loja.dados = estado
    loja.repositorio = RepositorioLivros(livros)
