"""Migração relacional idempotente: catálogo, usuários e dados iniciais."""

from copy import deepcopy
from datetime import datetime, timezone

from server.demonstracao import criar_demonstracao
from server.repositories import RepositorioLivros


def _livros_adicionais():
    titulos = [
        ('dom-casmurro', 'Dom Casmurro', 'Machado de Assis', 1899, 'Romance',
         'Memória, ciúme e os silêncios da história de Bento Santiago.'),
        ('pequeno-principe', 'O Pequeno Príncipe', 'Antoine de Saint-Exupéry', 1943, 'Infantojuvenil',
         'Uma viagem entre planetas, encontros e descobertas sobre a amizade.'),
        ('duna', 'Duna', 'Frank Herbert', 1965, 'Ficção científica',
         'No planeta Arrakis, uma disputa envolve poder, ecologia e o futuro de um povo.'),
        ('capitaes-areia', 'Capitães da Areia', 'Jorge Amado', 1937, 'Romance',
         'Um grupo de meninos encontra amizade e resistência nas ruas de Salvador.'),
        ('hora-estrela', 'A Hora da Estrela', 'Clarice Lispector', 1977, 'Romance',
         'A vida de Macabéa, contada por um narrador que também questiona a própria escrita.'),
        ('quarto-despejo', 'Quarto de Despejo', 'Carolina Maria de Jesus', 1960, 'Biografia',
         'Registros cotidianos de uma escritora na favela do Canindé, em São Paulo.'),
        ('orgulho-preconceito', 'Orgulho e Preconceito', 'Jane Austen', 1813, 'Romance',
         'Elizabeth Bennet enfrenta expectativas sociais e primeiras impressões.'),
    ]
    return [
        {'id': identificador, 'titulo': titulo, 'autor': autor, 'ano': ano,
         'genero': genero, 'estoque': 4, 'lancamento': False, 'preco': 44.90,
         'codigo': f'97800000000{numero:02d}', 'secao': genero, 'prateleira': 'D1',
         'sinopse': sinopse, 'avaliacoes': []}
        for numero, (identificador, titulo, autor, ano, genero, sinopse) in enumerate(titulos, 3)
    ]


def migrar(loja):
    """Carga e marcador são confirmados na mesma transação, sem redefinir dados."""
    def aplicar():
        migracoes = getattr(loja.dados, '_migracoes', {})
        if set(migracoes) - {'1'}:
            raise ValueError('O banco exige uma versão mais recente da aplicação.')
        if '1' in migracoes:
            return
        demonstracao = criar_demonstracao()
        atuais = list(loja.repositorio.todos())
        ids = {livro['id'] for livro in atuais}
        iniciais = [*demonstracao.repositorio.todos(), *_livros_adicionais()]
        loja.repositorio = RepositorioLivros(atuais + [livro for livro in iniciais if livro['id'] not in ids])
        if loja.dados.informacoes_loja()['horario'] == 'Não informado':
            loja.configurar_loja('Seg–Sáb, 09h às 19h', 12)
        for tipo in ('horarios', 'eventos', 'clubes'):
            if not loja.dados.listar(tipo):
                for valor in demonstracao.dados.listar(tipo):
                    loja.dados.salvar(tipo, valor['id'], deepcopy(valor))
        for numero, (nome, email, telefone) in enumerate([
            ('Ana Silva', 'ana.silva@example.com', '+55 11 90000-0001'),
            ('Bruno Costa', 'bruno.costa@example.com', '+55 11 90000-0002'),
            ('Carla Souza', 'carla.souza@example.com', '+55 11 90000-0003'),
            ('Diego Lima', 'diego.lima@example.com', '+55 11 90000-0004'),
        ], 1):
            cliente = loja._cliente(f'{numero:032x}')
            cliente.update(nome=nome, email=email, telefone=telefone)
        loja.dados._migracoes = migracoes | {
            '1': {'nome': 'catalogo-e-dados-completos',
                  'aplicada_em': datetime.now(timezone.utc).isoformat()},
        }
    loja.persistencia.executar(aplicar)
