# Deriv API (Nova Arquitetura Oficial - developers.deriv.com / AI Hub)

Documentação oficial de referência para automação, modelos LLM e agentes de IA extraída de:
- **AI Hub & Contexto para LLMs:** `https://developers.deriv.com/llms.txt`
- **MCP Endpoint Oficial:** `https://mcp-api.deriv.com/mcp`
- **Portal de Desenvolvedores:** `https://developers.deriv.com/`

---

## 1. Gateways e Transports

| Superfície | Gateway | Autenticação | Rate Limit |
|---|---|---|---|
| **Market Data Público (Ticks, Proposals, Ciclos)** | `wss://api.derivws.com/trading/v1/options/ws/public` | Nenhuma. Conexão direta e imediata. | Sem limite de auth |
| **Trading Autenticado (Demo)** | `wss://api.derivws.com/trading/v1/options/ws/demo` | URL com OTP emitida via `POST /trading/v1/options/accounts/{accountId}/otp` | 360 req/min por conta |
| **Trading Autenticado (Real)** | `wss://api.derivws.com/trading/v1/options/ws/real` | URL com OTP emitida via `POST /trading/v1/options/accounts/{accountId}/otp` | 360 req/min por conta |
| **REST API** | `https://api.derivws.com` | Headers: `Authorization: Bearer <PAT>` e `Deriv-App-ID: <APP_ID>` | 80 req/min |

---

## 2. Autenticação e Multi-Contas com PAT (Personal Access Token)

### Suporte Nativo a Múltiplos PATs Simultâneos
A arquitetura da Deriv suporta conexão simultânea de múltiplas contas autenticadas através de tokens independentes (PAT):
1. **Autenticação por Requisição / Por Conexão (*Per-Account Authentication*):**
   - Cada WebSocket aberto é um canal TCP isolado no servidor da Deriv.
   - Uma aplicação pode instanciar conexões simultâneas usando **tokens de contas diferentes** (mesmo titular ou titulares completamente distintos).
   - O rate limit de operações (`360 req/min` para trading) é computado **por token/conta**, e não por endereço IP.
2. **Bulk Purchase & Multi-Account Architecture:**
   - A própria Deriv fornece a API de *Bulk Purchase / Multi-Account Operations* onde cada transação recebe o par `(account_id, token_pat)`.
3. **Mapeamento de Contas:**
   - **Conta Primária (Real):** Autenticada com `PAT_PRIMARY` (`ROT...`).
   - **Conta Secundária (Escudo / Demo):** Autenticada com `PAT_SECONDARY` (`DOT...` ou virtual de outro usuário).

---

## 3. Especificação da Arquitetura "Conta Escudo" (Ghost Trading)

### Conceito Quantitativo
A estratégia da Conta Escudo baseia-se em absorção de variância estocástica:
1. **Fase 1 (Sondagem na Demo):** O robô dispara as ordens normalmente na Conta Secundária (Demo/Virtual).
2. **Fase 2 (Gatilho de Estresse):** Ao identificar uma sequência consecutiva de $X$ Derrotas (Loss Streak, ex: 2L ou 3L) na Demo, o sistema aciona o modo de execução cirúrgica.
3. **Fase 3 (Sniper na Conta Real):** No instante em que o ciclo oficial da Deriv reseta, a próxima ordem de compra é roteada exclusivamente para a **Conta Primária (Real)**.
4. **Fase 4 (Recuo para Escudo):** Após a finalização do trade na conta Real, o sistema retorna o controle de sondagem para a conta Demo.

### Vantagens de Implementação Senior (Sem Gambiarras):
- **Isolamento de Conexões:** Cada conta possui sua própria instância de `AccountClient` com seu socket e monitor de saldo próprio.
- **Stream de Mercado Único:** O monitoramento de ticks e detecção de reset de ciclo utiliza um único WebSocket público compartilhado, evitando consumo desnecessário de conexões.
- **Gestão de Risco Desacoplada:** A Conta Real possui seu próprio Stop Loss rígido e Take Profit em dólares reais, independente do saldo da Demo.
