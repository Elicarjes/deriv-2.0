# Deriv API (Nova Arquitetura Oficial - developers.deriv.com)

Documentação oficial de referência para automação e IA extraída de `https://developers.deriv.com/llms.txt`.

## Gateways e Transports

| Superfície | Gateway | Autenticação |
|---|---|---|
| **Market Data Público (Ticks, Candles, Proposals, Symbols)** | `wss://api.derivws.com/trading/v1/options/ws/public` | Nenhuma. Conexão direta e imediata. |
| **Trading Autenticado (Ordens, Posições)** | `wss://api.derivws.com/trading/v1/options/ws/demo` ou `/ws/real` | URL de WebSocket temporária emitida via OTP em `POST /trading/v1/options/accounts/{accountId}/otp`. |
| **REST API** | `https://api.derivws.com` | `Authorization: Bearer <token>` (+ `Deriv-App-ID` para Personal Access Tokens). |

## Regras Fundamentais
1. **Nenhum token é enviado no corpo de WebSocket inicial público.** Dados de mercado públicos conectam em `wss://api.derivws.com/trading/v1/options/ws/public`.
2. Para trading, um OTP WebSocket é emitido pela API REST e a conexão autenticada dedicada é aberta.
3. Campo de símbolo padrão: `underlying_symbol` ou `ticks_history` com o código do ativo (ex: `R_100`).
