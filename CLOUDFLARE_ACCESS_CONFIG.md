# Cloudflare Access Configuration - Payflow

## Objetivo
Deixar `https://payflow.ctrls.dev.br/healthz` público (sem 302), mantendo `/docs`, `/connect` e `/oauth/*` protegidos por login.

## Passos de Configuração

### 1. Acessar o Cloudflare Zero Trust Dashboard
1. Ir para: https://one.dash.cloudflare.com/
2. Selecionar sua conta/organização
3. Navegar para: **Access** → **Applications**

### 2. Localizar o Application Existente
1. Encontrar o app self-hosted: `payflow.ctrls.dev.br`
2. Clicar em **Edit** (ícone de lápis/editar)

### 3. Configurar Application Paths

#### Opção A: Usando Application Paths (Recomendado)

**Path 1: /healthz (Público - Bypass)**
- **Path**: `/healthz`
- **Policy Name**: `Bypass - Health Check`
- **Policy Action**: `Bypass`
- **Include Rule**: `Everyone`
- **Descrição**: Public health check endpoint

**Path 2: /* ou Default (Protegido)**
- **Path**: `/*` (ou deixar como default application)
- **Policy Name**: `Allow - Authorized Users`
- **Policy Action**: `Allow`
- **Include Rule**: 
  - Opção 1: Adicionar emails específicos
  - Opção 2: Criar um grupo (Access → Access Groups) e adicionar o grupo aqui
  - Opção 3: Usar domínio específico (@ctrls.dev.br)
- **Descrição**: Protected application routes

#### Configuração Detalhada no Dashboard

**Passo 1: Editar Application Settings**
```
Name: Payflow API
Session Duration: (manter existente ou ajustar conforme necessário)
Application domain: payflow.ctrls.dev.br
```

**Passo 2: Add Application Path - /healthz**
1. Na seção "Application paths", clicar em **Add a path**
2. Preencher:
   - **Path**: `/healthz`
   - Clicar em **Save path**

3. Configurar Policy para este path:
   - **Policy name**: `Bypass - Health Check`
   - **Action**: Selecionar `Bypass`
   - **Configure rules**:
     - **Include**: `Everyone`
   - Clicar em **Save policy**

**Passo 3: Configurar Default Path (Proteção)**
1. Se ainda não existir uma policy default, adicionar:
   - Na seção de policies (fora de paths específicos) ou criar path `/*`
   
2. Configurar:
   - **Policy name**: `Allow - Authorized Users`
   - **Action**: `Allow`
   - **Configure rules**:
     - **Include**: 
       - Adicionar `Emails` e listar os emails autorizados, OU
       - Adicionar `Access groups` e selecionar grupo pré-criado
   - Clicar em **Save policy**

**Passo 4: Ordem de Prioridade**
- Garantir que `/healthz` está listado ANTES de `/*` ou default
- Cloudflare avalia paths mais específicos primeiro
- Arrastar e reorganizar se necessário

**Passo 5: Salvar Configuração**
- Clicar em **Save application**

---

## Validação

### Teste 1: Health Check Público
```powershell
curl -i https://payflow.ctrls.dev.br/healthz
```
**Resultado esperado:**
```
HTTP/2 200
content-type: application/json
...

{"status":"ok"}
```
❌ **NÃO deve ter** `HTTP/2 302` ou redirecionamento para Access login

### Teste 2: Documentação Protegida
```powershell
curl -i https://payflow.ctrls.dev.br/docs
```
**Resultado esperado:**
```
HTTP/2 302
location: https://[seu-team].cloudflareaccess.com/cdn-cgi/access/login/[app-id]
...
```
✅ **Deve redirecionar** para tela de login do Cloudflare Access

### Teste 3: OAuth Protegido
```powershell
curl -i https://payflow.ctrls.dev.br/oauth/authorize
```
**Resultado esperado:**
```
HTTP/2 302
location: https://[seu-team].cloudflareaccess.com/cdn-cgi/access/login/[app-id]
...
```
✅ **Deve redirecionar** para tela de login do Cloudflare Access

### Teste 4: Connect Protegido
```powershell
curl -i https://payflow.ctrls.dev.br/connect
```
**Resultado esperado:**
```
HTTP/2 302
...
```
✅ **Deve redirecionar** para tela de login

---

## Checklist de Configuração

### Pré-Configuração
- [ ] Backup da configuração atual (tirar prints antes de alterar)
- [ ] Anotar policies existentes

### Configuração
- [ ] Acessei Zero Trust Dashboard → Access → Applications
- [ ] Localizei o app `payflow.ctrls.dev.br`
- [ ] Cliquei em **Edit**
- [ ] Adicionei path `/healthz` com policy `Bypass` para `Everyone`
- [ ] Configurei path default `/*` (ou root) com policy `Allow` para usuários autorizados
- [ ] Verifiquei ordem de prioridade dos paths (healthz primeiro)
- [ ] Cliquei em **Save application**
- [ ] Aguardei propagação (~30 segundos)

### Validação
- [ ] `curl -i https://payflow.ctrls.dev.br/healthz` retorna **200 OK** (sem 302)
- [ ] `curl -i https://payflow.ctrls.dev.br/docs` retorna **302** para Access login
- [ ] `curl -i https://payflow.ctrls.dev.br/oauth/authorize` retorna **302** para Access login
- [ ] `curl -i https://payflow.ctrls.dev.br/connect` retorna **302** para Access login

### Pós-Configuração
- [ ] Tirar prints da configuração final
- [ ] Documentar emails/grupos autorizados
- [ ] Testar login com usuário autorizado
- [ ] Testar acesso negado com usuário não autorizado (se aplicável)

---

## Troubleshooting

### Problema: /healthz ainda retorna 302
**Soluções:**
1. Verificar se o path é exatamente `/healthz` (case-sensitive)
2. Confirmar que policy é `Bypass` (não `Service Auth` ou `Allow`)
3. Verificar ordem - path `/healthz` deve ter prioridade sobre `/*`
4. Limpar cache do navegador/cloudflare
5. Aguardar 1-2 minutos para propagação

### Problema: Todos os paths ficaram públicos
**Soluções:**
1. Verificar se existe policy default com `Allow`
2. Confirmar que path `/*` ou default application tem policy `Allow` (não Bypass)
3. Verificar include rules da policy default

### Problema: Usuários autorizados não conseguem acessar /docs
**Soluções:**
1. Verificar se email está no include da policy `Allow`
2. Verificar se grupo Access tem os membros corretos
3. Pedir para usuário fazer logout/login no Cloudflare Access
4. Verificar logs em Access → Logs

---

## Configuração Alternativa (Se Application Paths não estiver disponível)

Caso seu plano do Cloudflare não tenha "Application Paths", use esta abordagem:

### Opção B: Criar Dois Applications Separados

**Application 1: Health Check (Público)**
- **Name**: `Payflow - Health Check`
- **Domain**: `payflow.ctrls.dev.br`
- **Path**: `/healthz`
- **Policy**: `Bypass` para `Everyone`

**Application 2: Payflow API (Protegido)**
- **Name**: `Payflow API - Protected`
- **Domain**: `payflow.ctrls.dev.br`
- **Path**: `/*` (ou deixar vazio)
- **Policy**: `Allow` para usuários autorizados
- **⚠️ Importante**: Criar policy de Bypass ou exclusão para `/healthz`

**Ordem de Prioridade:**
- Application 1 (Health Check) deve estar ACIMA de Application 2 na lista
- Arrastar para reordenar se necessário

---

## Informações Adicionais

### Documentação Oficial
- [Cloudflare Access Applications](https://developers.cloudflare.com/cloudflare-one/applications/)
- [Cloudflare Access Policies](https://developers.cloudflare.com/cloudflare-one/policies/access/)
- [Application Paths](https://developers.cloudflare.com/cloudflare-one/applications/configure-apps/self-hosted-apps/#application-paths)

### Contatos para Suporte
- Se precisar de ajuda adicional com configuração específica do Cloudflare
- Verificar limites do plano atual

---

## Registro de Alterações

**Data**: 2026-02-11
**Alterado por**: [Seu nome/email]
**Mudanças**:
- [ ] Adicionado path `/healthz` com Bypass
- [ ] Configurado path default com Allow para [listar emails/grupos]
- [ ] Validado acesso público ao healthz
- [ ] Validado proteção em /docs, /oauth/*, /connect

**Prints salvos em**: [Local onde salvou os prints]

---

## Modelo de Documentação das Mudanças

### Screenshot 1: Application Overview
- Nome do app
- Domain configurado
- Status (Active)

### Screenshot 2: Application Paths
- Lista de paths configurados
- Ordem de prioridade

### Screenshot 3: Policy - /healthz (Bypass)
```
Path: /healthz
Policy Name: Bypass - Health Check
Action: Bypass
Include: Everyone
```

### Screenshot 4: Policy - Default (Allow)
```
Path: /* (ou default)
Policy Name: Allow - Authorized Users
Action: Allow
Include: [emails ou grupos]
```

### Screenshot 5: Validation - cURL Results
```
$ curl -i https://payflow.ctrls.dev.br/healthz
HTTP/2 200 OK
...

$ curl -i https://payflow.ctrls.dev.br/docs
HTTP/2 302 Found
location: https://....cloudflareaccess.com/...
```

