# Persistência relacional

## Modelo de dados

O PostgreSQL armazena entidades e relacionamentos em tabelas próprias. `usuarios`
contém colunas nativas para `id`, `nome`, `email`, `telefone` e configuração de
notificações; dados pessoais não são guardados em um documento genérico.

| Tabelas | Conteúdo |
| --- | --- |
| `usuarios`, `preferencias_generos`, `preferencias_temas` | Perfil e preferências |
| `livros`, `avaliacoes_iniciais` | Catálogo, estoque, preço e avaliações ilustrativas |
| `reservas`, `avisos_estoque`, `desejos` | Reservas e interesse em livros |
| `compras`, `cupons`, `notificacoes` | Histórico, fidelidade e avisos |
| `horarios`, `fila`, `loja` | Atendimento e funcionamento |
| `eventos`, `inscricoes_eventos` | Agenda e inscrições |
| `clubes`, `membros_clubes`, `opinioes_clubes` | Comunidade |
| `avaliacoes` | Notas e comentários de usuários |
| `schema_migrations` | Versões de inicialização aplicadas |

Chaves estrangeiras mantêm as referências entre usuários, livros e operações.
Restrições `CHECK` impedem estoque, pontos e capacidade negativos e notas fora de
1 a 5. E-mails são normalizados e exclusivos; cada usuário avalia um livro uma vez.
Preços usam `NUMERIC(12,2)` e datas usam `TIMESTAMP WITH TIME ZONE`.

O único `JSONB` é `compras.livro_snapshot`: uma cópia histórica imutável dos dados
do livro no momento da compra, independente das alterações futuras no catálogo.
As entidades operacionais e suas relações continuam em colunas e tabelas SQL.

## Transações

`PostgresStore` envolve cada operação externa do serviço em uma transação. Antes
de ler o estado, obtém um advisory lock transacional PostgreSQL compartilhado entre
instâncias. Chamadas internas reutilizam a mesma operação; o bloqueio local protege
a visão de trabalho entre threads, e o banco coordena processos diferentes.

Depois de executar as regras, somente as linhas alteradas são gravadas, respeitando
a ordem das chaves estrangeiras. Reserva e baixa de estoque são confirmadas juntas;
cancelamento e devolução do exemplar também. Erros provocam rollback.

Apenas deadlocks e falhas de serialização explicitamente abortadas são repetidos,
até três tentativas. Perda de conexão ou commit incerto retorna 503 sem reexecutar
a mutação. Consulte o estado antes de repetir uma operação após falha de comunicação.
Erros públicos não incluem a URL, parâmetros SQL ou credenciais.

## Migração e carga inicial

```powershell
.venv\Scripts\python.exe -m server.migrate
```

O esquema é criado transacionalmente pelos metadados SQLAlchemy, sob o mesmo
bloqueio de migração. A carga v1 e seu marcador são confirmados juntos: 12 livros,
quatro usuários fictícios, loja, horários, eventos e clube. Uma nova execução
preserva dados e datas já existentes. Não há importação automática de dados
privados de outras implantações.

Os quatro perfis iniciais são Ana Silva, Bruno Costa, Carla Souza e Diego Lima,
com endereços do domínio `example.com` e telefones ilustrativos. Eles não fornecem
credenciais de acesso. Novas sessões usam identificadores próprios, e o cadastro
de informações pessoais acontece em **Meu perfil**.

Com uma conexão autenticada do `psql`:

```sql
SELECT id, nome, email, telefone FROM usuarios WHERE email IS NOT NULL;
SELECT count(*) FROM livros;
SELECT * FROM schema_migrations;
SELECT r.id, u.nome, l.titulo, r.status
FROM reservas r
JOIN usuarios u ON u.id = r.usuario_id
JOIN livros l ON l.id = r.livro_id;
```

## Limites operacionais

A leitura integral das tabelas e o bloqueio global simplificam a adaptação das
regras existentes, mas limitam concorrência e volume. O timeout de espera do lock
é quatro segundos e o de cada instrução é oito segundos. Requisições que excedem
os limites recebem falha explícita; não há fallback para memória em produção.
O pool é limitado a quatro conexões, com até duas extras temporárias por processo.

Transações ociosas são encerradas pelo PostgreSQL após 15 segundos, liberando
bloqueios deixados por um processo interrompido. Somente a criação do esquema
aguarda até 20 segundos pelo bloqueio, com limite de 25 segundos por instrução,
para permitir essa limpeza durante um reinício.

Para alto volume, adote consultas por usuário/agregado, paginação e bloqueios mais
específicos. Alterações futuras de esquema precisam de migrações versionadas;
`create_all` não altera colunas de uma tabela já existente.
