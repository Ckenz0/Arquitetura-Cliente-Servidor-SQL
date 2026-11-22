# Validação

Ambiente de teste: Python 3.12 e PostgreSQL 17 real, com bancos temporários
independentes. A interface é exercitada em navegador real nas dimensões
1366 × 900 e 390 × 844.

A suíte completa passou com **235 testes**, incluindo persistência, concorrência,
perfil, contrato e navegador. O build Docker também foi executado; o perfil
permaneceu disponível na mesma sessão após reiniciar o contêiner da API.

## Publicação

Verificação em 22 de novembro de 2026:

- O [workflow do frontend](https://github.com/Ckenz0/Arquitetura-Cliente-Servidor-SQL/actions/runs/45074671005)
  concluiu a validação e a publicação; os arquivos públicos respondem HTTP 200.
- O [workflow da API](https://github.com/Ckenz0/Arquitetura-Cliente-Servidor-SQL/actions/runs/45074671014)
  concluiu a validação, a publicação e a verificação pública do banco.
- A API usa o plano B1 com Always On. `/api/health`, `/docs` e `/openapi.json`
  responderam HTTP 200. No Swagger UI, a criação de sessão retornou 201 e a
  consulta autenticada retornou os 12 livros, sem erros de JavaScript.
- A conexão direta com o PostgreSQL da Azure, usando o login da aplicação e TLS,
  confirmou 12 livros e quatro perfis nomeados. A configuração de conexão do
  App Service foi conferida com essa conexão.

O App Service foi reiniciado após a publicação. Os logs da Azure confirmaram a
inicialização do novo contêiner às 22:00:23 UTC. Após a troca, foram conferidos
perfil, reserva, estoque, preferências, desejos, avaliação, fidelidade, cupom,
fila, agendamento, inscrição em evento e participação e opinião em clube.
O cancelamento repetido devolveu o exemplar apenas uma vez.

Os navegadores desktop e celular mantiveram o perfil na mesma sessão após o
reinício, sem erros de JavaScript ou rolagem horizontal. O Swagger UI foi
exercitado novamente. Os cinco perfis criados especificamente para essa
verificação e suas interações foram removidos; os quatro perfis iniciais e o
estoque original foram preservados. Consulte a configuração em [deploy](deploy.md).

## Cobertura

- Regras atuais da livraria, API, Bearer, CORS e contrato OpenAPI.
- Catálogo com 12 livros e quatro perfis nomeados com e-mails distintos.
- Perfis salvos em colunas SQL, normalização, validação, duplicação e isolamento.
- Reservas, estoque, compras, cupons, notificações, fila, agendamentos, eventos,
  clubes, opiniões, desejos e preferências após uma nova instância.
- Rollback sem alterações parciais e recuperação da instância após falha de escrita.
- Reinício com conexão interrompida, liberação de transação ociosa e recuperação
  do bloqueio de inicialização em PostgreSQL real.
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
