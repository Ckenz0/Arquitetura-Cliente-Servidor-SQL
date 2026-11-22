"""Esquema relacional: entidades, associações e restrições PostgreSQL."""

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, MetaData,
    Numeric, String, Table, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()


def pk(nome='id'):
    return Column(nome, Text, primary_key=True)


def fk(nome, destino, *, primary=False, nullable=False):
    return Column(nome, Text, ForeignKey(destino), primary_key=primary, nullable=nullable, index=True)


def coluna(nome, tipo=Text, *, nullable=False):
    return Column(nome, tipo, nullable=nullable)


usuarios = Table('usuarios', metadata, pk(), coluna('nome', String(120), nullable=True),
    coluna('email', String(254), nullable=True), coluna('telefone', String(32), nullable=True),
    coluna('notificacoes_todos', Boolean), coluna('ordem', Integer),
    UniqueConstraint('email', name='uq_usuarios_email'),
    CheckConstraint('email IS NULL OR email = lower(email)', name='email_normalizado'))
livros = Table('livros', metadata, pk(), coluna('titulo'), coluna('autor'), coluna('ano', Integer),
    coluna('genero'), coluna('estoque', Integer), coluna('lancamento', Boolean),
    coluna('preco', Numeric(12, 2)), coluna('codigo'), coluna('secao'), coluna('prateleira'),
    coluna('sinopse'), coluna('ordem', Integer), UniqueConstraint('codigo'),
    CheckConstraint('estoque >= 0'), CheckConstraint('preco >= 0'))
avaliacoes_iniciais = Table('avaliacoes_iniciais', metadata,
    fk('livro_id', 'livros.id', primary=True), Column('ordem', Integer, primary_key=True),
    coluna('cliente'), coluna('texto'), coluna('nota', Integer, nullable=True),
    coluna('data', DateTime(timezone=True), nullable=True))
preferencias_generos = Table('preferencias_generos', metadata,
    fk('usuario_id', 'usuarios.id', primary=True), pk('genero'), coluna('ordem', Integer))
preferencias_temas = Table('preferencias_temas', metadata,
    fk('usuario_id', 'usuarios.id', primary=True), pk('tema'), coluna('ordem', Integer))
desejos = Table('desejos', metadata,
    fk('usuario_id', 'usuarios.id', primary=True), fk('livro_id', 'livros.id', primary=True),
    coluna('ordem', Integer))
compras = Table('compras', metadata, pk(), fk('usuario_id', 'usuarios.id'), fk('livro_id', 'livros.id'),
    coluna('livro_snapshot', JSONB), coluna('pontos', Integer), coluna('data', DateTime(timezone=True)),
    coluna('expira_em', DateTime(timezone=True), nullable=True),
    coluna('avisar_em', DateTime(timezone=True), nullable=True), coluna('avisado', Boolean),
    coluna('ordem', Integer), CheckConstraint('pontos >= 0'))
cupons = Table('cupons', metadata, fk('usuario_id', 'usuarios.id', primary=True),
    Column('ordem', Integer, primary_key=True), coluna('codigo'), coluna('termos'))
notificacoes = Table('notificacoes', metadata, pk(), fk('usuario_id', 'usuarios.id'),
    coluna('tema'), coluna('mensagem'), coluna('data', DateTime(timezone=True)), coluna('ordem', Integer))
reservas = Table('reservas', metadata, pk(), fk('usuario_id', 'usuarios.id'), fk('livro_id', 'livros.id'),
    coluna('titulo'), coluna('prazo', DateTime(timezone=True)), coluna('embrulho', Boolean),
    coluna('status'), coluna('ordem', Integer), CheckConstraint("status IN ('pendente','pronta','cancelada')"))
avisos_estoque = Table('avisos_estoque', metadata,
    fk('livro_id', 'livros.id', primary=True), fk('usuario_id', 'usuarios.id', primary=True))
horarios = Table('horarios', metadata, pk(), coluna('livreiro'), coluna('quando', DateTime(timezone=True)),
    fk('usuario_id', 'usuarios.id', nullable=True), coluna('ordem', Integer))
eventos = Table('eventos', metadata, pk(), coluna('titulo'), coluna('quando', DateTime(timezone=True)),
    coluna('local'), coluna('capacidade', Integer, nullable=True),
    coluna('lembrar_em', DateTime(timezone=True), nullable=True), coluna('ordem', Integer),
    CheckConstraint('capacidade IS NULL OR capacidade >= 0'))
inscricoes_eventos = Table('inscricoes_eventos', metadata,
    fk('evento_id', 'eventos.id', primary=True), fk('usuario_id', 'usuarios.id', primary=True),
    coluna('avisado', Boolean))
clubes = Table('clubes', metadata, pk(), coluna('nome'), coluna('ordem', Integer))
membros_clubes = Table('membros_clubes', metadata,
    fk('clube_id', 'clubes.id', primary=True), fk('usuario_id', 'usuarios.id', primary=True))
opinioes_clubes = Table('opinioes_clubes', metadata,
    fk('clube_id', 'clubes.id', primary=True), Column('ordem', Integer, primary_key=True),
    fk('usuario_id', 'usuarios.id'), coluna('texto'))
fila = Table('fila', metadata, fk('usuario_id', 'usuarios.id', primary=True),
    coluna('ordem', Integer), CheckConstraint('ordem >= 0'))
loja = Table('loja', metadata, Column('id', Integer, primary_key=True), coluna('horario'),
    coluna('lotacao', Integer), CheckConstraint('id=1'), CheckConstraint('lotacao >= 0'))
avaliacoes = Table('avaliacoes', metadata, pk(), fk('livro_id', 'livros.id'),
    fk('usuario_id', 'usuarios.id'), coluna('cliente'), coluna('nota', Integer),
    coluna('texto'), coluna('data', DateTime(timezone=True)), coluna('ordem', Integer),
    UniqueConstraint('livro_id', 'usuario_id'), CheckConstraint('nota BETWEEN 1 AND 5'))
schema_migrations = Table('schema_migrations', metadata, pk('versao'), coluna('nome'),
    coluna('aplicada_em', DateTime(timezone=True)))

TABLES = {table.name: table for table in metadata.sorted_tables}
