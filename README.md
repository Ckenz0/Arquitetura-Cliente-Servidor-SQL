# Entrelinhas

Livraria cliente-servidor com API Flask, PostgreSQL 17 e frontend independente.
O catálogo, os perfis, as reservas, a fidelidade e a comunidade usam persistência
relacional, com transações e integridade referencial.

[Abrir a livraria](https://salmon-field-0cba0d410.3.azurestaticapps.net) ·
[API](https://entrelinhas-sql-api-ckenz0.azurewebsites.net) ·
[Documentação interativa](https://entrelinhas-sql-api-ckenz0.azurewebsites.net/docs) ·
[Health check](https://entrelinhas-sql-api-ckenz0.azurewebsites.net/api/health)

## Arquitetura

```text
Navegador ⇄ HTTP/JSON + Bearer ⇄ API Flask
                                  ↓
                          Serviços e domínio
                                  ↓
                       Unidade de trabalho SQLAlchemy
                                  ↓
                           PostgreSQL 17
```

O cliente está em `client/`, a API em `server/` e o contrato HTTP em
[server/openapi.yaml](server/openapi.yaml). `/docs` abre o Swagger UI e
`/openapi.json` publica o mesmo contrato, apontando para o servidor atual.

## Funcionalidades

- Catálogo de 12 livros, busca, filtros, detalhes e avaliações.
- Cadastro e atualização de nome, e-mail e telefone em **Meu perfil**.
- Reservas com prazo e embrulho, alteração, confirmação e cancelamento.
- Fila virtual, atendimento com livreiro e informações da loja.
- Compras ilustrativas, pontos, cartão fidelidade, cupons e notificações.
- Eventos, inscrições, clubes de leitura e opiniões.
- Lista de desejos, recomendações e preferências de leitura.

A carga inicial inclui quatro perfis fictícios com e-mails distintos do domínio
`example.com`. Os dados pessoais pertencem à própria sessão; não há listagem
pública de usuários ou e-mails. Consulte o [modelo relacional](docs/persistence.md).

## Executar com Docker

```powershell
docker compose up --build -d
```

Abra `http://127.0.0.1:8081`. A API usa `http://127.0.0.1:5001`, a documentação
fica em `http://127.0.0.1:5001/docs` e o PostgreSQL local usa a porta `5433`.
O volume `postgres-data` mantém os dados quando os contêineres são recriados.

```powershell
docker compose down
```

O comando preserva o volume; removê-lo elimina o banco local. As credenciais
padrão do Compose servem apenas para desenvolvimento.

## Executar com Python

Use Python 3.12:

```powershell
docker compose up -d --wait postgres
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Defina uma `SECRET_KEY` estável no `.env` e execute:

```powershell
.venv\Scripts\python.exe -m server.migrate
.venv\Scripts\python.exe -m server.app
```

Em outro terminal:

```powershell
.venv\Scripts\python.exe -m http.server 8081 --bind 127.0.0.1 --directory client
```

`DATABASE_URL` é lida somente pelo servidor. Nunca coloque a conexão do banco
em `client/config.js`. As migrações também executam ao iniciar a API: repeti-las
não redefine perfis, estoque, reservas ou calendário.

## Validação

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://entrelinhas:entrelinhas-local@127.0.0.1:5433/entrelinhas'
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m openapi_spec_validator server/openapi.yaml
```

Os testes de integração criam e removem bancos temporários independentes. A URL
de testes precisa de um usuário local com permissão `CREATEDB`; a suíte não usa
o banco publicado. Sem `TEST_DATABASE_URL`, as integrações são puladas explicitamente.
Para o navegador, use Chrome/Edge instalado ou execute
`.venv\Scripts\python.exe -m playwright install chromium`.

Consulte as [evidências de validação](docs/validation.md) e o
[guia de publicação na Azure](docs/deploy.md).

## Identidade e limites

A identidade é uma sessão anônima assinada, válida por 24 horas, sem login ou senha.
Nome e e-mail não autenticam nem recuperam contas. Uma nova sessão cria outro perfil;
no prazo de validade, manter a mesma chave permite continuar após reiniciar a API.
Os dados continuam no PostgreSQL mesmo após a sessão expirar.

Não há pagamentos, caixa ou notificações externas. Para preservar as regras do MVP,
a unidade de trabalho lê as tabelas e serializa operações com um bloqueio transacional.
O modelo prioriza consistência em pequeno volume; consultas específicas, paginação e
bloqueios por agregado são necessários para crescer.
