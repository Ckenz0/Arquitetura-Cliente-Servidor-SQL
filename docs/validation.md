# Validação

Ambiente de teste: Python 3.12 e PostgreSQL 17 real, com bancos temporários
independentes. A interface é exercitada em navegador real nas dimensões
1366 × 900 e 390 × 844.

A suíte completa passou com **234 testes**, incluindo persistência, concorrência,
perfil, contrato e navegador. O build Docker também foi executado; o perfil
permaneceu disponível na mesma sessão após reiniciar o contêiner da API.

## Publicação

Verificação em 22 de novembro de 2026:

- O [workflow do frontend](https://github.com/Ckenz0/Arquitetura-Cliente-Servidor-SQL/actions/runs/45071616295)
  concluiu a publicação; os arquivos públicos respondem HTTP 200.
- O [workflow da API](https://github.com/Ckenz0/Arquitetura-Cliente-Servidor-SQL/actions/runs/45071616319)
  validou e publicou o pacote. A verificação pública final falhou: o App Service
  retornou `QuotaExceeded`/`Exceeded`, com HTTP 403 da própria plataforma.
- A conexão direta com o PostgreSQL da Azure, usando o login da aplicação e TLS,
  confirmou 12 livros e quatro perfis nomeados. A configuração de conexão do
  App Service foi conferida com essa conexão.

A execução pública da API, do Swagger UI e o teste de persistência após reiniciar
o App Service permanecem pendentes da liberação da cota. A verificação local não
substitui essas verificações públicas. Consulte as opções de plano em
[deploy](deploy.md).

## Cobertura

- Regras atuais da livraria, API, Bearer, CORS e contrato OpenAPI.
- Catálogo com 12 livros e quatro perfis nomeados com e-mails distintos.
- Perfis salvos em colunas SQL, normalização, validação, duplicação e isolamento.
- Reservas, estoque, compras, cupons, notificações, fila, agendamentos, eventos,
  clubes, opiniões, desejos e preferências após uma nova instância.
- Rollback sem alterações parciais e recuperação da instância após falha de escrita.
- Concorrência entre instâncias para estoque, vagas, agendamento, avaliações e e-mail.
- Deadlocks com repetição limitada e commit incerto sem repetir a reserva.
- Chaves estrangeiras e restrições de estoque verificadas no banco.
- Carga inicial idempotente e leituras sem regravar linhas.
- Perfil com rascunho preservado durante atualização e limpo ao trocar identidade.
- Swagger UI público, contrato JSON e execução de requisições pelo navegador.
- Empacotamento sem segredos, instruções locais ou caches.

## Reproduzir

```powershell
docker compose up -d --wait postgres
$env:TEST_DATABASE_URL='postgresql+psycopg://entrelinhas:entrelinhas-local@127.0.0.1:5433/entrelinhas'
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m openapi_spec_validator server/openapi.yaml
docker compose config --quiet
```

Os testes criam bancos com prefixo `entrelinhas_test_` e removem somente esses
bancos ao terminar. Use um usuário local com `CREATEDB`. O banco publicado não
é usado pela suíte.
