# Deploy na Azure

A aplicação usa três serviços independentes: Static Web Apps para o frontend,
App Service Linux para a API Flask e Azure Database for PostgreSQL Flexible Server.
O navegador acessa somente a API, por HTTPS; a conexão do banco fica no servidor.

## Recursos

Grupo: `livraria-entrelinhas-sql`.

| Componente | Nome | Configuração |
| --- | --- | --- |
| Frontend | `entrelinhas-sql-front-ckenz0` | Static Web Apps Free, Central US |
| API | `entrelinhas-sql-api-ckenz0` | Python 3.12, Brazil South |
| Plano | `entrelinhas-sql-plan` | App Service Linux Basic B1 |
| PostgreSQL | `entrelinhas-sql-pg-ckenz0` | PostgreSQL 17, Burstable B1ms, 32 GB |
| Identidade de CI | `entrelinhas-sql-github` | OIDC, acesso somente à nova API |

O PostgreSQL tem armazenamento e computação próprios; o custo depende da assinatura.
O template não pressupõe gratuidade desse serviço. Backup local por sete dias,
sem alta disponibilidade e sem expansão automática de armazenamento.

O ambiente publicado usa `B1`, que é pago. O template mantém `F1` como padrão
para novas instalações; esse plano gratuito tem cotas de execução que podem
interromper o aplicativo com HTTP 403 da Azure. Para preservar o plano B1 ao
reaplicar o template neste ambiente, informe `appServiceSku` explicitamente.
O template ativa Always On no B1 para manter a API inicializada.

- [Frontend](https://salmon-field-0cba0d410.3.azurestaticapps.net).
- [API](https://entrelinhas-sql-api-ckenz0.azurewebsites.net).
- [Documentação interativa](https://entrelinhas-sql-api-ckenz0.azurewebsites.net/docs).
- [Contrato OpenAPI](https://entrelinhas-sql-api-ckenz0.azurewebsites.net/openapi.json).
- [Health check](https://entrelinhas-sql-api-ckenz0.azurewebsites.net/api/health).

Consulte os domínios reais após provisionar, sem deduzi-los do nome do recurso:

```powershell
az webapp show -g livraria-entrelinhas-sql -n entrelinhas-sql-api-ckenz0 --query defaultHostName -o tsv
az staticwebapp show -g livraria-entrelinhas-sql -n entrelinhas-sql-front-ckenz0 --query defaultHostname -o tsv
```

## Criar a infraestrutura

O [template ARM](../infrastructure/azure.json) cria os serviços, o banco
`entrelinhas`, regras de firewall e configurações da API. Use parâmetros seguros
em `.env.azure.parameters.json`, ignorado pelo Git:

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "secretKey": {"value": "SUBSTITUA_POR_CHAVE_ALEATORIA_ESTAVEL_COM_32_CARACTERES"},
    "postgresAdminPassword": {"value": "SUBSTITUA_POR_SENHA_FORTE_DO_ADMINISTRADOR"},
    "databasePassword": {"value": "SUBSTITUA_POR_SENHA_FORTE_DA_APLICACAO"},
    "adminIp": {"value": "SEU_IP_PUBLICO_ATUAL"},
    "appServiceSku": {"value": "B1"}
  }
}
```

```powershell
az login
az provider register --namespace Microsoft.DBforPostgreSQL --wait
az group create --name livraria-entrelinhas-sql --location brazilsouth
az deployment group create --name entrelinhas-sql-infra --resource-group livraria-entrelinhas-sql --template-file infrastructure/azure.json --parameters '@.env.azure.parameters.json'
```

Mantenha as chaves estáveis ao reaplicar o template. O firewall aceita serviços
Azure e o IP administrativo informado; conexões públicas fora dessas regras são
recusadas. Se seu IP mudar, atualize a regra administrativa para conseguir conectar.

## Preparar o usuário da aplicação

O template cria o servidor e o banco; a criação do login PostgreSQL da aplicação
é uma etapa administrativa separada, antes do primeiro deploy. Conecte com o
administrador, usando TLS e o prompt de senha do `psql`:

```powershell
$env:PGSSLMODE='require'
psql --host entrelinhas-sql-pg-ckenz0.postgres.database.azure.com --username entrelinhasadmin --dbname entrelinhas
```

Na primeira preparação:

```sql
CREATE ROLE entrelinhas_app LOGIN;
\password entrelinhas_app
GRANT CONNECT ON DATABASE entrelinhas TO entrelinhas_app;
GRANT USAGE, CREATE ON SCHEMA public TO entrelinhas_app;
ALTER ROLE entrelinhas_app SET idle_in_transaction_session_timeout TO '15s';
```

No prompt de `\password`, informe a mesma senha de `databasePassword`. O aplicativo
cria e gerencia suas próprias tabelas com esse login, que não recebe privilégios
de administrador do servidor. Em novas publicações, preserve o login existente;
não execute `CREATE ROLE` novamente. Uma rotação de senha deve atualizar também
`DATABASE_URL` nas configurações do App Service.

## Configuração da API

| Variável | Valor |
| --- | --- |
| `APP_ENV` | `production` |
| `STORAGE_BACKEND` | `postgresql` |
| `DATABASE_URL` | URI PostgreSQL do login `entrelinhas_app`, com `sslmode=require` |
| `SECRET_KEY` | Chave aleatória estável, somente no backend |
| `ALLOWED_ORIGINS` | Origem HTTPS real do frontend, sem barra final |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |

Runtime Python 3.12 em Linux, startup `bash startup.sh`, HTTPS obrigatório.
A configuração de produção exige PostgreSQL com TLS e não aceita fallback para
memória. A inicialização cria o esquema e aplica a carga idempotente. O endpoint
`/api/health` também verifica a conexão com o banco.

As conexões da aplicação encerram transações que ficam ociosas por 15 segundos.
Isso permite ao PostgreSQL liberar bloqueios de um processo interrompido durante
um reinício. O pool descarta conexões encerradas antes de reutilizá-las.

## GitHub Actions

Os workflows validam backend, PostgreSQL real, concorrência, contrato e navegador.
A publicação acontece em `main` quando `AZURE_DEPLOY_ENABLED=true`.

| Tipo | Nome | Conteúdo |
| --- | --- | --- |
| Variable | `AZURE_DEPLOY_ENABLED` | `true` após preparar banco, login e identidade |
| Variable | `AZURE_WEBAPP_NAME` | `entrelinhas-sql-api-ckenz0` |
| Variable | `AZURE_API_BASE_URL` | Origem HTTPS da API, sem `/api` |
| Secret | `AZURE_CLIENT_ID` | Client ID da identidade gerenciada |
| Secret | `AZURE_TENANT_ID` | Tenant ID |
| Secret | `AZURE_SUBSCRIPTION_ID` | Assinatura |
| Secret | `AZURE_STATIC_WEB_APPS_API_TOKEN` | Token de publicação do frontend |

A identidade `entrelinhas-sql-github` usa OIDC e a role `Website Contributor`
no escopo exclusivo desta API. Credencial federada:

- Issuer: `https://token.actions.githubusercontent.com`.
- Audience: `api://AzureADTokenExchange`.
- Subject: `repo:Ckenz0@146033211/Arquitetura-Cliente-Servidor-SQL@1467895436:ref:refs/heads/main`.

O prefixo usa os IDs imutáveis consultados no GitHub. Uma cópia do projeto precisa
consultar sua própria configuração OIDC. Não é necessário client secret.

## Conferir a publicação

1. Verifique `/api/health` e abra o frontend e `/docs`.
2. Em **Meu perfil**, salve nome, e-mail e telefone.
3. Faça uma reserva e salve preferências.
4. Reinicie somente a API e recarregue a mesma aba.
5. Confira perfil, reserva, estoque e preferências preservados.
6. Cancele a reserva e confirme a devolução de apenas um exemplar.
7. No Swagger UI, crie uma sessão, use seu token em **Authorize** e consulte livros
   e `/api/perfil` no mesmo servidor.

Consulte as [evidências](validation.md). Provisionar recursos não comprova que a
aplicação foi publicada ou que o login do banco está preparado.

## Referências

- [SQLAlchemy e psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg).
- [Azure PostgreSQL Flexible Server](https://learn.microsoft.com/en-us/azure/postgresql/configure-maintain/quickstart-create-server).
- [App Service: deploy ZIP](https://learn.microsoft.com/en-us/azure/app-service/deploy-zip).
