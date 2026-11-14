# Deriv Quant 2.0 🚀

Sistema algorítmico automatizado e painel em tempo real construído com a **Nova API Oficial da Deriv (developers.deriv.com / AI Hub)**.

Especializado na operação de **Contratos de Acumuladores (`ACCU`)** com seleção adaptativa do ativo com maior taxa de sobrevivência histórica e saída ultra-rápida (Cash Out programado).

---

## 🌟 Principais Recursos

- **Nova Arquitetura Deriv API (v2):**
  - Autenticação moderna via Personal Access Token (PAT) e emissão de WebSocket com One-Time Password (OTP) via REST.
  - Streaming de saldo nativo em tempo real (`balance: 1, subscribe: 1`) sem polling.
  - Heartbeat contínuo (`ping: 1`) a cada 20 segundos e reconexão automática com backoff exponencial.
- **Motor Adaptativo de Seleção de Ativos (`asset_selector.py`):**
  - Varre dinamicamente todos os 12 índices de volatilidade da Deriv (`R_10`, `R_25`, `R_50`, `R_75`, `R_100`, `1HZ10V`, `1HZ50V`, etc.).
  - Analisa a matriz oficial de 100 contratos de cada ativo (`ticks_stayed_in`) e elege o ativo com a maior probabilidade de sobrevivência na janela de ticks alvo.
  - Reavaliação periódica automática a cada 5 trades.
- **Operação de Acumuladores com Cash Out Inteligente:**
  - Taxa de crescimento configurável (1% a 5% ao tick).
  - Cash Out automático nos ticks alvo (ex: 6 ticks para coletar 5 degraus de 5% = +28% por vitória).
- **Gerenciador de Risco Rigoroso (`risk_manager.py`):**
  - Meta diária de lucro (Take Profit Diário).
  - Limite diário de perda (Stop Loss Diário).
  - Circuit Breaker automático para limitar perdas consecutivas.
- **Dashboard Web em Tempo Real (`web_server.py` + `web/index.html`):**
  - Interface Dark Glassmorphism moderna sem layout shift.
  - Comunicação WebSocket reativa (Pub/Sub) sem polling.
  - Controles de Iniciar e Pausar com 1 clique.
  - Live Trade Tracker mostrando o contrato em andamento tick a tick com lucro flutuante.
  - Histórico de trades e terminal de eventos em tempo real.

---

## 📂 Estrutura do Projeto

```
deriv-2.0/
├── .env.example               # Template de variáveis de ambiente
├── requirements.txt           # Dependências Python (fastapi, websockets, pandas, uvicorn...)
├── web/
│   └── index.html             # Interface Web do Dashboard (Tailwind + Lucide)
├── src/
│   ├── config.py              # Central de configurações e parâmetros
│   ├── risk_manager.py        # Travas rígidas de Stop Loss, Meta e Circuit Breaker
│   ├── asset_selector.py      # Scanner quantitativo dos melhores índices sintéticos
│   ├── accumulator_bot.py     # Motor autônomo de execução do Acumulador
│   └── web_server.py          # Backend FastAPI + WebSocket Event-Driven
└── README.md
```

---

## 🚀 Como Executar

### 1. Clonar e Instalar Dependências

```bash
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar Variáveis de Ambiente

Copie o `.env.example` para `.env`:

```bash
cp .env.example .env
```

Preencha as suas credenciais obtidas no portal [developers.deriv.com](https://developers.deriv.com/):
- `DERIV_API_TOKEN`: Seu Personal Access Token (PAT).
- `DERIV_APP_ID`: O App ID da aplicação cadastrada.
- `DERIV_ACCOUNT_ID`: Sua conta Demo (`DOT...`) ou Real (`ROT...`).

### 3. Iniciar o Dashboard Web

```bash
python src/web_server.py
```

Acesse no seu navegador: **`http://localhost:8000`** e clique em **"Iniciar"** para operar!

---

## ⚠️ Aviso Legal (Disclaimer)

Este software foi desenvolvido para fins educacionais, de pesquisa quantitativa e simulação em ambiente virtual (Demo). Negociar derivativos financeiros e índices sintéticos envolve risco substancial de perda de capital.
