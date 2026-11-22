import json
import os

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Deriv Quant - Backtest Quantitativo & Histórico de Streaks | R_100</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --text-bright: #f0f6fc;
      --green: #238636;
      --green-light: #2ea043;
      --red: #da3633;
      --red-light: #f85149;
      --blue: #1f6feb;
      --blue-light: #58a6ff;
      --yellow: #d29922;
      --purple: #8957e5;
      --gold: #e3b341;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 24px;
    }
    .container { max-width: 1440px; margin: 0 auto; }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 16px;
    }
    .header-title h1 {
      font-size: 24px;
      font-weight: 700;
      color: var(--text-bright);
      margin-bottom: 8px;
    }
    .badge {
      display: inline-block;
      padding: 3px 10px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
      margin-right: 6px;
      margin-bottom: 4px;
    }
    .badge-symbol { background: rgba(31, 111, 235, 0.2); color: var(--blue-light); border: 1px solid rgba(31, 111, 235, 0.4); }
    .badge-strategy { background: rgba(137, 87, 229, 0.2); color: #bc8cff; border: 1px solid rgba(137, 87, 229, 0.4); }
    .badge-shield { background: rgba(46, 160, 67, 0.2); color: #3fb950; border: 1px solid rgba(46, 160, 67, 0.4); }
    .badge-date { background: rgba(210, 153, 34, 0.2); color: #e3b341; border: 1px solid rgba(210, 153, 34, 0.4); }
    .badge-info { background: rgba(56, 139, 253, 0.15); color: #79c0ff; border: 1px solid rgba(56, 139, 253, 0.4); }

    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .kpi-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 18px;
    }
    .kpi-title { font-size: 13px; color: #8b949e; font-weight: 500; margin-bottom: 6px; }
    .kpi-value { font-size: 26px; font-weight: 700; line-height: 1.2; }
    .kpi-sub { font-size: 12px; color: #8b949e; margin-top: 6px; }
    
    .val-green { color: var(--green-light); }
    .val-red { color: var(--red-light); }
    .val-blue { color: var(--blue-light); }
    .val-gold { color: var(--gold); }

    .section-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 24px;
    }
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      flex-wrap: wrap;
      gap: 10px;
    }
    .section-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-bright);
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .streaks-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 12px;
    }
    .streak-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      border: 1px solid transparent;
    }
    .streak-loss { background: rgba(218, 54, 51, 0.15); border-color: rgba(218, 54, 51, 0.3); color: var(--red-light); }
    .streak-win { background: rgba(35, 134, 54, 0.15); border-color: rgba(35, 134, 54, 0.3); color: var(--green-light); }
    .streak-count { font-size: 11px; opacity: 0.8; font-weight: 400; }

    .controls-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 14px;
      background: #0d1117;
      padding: 16px;
      border-radius: 6px;
      border: 1px solid var(--border);
      margin-bottom: 16px;
    }
    .control-group label {
      display: block;
      font-size: 12px;
      color: #8b949e;
      margin-bottom: 6px;
      font-weight: 500;
    }
    .control-group select, .control-group input {
      width: 100%;
      background: #161b22;
      border: 1px solid var(--border);
      color: var(--text-bright);
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 13px;
      outline: none;
    }
    .control-group select:focus, .control-group input:focus {
      border-color: var(--blue-light);
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      text-align: left;
    }
    th, td {
      padding: 10px 14px;
      border-bottom: 1px solid var(--border);
    }
    th {
      color: #8b949e;
      font-weight: 600;
      background: #0d1117;
      position: sticky;
      top: 0;
      z-index: 2;
    }
    tr:hover td { background: rgba(255, 255, 255, 0.02); }

    .shield-stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      background: #0d1117;
      padding: 14px;
      border-radius: 6px;
      border: 1px solid var(--border);
      margin-bottom: 16px;
    }
    .shield-stat-title { font-size: 12px; color: #8b949e; }
    .shield-stat-val { font-size: 20px; font-weight: 700; }

    .table-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 14px;
      flex-wrap: wrap;
      gap: 10px;
    }
    .btn {
      background: #21262d;
      color: var(--text-bright);
      border: 1px solid var(--border);
      padding: 6px 14px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 13px;
      transition: background 0.2s;
    }
    .btn:hover { background: #30363d; }
    .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="header-title">
        <h1>Dashboard Quantitativo: Backtest Deriv</h1>
        <span class="badge badge-symbol" id="headerSymbol">R_100</span>
        <span class="badge badge-strategy" id="headerStrategyBadge">Estratégia: Reversão após 7 Velas</span>
        <span class="badge badge-shield" id="headerModeBadge">⚠️ Sem Escudo (100% Real)</span>
        <span class="badge badge-date" id="headerDate">Carregando período...</span>
        <span class="badge badge-info" id="headerWindowBadge">5 Dias (4 Fechados + Hoje)</span>
        <span class="badge" style="background: rgba(46, 160, 67, 0.15); color: #3fb950; border: 1px solid rgba(46, 160, 67, 0.4);">🕒 Horário Oficial Deriv (GMT)</span>
      </div>
      <div>
        <button class="btn" onclick="exportCSV()">📥 Exportar CSV dos Trades</button>
      </div>
    </header>

    <!-- KPIs Dinâmicos -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-title">Ordens na Conta Real (Master)</div>
        <div class="kpi-value val-gold" id="kpiRealTrades">-</div>
        <div class="kpi-sub" id="kpiFilteredSub">Calculando...</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Assertividade na Conta Real</div>
        <div class="kpi-value val-blue" id="kpiWinRate">-</div>
        <div class="kpi-sub" id="kpiCyclesSub">-</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Maior Sequência de Perdas</div>
        <div class="kpi-value val-red" id="kpiMaxLossStreak">-</div>
        <div class="kpi-sub">No período selecionado</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Maior Sequência de Vitórias</div>
        <div class="kpi-value val-green" id="kpiMaxWinStreak">-</div>
        <div class="kpi-sub">No período selecionado</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Resultado Líquido (Conta Real)</div>
        <div class="kpi-value val-red" id="kpiPnL">-</div>
        <div class="kpi-sub" id="kpiPnLSub">-</div>
      </div>
    </div>

    <!-- Seção de Recordes Históricos e Banco de Streaks Perpétuo -->
    <div class="section-card" style="border: 1px solid rgba(227, 179, 65, 0.35); background: linear-gradient(180deg, rgba(22, 27, 34, 0.95) 0%, rgba(13, 17, 23, 0.95) 100%);">
      <div class="section-header">
        <div class="section-title">
          <span>🏛️ Recordes Históricos Perpétuos de Streaks (Banco de Dados SQLite)</span>
        </div>
        <span style="font-size: 12px; color: #8b949e;">Registro perpétuo de sequências ≥ 6 velas consecutivas (permanece salvo mesmo após o descarte dos 5 dias de backtest)</span>
      </div>

      <!-- Cards de Destaque dos Recordes Absolutos -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-bottom: 20px;">
        <div style="background: rgba(227, 179, 65, 0.08); border: 1px solid rgba(227, 179, 65, 0.35); border-radius: 8px; padding: 16px;">
          <div style="font-size: 11px; font-weight: 700; color: var(--gold); text-transform: uppercase; letter-spacing: 0.5px;">👑 MAIOR SEQUÊNCIA DA HISTÓRIA</div>
          <div style="font-size: 26px; font-weight: 800; color: #fff; margin: 8px 0;" id="histMaxOverallLen">-</div>
          <div style="font-size: 12px; color: #c9d1d9;" id="histMaxOverallDates">-</div>
          <div style="font-size: 11px; color: #8b949e; margin-top: 4px;" id="histMaxOverallPrices">-</div>
        </div>

        <div style="background: rgba(46, 160, 67, 0.08); border: 1px solid rgba(46, 160, 67, 0.35); border-radius: 8px; padding: 16px;">
          <div style="font-size: 11px; font-weight: 700; color: var(--green-light); text-transform: uppercase; letter-spacing: 0.5px;">🟢 MAIOR SEQUÊNCIA VERDE DA HISTÓRIA</div>
          <div style="font-size: 26px; font-weight: 800; color: var(--green-light); margin: 8px 0;" id="histMaxGreenLen">-</div>
          <div style="font-size: 12px; color: #c9d1d9;" id="histMaxGreenDates">-</div>
          <div style="font-size: 11px; color: #8b949e; margin-top: 4px;" id="histMaxGreenPrices">-</div>
        </div>

        <div style="background: rgba(248, 81, 73, 0.08); border: 1px solid rgba(248, 81, 73, 0.35); border-radius: 8px; padding: 16px;">
          <div style="font-size: 11px; font-weight: 700; color: var(--red-light); text-transform: uppercase; letter-spacing: 0.5px;">🔴 MAIOR SEQUÊNCIA VERMELHA DA HISTÓRIA</div>
          <div style="font-size: 26px; font-weight: 800; color: var(--red-light); margin: 8px 0;" id="histMaxRedLen">-</div>
          <div style="font-size: 12px; color: #c9d1d9;" id="histMaxRedDates">-</div>
          <div style="font-size: 11px; color: #8b949e; margin-top: 4px;" id="histMaxRedPrices">-</div>
        </div>
      </div>

      <!-- Frequência Histórica -->
      <div style="margin-bottom: 14px;">
        <span style="font-size: 13px; font-weight: 600; color: var(--text-bright);">📊 Frequência Total de Sequências ≥ 6 Velas Catalogadas no Banco de Dados:</span>
        <div class="streaks-row" id="histDistributionBadges" style="margin-top: 8px;"></div>
      </div>

      <!-- Tabela Histórica Colapsável -->
      <details style="margin-top: 10px; background: #0d1117; border: 1px solid var(--border); border-radius: 6px; padding: 10px 14px;">
        <summary style="cursor: pointer; font-weight: 600; font-size: 13px; color: var(--blue-light);">
          🔍 Consultar Todas as Sequências ≥ 6 Velas com Data e Horário Exatos (<span id="histTotalCount">0</span> registros no banco)
        </summary>
        <div style="max-height: 280px; overflow-y: auto; margin-top: 10px;">
          <table>
            <thead>
              <tr>
                <th>Direção</th>
                <th>Tamanho do Streak</th>
                <th>Início Exato (GMT)</th>
                <th>Término Exato (GMT)</th>
                <th>Abertura</th>
                <th>Fechamento</th>
              </tr>
            </thead>
            <tbody id="histStreaksTableBody">
              <!-- Preenchido via JS -->
            </tbody>
          </table>
        </div>
      </details>
    </div>

    <!-- Seção de Streaks da Estratégia no Período Selecionado -->
    <div class="section-card">
      <div class="section-header">
        <div class="section-title">
          <span>🔥 Sequências Consecutivas (Streaks) da Estratégia no Período Selecionado</span>
        </div>
        <span style="font-size: 13px; color: #8b949e;" id="streaksSubHeader">Contagem exata de quantas vezes cada sequência consecutiva ocorreu</span>
      </div>

      <div style="margin-bottom: 12px; font-weight: 600; color: var(--red-light); font-size: 14px;">
        🔻 STREAKS DE DERROTA (LOSSES CONSECUTIVOS):
      </div>
      <div class="streaks-row" id="lossStreaksBadges">
        <!-- Badges inseridos via JS -->
      </div>

      <div style="margin-top: 20px; margin-bottom: 12px; font-weight: 600; color: var(--green-light); font-size: 14px;">
        🟢 STREAKS DE VITÓRIA (WINS CONSECUTIVOS):
      </div>
      <div class="streaks-row" id="winStreaksBadges">
        <!-- Badges inseridos via JS -->
      </div>
    </div>

    <!-- Simulador Master / Slave com Escudo -->
    <div class="section-card">
      <div class="section-header">
        <div class="section-title">
          <span>🛡️ Painel de Controle e Parâmetros da Simulação</span>
        </div>
        <span style="font-size: 12px; color: #8b949e;">Altere os parâmetros para recalcular em tempo real</span>
      </div>

      <div class="controls-grid">
        <!-- Seletor de Período / Data -->
        <div class="control-group">
          <label>Janela / Data do Backtest</label>
          <select id="ctrlPeriod" onchange="onPeriodChange()">
            <!-- Preenchido via JS com Janela Completa (5 Dias) e cada dia individual -->
          </select>
        </div>

        <!-- Seletor de Estratégia -->
        <div class="control-group">
          <label>Estratégia Operacional</label>
          <select id="ctrlStrategy" onchange="onStrategyChange()">
            <option value="REV_STREAK" selected>🔁 Reversão por Streaks de Cores (Exaustão 6 a 15 Velas)</option>
            <option value="ALTERNADA_RISE_FALL">🔀 Alternância Contínua (Inicia RISE -> FALL -> RISE...)</option>
            <option value="ALTERNADA_FALL_RISE">🔀 Alternância Contínua (Inicia FALL -> RISE -> FALL...)</option>
            <option value="TRES_MOSQUETEIROS">⚔️ Três Mosqueteiros (2 Velas Iguais -> 3ª na Mesma Direção)</option>
            <option value="CONTRA_MOSQUETEIROS">🛡️ Contra Mosqueteiros (2 Velas Iguais -> Reversão na 3ª)</option>
            <option value="TRES_MOSQUETEIROS_ESTRITO">🎯 Três Mosqueteiros Estrito (Ciclos Fechados de 3 Velas)</option>
            <option value="MILHAO_MINORIA_M5">🎯 Milhão Minoria (Blocos 5 min / M5)</option>
            <option value="MILHAO_MAIORIA_M5">🔥 Milhão Maioria (Blocos 5 min / M5)</option>
            <option value="MILHAO_MINORIA_MOVEL">⚡ Milhão Minoria Móvel (5 velas contínuas)</option>
            <option value="MILHAO_MAIORIA_MOVEL">⚡ Milhão Maioria Móvel (5 velas contínuas)</option>
            <option value="TREND_50S">🟢 Seguidor de Cor M1 (Verde=Rise / Vermelho=Fall)</option>
            <option value="REVERSAL_50S">🔄 Reversão de Cor M1 (Verde=Fall / Vermelho=Rise)</option>
          </select>
        </div>

        <!-- Tempo de Expiração -->
        <div class="control-group" id="groupDuration">
          <label>Tempo de Expiração</label>
          <select id="ctrlDuration" onchange="onDurationChange()">
            <option value="50s" selected>50 Segundos (50s) [Padrão Bot]</option>
            <option value="60s">60 Segundos (1 Minuto / Fim da Vela M1)</option>
            <option value="30s">30 Segundos (30s)</option>
            <option value="15s">15 Segundos (15s)</option>
            <option value="2m">2 Minutos (120s)</option>
            <option value="5m">5 Minutos (M5 / 300s)</option>
          </select>
        </div>

        <!-- Controles Específicos para Reversão por Streaks de Cores -->
        <div class="control-group" id="groupCandleStreakCount" style="display: block;">
          <label>Velas Consecutivas para Reversão</label>
          <select id="ctrlCandleStreakCount" onchange="onStrategyChange()">
            <option value="6">6 velas consecutivas</option>
            <option value="7" selected>7 velas consecutivas</option>
            <option value="8">8 velas consecutivas</option>
            <option value="9">9 velas consecutivas</option>
            <option value="10">10 velas consecutivas</option>
            <option value="11">11 velas consecutivas</option>
            <option value="12">12 velas consecutivas</option>
            <option value="13">13 velas consecutivas</option>
            <option value="14">14 velas consecutivas</option>
            <option value="15">15 velas consecutivas</option>
          </select>
        </div>

        <div class="control-group" id="groupCandleStreakDir" style="display: block;">
          <label>Filtro de Cor (Gatilho)</label>
          <select id="ctrlCandleStreakDir" onchange="onStrategyChange()">
            <option value="BOTH" selected>Ambas (Vermelhos=RISE / Verdes=FALL)</option>
            <option value="RED">Apenas Vermelhos (Entra RISE)</option>
            <option value="GREEN">Apenas Verdes (Entra FALL)</option>
          </select>
        </div>

        <!-- Modo de Operação -->
        <div class="control-group">
          <label>Modo de Operação</label>
          <select id="ctrlMode" onchange="onModeChange()">
            <option value="LOSS_STREAK">1 - Streaks de Derrotas (Loss)</option>
            <option value="WIN_STREAK">2 - Streaks de Vitórias (Win)</option>
            <option value="DIRECT" selected>3 - Sem Escudo (Direto na Real)</option>
          </select>
        </div>

        <!-- Quantidade de Streaks para Gatilho -->
        <div class="control-group" id="groupStreakCount">
          <label>Quantidade de Streaks (Gatilho)</label>
          <select id="ctrlStreakCount" onchange="recalcSimulation()" disabled>
            <option value="1" selected>1 ocorrência (1x)</option>
            <option value="2">2 ocorrências consecutivas (2x)</option>
            <option value="3">3 ocorrências consecutivas (3x)</option>
            <option value="4">4 ocorrências consecutivas (4x)</option>
            <option value="5">5 ocorrências consecutivas (5x)</option>
            <option value="6">6 ocorrências consecutivas (6x)</option>
            <option value="7">7 ocorrências consecutivas (7x)</option>
            <option value="8">8 ocorrências consecutivas (8x)</option>
            <option value="9">9 ocorrências consecutivas (9x)</option>
            <option value="10">10 ocorrências consecutivas (10x)</option>
          </select>
        </div>

        <!-- Nível Máximo de Martingale -->
        <div class="control-group">
          <label>Gales na Conta Real</label>
          <select id="ctrlGaleLevel" onchange="recalcSimulation()">
            <option value="0">Mão Fixa (Padrão - Sem Gale)</option>
            <option value="1">Gale 1 (G1)</option>
            <option value="2">Gale 2 (G2)</option>
            <option value="3">Gale 3 (G3)</option>
            <option value="4">Gale 4 (G4)</option>
            <option value="5">Gale 5 (G5)</option>
            <option value="6" selected>Gale 6 (G6)</option>
            <option value="7">Gale 7 (G7)</option>
            <option value="8">Gale 8 (G8)</option>
            <option value="9">Gale 9 (G9)</option>
            <option value="10">Gale 10 (G10)</option>
          </select>
        </div>

        <!-- Stake Base -->
        <div class="control-group">
          <label>Stake Base na Real ($)</label>
          <input type="number" id="ctrlStake" value="0.35" step="0.05" min="0.35" oninput="recalcSimulation()">
        </div>

        <!-- Payout -->
        <div class="control-group">
          <label>Payout Deriv (0.88)</label>
          <input type="number" id="ctrlPayout" value="0.88" step="0.01" min="0.5" max="1.0" oninput="recalcSimulation()">
        </div>

        <!-- Multiplicador -->
        <div class="control-group" id="groupMultiplier">
          <label>Multiplicador do Gale</label>
          <input type="number" id="ctrlMultiplier" value="2.40" step="0.05" min="1.5" max="5.0" oninput="recalcSimulation()">
        </div>
      </div>

      <!-- Estatísticas do Escudo -->
      <div class="shield-stats">
        <div>
          <div class="shield-stat-title">Ordens no Escudo (Demo)</div>
          <div class="shield-stat-val" id="statSlaveOrders">-</div>
        </div>
        <div>
          <div class="shield-stat-title">Ordens na Conta Real</div>
          <div class="shield-stat-val val-gold" id="statMasterOrders">-</div>
        </div>
        <div>
          <div class="shield-stat-title">Exposição Filtrada</div>
          <div class="shield-stat-val val-green" id="statExposureSaved">-</div>
        </div>
        <div>
          <div class="shield-stat-title">Stops na Real (Loss Total)</div>
          <div class="shield-stat-val val-red" id="statStopsAvoided">-</div>
        </div>
      </div>

      <!-- Resumo dos Ciclos de Gale da Master com Saldo Necessário -->
      <div style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <span id="martingaleTableTitle" style="font-weight: 600; font-size: 14px; color: var(--text-bright);">📊 Eficiência dos Ciclos de Gale na Conta Real</span>
        <span id="martingaleTableSummary" style="font-size: 12px; color: #8b949e;"></span>
      </div>
      <div style="overflow-x: auto; margin-bottom: 20px;">
        <table>
          <thead>
            <tr>
              <th>Nível na Conta Real</th>
              <th>Stake por Ordem</th>
              <th>Saldo Necessário (Banca)</th>
              <th>Vitórias (Wins)</th>
              <th>% Individual</th>
              <th>Acumulado</th>
              <th>% Acumulada</th>
            </tr>
          </thead>
          <tbody id="martingaleTableBody">
            <!-- Preenchido via JS -->
          </tbody>
        </table>
      </div>

      <!-- Gráfico da Curva de Capital (PnL da Conta Real) -->
      <div style="height: 320px; position: relative;">
        <canvas id="chartPnL"></canvas>
      </div>
    </div>

    <!-- Log de Trades com Filtro de Conta (Demo vs Real) -->
    <div class="section-card">
      <div class="section-header">
        <div class="section-title" id="logSectionTitle">📋 Log Individual das Ordens</div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <select id="filterAccount" style="background: #0d1117; border: 1px solid var(--border); color: #fff; padding: 4px 10px; border-radius: 4px; font-size: 12px;" onchange="filterTrades()">
            <option value="ALL">Todas as Contas</option>
            <option value="REAL" selected>⭐ Apenas Conta Real (Master)</option>
            <option value="DEMO">🛡️ Apenas Conta Demo (Slave)</option>
          </select>
          <input type="text" id="searchTrade" placeholder="Filtrar hora/data (ex: 11-21 ou 14:2)..." style="background: #0d1117; border: 1px solid var(--border); color: #fff; padding: 4px 10px; border-radius: 4px; font-size: 12px;" oninput="filterTrades()">
          <select id="filterResult" style="background: #0d1117; border: 1px solid var(--border); color: #fff; padding: 4px 10px; border-radius: 4px; font-size: 12px;" onchange="filterTrades()">
            <option value="ALL">Todos os Resultados</option>
            <option value="WIN">Apenas Wins</option>
            <option value="LOSS">Apenas Losses</option>
          </select>
          <select id="filterGale" style="background: #0d1117; border: 1px solid var(--border); color: #fff; padding: 4px 10px; border-radius: 4px; font-size: 12px;" onchange="filterTrades()">
            <option value="ALL">Todos os Ciclos</option>
            <option value="0">Apenas G0 (1ª Mão)</option>
            <option value="1">Apenas G1</option>
            <option value="2">Apenas G2</option>
            <option value="3">Apenas G3</option>
            <option value="4">Apenas G4</option>
            <option value="5">Apenas G5</option>
            <option value="6">Apenas G6</option>
            <option value="7">Apenas G7</option>
            <option value="8">Apenas G8</option>
            <option value="9">Apenas G9</option>
            <option value="10">Apenas G10</option>
          </select>
        </div>
      </div>

      <div style="overflow-x: auto;">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Conta Executora</th>
              <th>Horário (GMT Deriv)</th>
              <th>Contexto / Análise Prévia</th>
              <th>Contrato</th>
              <th>Entrada (:00)</th>
              <th id="thExitHeader">Saída (:50)</th>
              <th>Variação</th>
              <th>Resultado</th>
              <th>Stake</th>
              <th>Impacto Saldo Real</th>
            </tr>
          </thead>
          <tbody id="tradesTableBody">
            <!-- Preenchido via JS -->
          </tbody>
        </table>
      </div>

      <div class="table-footer">
        <div id="paginationInfo" style="font-size: 13px; color: #8b949e;">Exibindo 1 a 50</div>
        <div style="display: flex; gap: 8px;">
          <button class="btn" id="btnPrev" onclick="prevPage()">Anterior</button>
          <button class="btn" id="btnNext" onclick="nextPage()">Próxima</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    const RAW_DATA = __DATA_JSON__;

    let chartPnLInstance = null;
    let simulatedTrades = [];
    let filteredTrades = [];
    let currentPage = 1;
    const pageSize = 50;

    function initPeriodSelector() {
      const select = document.getElementById('ctrlPeriod');
      if (!select || !RAW_DATA.window_info) return;
      select.innerHTML = '';
      
      const optAll = document.createElement('option');
      optAll.value = 'ALL';
      const totCandles = RAW_DATA.window_info.total_candles || 0;
      optAll.textContent = `🌐 Janela Completa (5 Dias: 4 Fechados + Hoje) [${totCandles.toLocaleString()} velas]`;
      optAll.selected = true;
      select.appendChild(optAll);
      
      const days = (RAW_DATA.window_info.days_list || []).slice().reverse();
      days.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d;
        const isToday = d === RAW_DATA.window_info.current_day;
        opt.textContent = isToday ? `📅 ${d} (Hoje em Andamento)` : `📅 ${d}`;
        select.appendChild(opt);
      });
    }

    function renderHistoricalRecords() {
      const rec = RAW_DATA.historical_records;
      if (!rec) return;

      if (rec.max_overall) {
        document.getElementById('histMaxOverallLen').innerHTML = `${rec.max_overall.streak_len} Velas Consecutivas <span style="font-size: 16px; color: ${rec.max_overall.direction === 'VERDE' ? 'var(--green-light)' : 'var(--red-light)'};">(${rec.max_overall.direction})</span>`;
        document.getElementById('histMaxOverallDates').innerText = `🕒 Início: ${rec.max_overall.start_time} até ${rec.max_overall.end_time}`;
        document.getElementById('histMaxOverallPrices').innerText = `Entrada: ${rec.max_overall.open_price} ➔ Saída: ${rec.max_overall.close_price}`;
      }

      if (rec.max_green) {
        document.getElementById('histMaxGreenLen').innerText = `${rec.max_green.streak_len} Velas Verdes`;
        document.getElementById('histMaxGreenDates').innerText = `🕒 ${rec.max_green.start_time} até ${rec.max_green.end_time}`;
        document.getElementById('histMaxGreenPrices').innerText = `Entrada: ${rec.max_green.open_price} ➔ Saída: ${rec.max_green.close_price}`;
      }

      if (rec.max_red) {
        document.getElementById('histMaxRedLen').innerText = `${rec.max_red.streak_len} Velas Vermelhas`;
        document.getElementById('histMaxRedDates').innerText = `🕒 ${rec.max_red.start_time} até ${rec.max_red.end_time}`;
        document.getElementById('histMaxRedPrices').innerText = `Entrada: ${rec.max_red.open_price} ➔ Saída: ${rec.max_red.close_price}`;
      }

      document.getElementById('histTotalCount').innerText = (rec.total_streaks || 0).toLocaleString();

      const distBadges = document.getElementById('histDistributionBadges');
      if (distBadges && rec.distribution) {
        distBadges.innerHTML = '';
        Object.keys(rec.distribution).sort((a,b) => parseInt(a) - parseInt(b)).forEach(len => {
          const count = rec.distribution[len];
          const div = document.createElement('div');
          div.className = 'streak-badge';
          div.style.background = 'rgba(227, 179, 65, 0.15)';
          div.style.borderColor = 'rgba(227, 179, 65, 0.4)';
          div.style.color = '#fff';
          div.innerHTML = `<span style="font-weight: 700;">${len} Velas</span> <span class="streak-count" style="color: var(--gold);">x${count}</span>`;
          distBadges.appendChild(div);
        });
      }

      const tableBody = document.getElementById('histStreaksTableBody');
      if (tableBody && rec.all_streaks) {
        tableBody.innerHTML = '';
        rec.all_streaks.forEach(s => {
          const tr = document.createElement('tr');
          const isGreen = s.direction === 'VERDE';
          tr.innerHTML = `
            <td><strong class="${isGreen ? 'val-green' : 'val-red'}">${isGreen ? '🟢 VERDE' : '🔴 VERMELHO'}</strong></td>
            <td><strong>${s.streak_len} velas</strong></td>
            <td>${s.start_time}</td>
            <td>${s.end_time}</td>
            <td>${s.open_price ? s.open_price.toFixed(2) : '-'}</td>
            <td>${s.close_price ? s.close_price.toFixed(2) : '-'}</td>
          `;
          tableBody.appendChild(tr);
        });
      }
    }

    function getActiveDataset() {
      const st = document.getElementById('ctrlStrategy').value;
      let baseDs = null;
      if (st === 'REV_STREAK') {
        const n = document.getElementById('ctrlCandleStreakCount').value;
        const dir = document.getElementById('ctrlCandleStreakDir').value;
        const key = `REV_STREAK_${n}_${dir}`;
        baseDs = RAW_DATA.strategies[key];
      } else {
        baseDs = RAW_DATA.strategies[st] || RAW_DATA.strategies['TREND_50S'];
      }

      if (!baseDs) {
        return {
          total_trades: 0,
          direct_wins: 0,
          direct_losses: 0,
          direct_rate: 0,
          loss_streaks: [],
          win_streaks: [],
          trades: []
        };
      }

      const periodEl = document.getElementById('ctrlPeriod');
      const selectedPeriod = periodEl ? periodEl.value : 'ALL';

      if (!selectedPeriod || selectedPeriod === 'ALL') {
        return baseDs;
      }

      // Filtrar trades pelo dia selecionado
      const filtered = baseDs.trades.filter(t => t.day === selectedPeriod);
      const wins = filtered.map(t => t.win);
      const tot = filtered.length;
      const w_sum = wins.reduce((acc, v) => acc + v, 0);

      // Calcular streaks para o período filtrado
      const loss_streaks_map = {};
      const win_streaks_map = {};
      let current_streak = 0;
      let current_val = null;

      wins.forEach(w => {
        if (w === current_val) {
          current_streak++;
        } else {
          if (current_val !== null) {
            if (current_val === 0) {
              loss_streaks_map[current_streak] = (loss_streaks_map[current_streak] || 0) + 1;
            } else {
              win_streaks_map[current_streak] = (win_streaks_map[current_streak] || 0) + 1;
            }
          }
          current_val = w;
          current_streak = 1;
        }
      });
      if (current_val !== null) {
        if (current_val === 0) {
          loss_streaks_map[current_streak] = (loss_streaks_map[current_streak] || 0) + 1;
        } else {
          win_streaks_map[current_streak] = (win_streaks_map[current_streak] || 0) + 1;
        }
      }

      const loss_streak_data = Object.keys(loss_streaks_map).sort((a,b)=>parseInt(a)-parseInt(b)).map(k => ({
        streak: `${k}L`,
        length: parseInt(k),
        count: loss_streaks_map[k],
        label: `${k}L (x${loss_streaks_map[k]})`
      }));

      const win_streak_data = Object.keys(win_streaks_map).sort((a,b)=>parseInt(a)-parseInt(b)).map(k => ({
        streak: `${k}W`,
        length: parseInt(k),
        count: win_streaks_map[k],
        label: `${k}W (x${win_streaks_map[k]})`
      }));

      return {
        total_trades: tot,
        direct_wins: w_sum,
        direct_losses: tot - w_sum,
        direct_rate: tot > 0 ? parseFloat((w_sum / tot * 100).toFixed(2)) : 0,
        loss_streaks: loss_streak_data,
        win_streaks: win_streak_data,
        trades: filtered
      };
    }

    window.addEventListener('DOMContentLoaded', () => {
      document.getElementById('headerSymbol').innerText = RAW_DATA.symbol;
      document.getElementById('headerDate').innerText = `${RAW_DATA.date}`;

      initPeriodSelector();
      renderHistoricalRecords();
      onStrategyChange();
    });

    function onPeriodChange() {
      const p = document.getElementById('ctrlPeriod').value;
      const subEl = document.getElementById('streaksSubHeader');
      if (subEl) {
        subEl.innerText = p === 'ALL' ? 'Contagem consolidada na janela de 5 dias' : `Contagem de streaks no dia ${p}`;
      }
      renderStreakBadges();
      recalcSimulation();
    }

    function onDurationChange() {
      const dur = document.getElementById('ctrlDuration').value;
      const thExit = document.getElementById('thExitHeader');
      if (thExit) {
        if (dur === '50s') thExit.innerText = 'Saída (:50)';
        else if (dur === '60s') thExit.innerText = 'Saída (:60 / M1)';
        else if (dur === '30s') thExit.innerText = 'Saída (:30)';
        else if (dur === '15s') thExit.innerText = 'Saída (:15)';
        else if (dur === '2m') thExit.innerText = 'Saída (+2m)';
        else if (dur === '5m') thExit.innerText = 'Saída (+5m)';
        else thExit.innerText = `Saída (${dur})`;
      }
      onStrategyChange();
    }

    function onStrategyChange() {
      const st = document.getElementById('ctrlStrategy').value;
      const stBadge = document.getElementById('headerStrategyBadge');
      const grpStreakCount = document.getElementById('groupCandleStreakCount');
      const grpStreakDir = document.getElementById('groupCandleStreakDir');
      const dur = document.getElementById('ctrlDuration') ? document.getElementById('ctrlDuration').value : '50s';
      const durLabel = ` | Expiração: ${dur}`;

      if (st === 'REV_STREAK') {
        grpStreakCount.style.display = 'block';
        grpStreakDir.style.display = 'block';
        const n = document.getElementById('ctrlCandleStreakCount').value;
        const dir = document.getElementById('ctrlCandleStreakDir').value;
        const dirLabel = dir === 'BOTH' ? 'Ambas as Cores' : (dir === 'RED' ? 'Após Vermelhos (RISE)' : 'Após Verdes (FALL)');
        stBadge.innerText = `Estratégia: Reversão após ${n} Velas (${dirLabel})${durLabel}`;
      } else {
        grpStreakCount.style.display = 'none';
        grpStreakDir.style.display = 'none';
        if (st === 'ALTERNADA_RISE_FALL') {
          stBadge.innerText = `Estratégia: Alternância Contínua (Inicia RISE -> FALL)${durLabel}`;
        } else if (st === 'ALTERNADA_FALL_RISE') {
          stBadge.innerText = `Estratégia: Alternância Contínua (Inicia FALL -> RISE)${durLabel}`;
        } else if (st === 'TRES_MOSQUETEIROS') {
          stBadge.innerText = `Estratégia: Três Mosqueteiros (Seguindo 3º Candle)${durLabel}`;
        } else if (st === 'CONTRA_MOSQUETEIROS') {
          stBadge.innerText = `Estratégia: Contra Mosqueteiros (Reversão no 3º Candle)${durLabel}`;
        } else if (st === 'TRES_MOSQUETEIROS_ESTRITO') {
          stBadge.innerText = `Estratégia: Três Mosqueteiros Estrito (Ciclos Fechados)${durLabel}`;
        } else if (st === 'MILHAO_MINORIA_M5') {
          stBadge.innerText = `Estratégia: Milhão Minoria (Blocos M5)${durLabel}`;
        } else if (st === 'MILHAO_MAIORIA_M5') {
          stBadge.innerText = `Estratégia: Milhão Maioria (Blocos M5)${durLabel}`;
        } else if (st === 'MILHAO_MINORIA_MOVEL') {
          stBadge.innerText = `Estratégia: Milhão Minoria Móvel (5 Velas)${durLabel}`;
        } else if (st === 'MILHAO_MAIORIA_MOVEL') {
          stBadge.innerText = `Estratégia: Milhão Maioria Móvel (5 Velas)${durLabel}`;
        } else if (st === 'TREND_50S') {
          stBadge.innerText = `Estratégia: Seguidor de Cor M1${durLabel}`;
        } else if (st === 'REVERSAL_50S') {
          stBadge.innerText = `Estratégia: Reversão de Cor M1${durLabel}`;
        } else {
          stBadge.innerText = `Estratégia: Opções Deriv${durLabel}`;
        }
      }

      renderStreakBadges();
      onModeChange();
    }

    function onModeChange() {
      const mode = document.getElementById('ctrlMode').value;
      const countSelect = document.getElementById('ctrlStreakCount');
      const badgeMode = document.getElementById('headerModeBadge');

      if (mode === 'DIRECT') {
        countSelect.disabled = true;
        badgeMode.innerText = '⚠️ Sem Escudo (100% Real)';
        badgeMode.className = 'badge badge-date';
      } else if (mode === 'LOSS_STREAK') {
        countSelect.disabled = false;
        badgeMode.innerText = '🛡️ Escudo: Streaks de Loss';
        badgeMode.className = 'badge badge-shield';
      } else {
        countSelect.disabled = false;
        badgeMode.innerText = '🛡️ Escudo: Streaks de Win';
        badgeMode.className = 'badge badge-shield';
      }

      recalcSimulation();
    }

    function renderStreakBadges() {
      const ds = getActiveDataset();
      const lossContainer = document.getElementById('lossStreaksBadges');
      const winContainer = document.getElementById('winStreaksBadges');

      lossContainer.innerHTML = '';
      winContainer.innerHTML = '';

      let maxL = 0;
      ds.loss_streaks.forEach(s => {
        if (s.length > maxL) maxL = s.length;
        const div = document.createElement('div');
        div.className = 'streak-badge streak-loss';
        div.innerHTML = `<span>${s.length}L</span> <span class="streak-count">x${s.count}</span>`;
        lossContainer.appendChild(div);
      });
      document.getElementById('kpiMaxLossStreak').innerText = `${maxL}L`;

      let maxW = 0;
      ds.win_streaks.forEach(s => {
        if (s.length > maxW) maxW = s.length;
        const div = document.createElement('div');
        div.className = 'streak-badge streak-win';
        div.innerHTML = `<span>${s.length}W</span> <span class="streak-count">x${s.count}</span>`;
        winContainer.appendChild(div);
      });
      document.getElementById('kpiMaxWinStreak').innerText = `${maxW}W`;
    }

    function recalcSimulation() {
      const ds = getActiveDataset();
      const mode = document.getElementById('ctrlMode').value;
      const targetCount = parseInt(document.getElementById('ctrlStreakCount').value) || 1;
      const maxGales = parseInt(document.getElementById('ctrlGaleLevel').value) || 0;
      const baseStake = parseFloat(document.getElementById('ctrlStake').value) || 0.35;
      const payoutVal = parseFloat(document.getElementById('ctrlPayout').value) || 0.88;
      const payoutFactor = payoutVal > 1.5 ? payoutVal / 100.0 : payoutVal;
      const multiplier = parseFloat(document.getElementById('ctrlMultiplier').value) || 2.40;

      const outcomes = {};
      for (let i = 0; i <= maxGales; i++) outcomes[`G${i}`] = 0;
      outcomes['TOTAL_LOSS'] = 0;

      let state = (mode === 'DIRECT') ? 'MASTER' : 'SLAVE';
      let consecLossesSlave = 0;
      let consecWinsSlave = 0;
      let masterGale = 0;
      let masterAccumLoss = 0.0;
      let currentRealPnl = 0.0;

      const pnlPoints = [0.0];
      const pnlLabels = ['Início'];

      let slaveOrdersCount = 0;
      let masterOrdersCount = 0;
      let masterWins = 0;
      let masterLosses = 0;
      let totalCycles = 0;

      simulatedTrades = [];

      ds.trades.forEach((t) => {
        const isMaster = (mode === 'DIRECT') || (state === 'MASTER');

        if (isMaster) {
          masterOrdersCount++;
          const stake = baseStake * Math.pow(multiplier, masterGale);
          let pnlDelta = 0;

          if (t.win === 1) {
            const winProfit = stake * payoutFactor;
            const cycleNet = winProfit - masterAccumLoss;
            currentRealPnl += winProfit;
            pnlDelta = winProfit;
            masterWins++;
            outcomes[`G${masterGale}`] = (outcomes[`G${masterGale}`] || 0) + 1;
            totalCycles++;

            simulatedTrades.push({
              ...t,
              account: 'REAL',
              stake: stake,
              pnlDelta: pnlDelta,
              cycleNet: cycleNet,
              galeLevel: masterGale
            });

            state = (mode === 'DIRECT') ? 'MASTER' : 'SLAVE';
            consecLossesSlave = 0;
            consecWinsSlave = 0;
            masterGale = 0;
            masterAccumLoss = 0.0;
          } else {
            masterAccumLoss += stake;
            currentRealPnl -= stake;
            pnlDelta = -stake;
            masterLosses++;

            simulatedTrades.push({
              ...t,
              account: 'REAL',
              stake: stake,
              pnlDelta: pnlDelta,
              cycleNet: -masterAccumLoss,
              galeLevel: masterGale
            });

            if (masterGale < maxGales) {
              masterGale++;
            } else {
              outcomes['TOTAL_LOSS'] = (outcomes['TOTAL_LOSS'] || 0) + 1;
              totalCycles++;
              state = (mode === 'DIRECT') ? 'MASTER' : 'SLAVE';
              consecLossesSlave = 0;
              consecWinsSlave = 0;
              masterGale = 0;
              masterAccumLoss = 0.0;
            }
          }

          pnlPoints.push(parseFloat(currentRealPnl.toFixed(2)));
          pnlLabels.push(t.time);
        } else {
          slaveOrdersCount++;
          simulatedTrades.push({
            ...t,
            account: 'DEMO',
            stake: 0,
            pnlDelta: 0,
            galeLevel: '-'
          });

          if (t.win === 1) {
            consecWinsSlave++;
            consecLossesSlave = 0;
            if (mode === 'WIN_STREAK' && consecWinsSlave >= targetCount) {
              state = 'MASTER';
              masterGale = 0;
              masterAccumLoss = 0.0;
            }
          } else {
            consecLossesSlave++;
            consecWinsSlave = 0;
            if (mode === 'LOSS_STREAK' && consecLossesSlave >= targetCount) {
              state = 'MASTER';
              masterGale = 0;
              masterAccumLoss = 0.0;
            }
          }
        }
      });

      // Atualiza KPIs
      document.getElementById('kpiRealTrades').innerText = masterOrdersCount.toLocaleString();
      const expSavedPct = ds.total_trades > 0 ? ((slaveOrdersCount / ds.total_trades) * 100).toFixed(1) : '0.0';
      document.getElementById('kpiFilteredSub').innerText = mode === 'DIRECT' 
        ? 'Sem filtro (100% exposto)' 
        : `Economizou ${slaveOrdersCount} ordens na Demo (${expSavedPct}%)`;

      if (maxGales === 0) {
        const directRate = masterOrdersCount > 0 ? ((masterWins / masterOrdersCount) * 100).toFixed(1) : '0.0';
        document.getElementById('kpiWinRate').innerText = `${directRate}%`;
        document.getElementById('kpiCyclesSub').innerText = `${masterWins} Wins / ${masterLosses} Losses`;
      } else {
        const winCycles = totalCycles - (outcomes['TOTAL_LOSS'] || 0);
        const cycleRate = totalCycles > 0 ? ((winCycles / totalCycles) * 100).toFixed(1) : '0.0';
        document.getElementById('kpiWinRate').innerText = `${cycleRate}%`;
        document.getElementById('kpiCyclesSub').innerText = `${winCycles} Wins / ${outcomes['TOTAL_LOSS'] || 0} Stops`;
      }

      const pnlEl = document.getElementById('kpiPnL');
      pnlEl.innerText = `${currentRealPnl >= 0 ? '+' : ''}$${currentRealPnl.toFixed(2)}`;
      pnlEl.className = `kpi-value ${currentRealPnl >= 0 ? 'val-green' : 'val-red'}`;

      let modeLabel = 'Sem Escudo';
      if (mode === 'LOSS_STREAK') modeLabel = `Escudo: ${targetCount}L`;
      else if (mode === 'WIN_STREAK') modeLabel = `Escudo: ${targetCount}W`;
      const galeLabel = maxGales === 0 ? 'Mão Fixa' : `Até G${maxGales}`;
      document.getElementById('kpiPnLSub').innerText = `${modeLabel} | ${galeLabel} | Payout: ${(payoutFactor * 100).toFixed(0)}%`;

      const titleEl = document.getElementById('logSectionTitle');
      if (titleEl) titleEl.innerText = `📋 Log Individual das Ordens (${ds.trades.length} Sinais / Entradas)`;

      // Cálculo da Banca / Saldo Necessário
      let totalBancaNeeded = 0;
      for (let i = 0; i <= maxGales; i++) {
        totalBancaNeeded += baseStake * Math.pow(multiplier, i);
      }

      const tableTitleEl = document.getElementById('martingaleTableTitle');
      if (tableTitleEl) tableTitleEl.innerText = maxGales === 0 ? '📊 Simulação Mão Fixa na Conta Real' : `📊 Ciclos de Gale na Conta Real (G0 até G${maxGales})`;
      const tableSumEl = document.getElementById('martingaleTableSummary');
      if (tableSumEl) {
        tableSumEl.innerHTML = `Total de Ciclos: ${totalCycles} | Stops de Ciclo: ${outcomes['TOTAL_LOSS'] || 0} &nbsp;|&nbsp; <span style="background: rgba(227, 179, 65, 0.15); color: var(--gold); border: 1px solid rgba(227, 179, 65, 0.4); padding: 3px 8px; border-radius: 6px; font-weight: 700;">💰 Saldo Necessário: $${totalBancaNeeded.toFixed(2)}</span>`;
      }

      document.getElementById('statSlaveOrders').innerText = slaveOrdersCount.toLocaleString();
      document.getElementById('statMasterOrders').innerText = masterOrdersCount.toLocaleString();
      document.getElementById('statExposureSaved').innerText = `${expSavedPct}%`;
      
      const currentStops = outcomes['TOTAL_LOSS'] || 0;
      document.getElementById('statStopsAvoided').innerText = mode === 'DIRECT' ? '0 stops' : `${currentStops} stops na Real`;

      const tbody = document.getElementById('martingaleTableBody');
      tbody.innerHTML = '';
      let cumCycles = 0;
      let cumStakeRequired = 0;

      for (let i = 0; i <= maxGales; i++) {
        const count = outcomes[`G${i}`] || 0;
        cumCycles += count;
        const stakeN = baseStake * Math.pow(multiplier, i);
        cumStakeRequired += stakeN;
        const pctInd = totalCycles > 0 ? (count / totalCycles * 100).toFixed(2) : '0.00';
        const pctCum = totalCycles > 0 ? (cumCycles / totalCycles * 100).toFixed(2) : '0.00';

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${i === 0 ? (maxGales === 0 ? 'Mão Fixa (G0)' : 'G0 (1ª Mão)') : `G${i} (${i}º Gale)`}</strong></td>
          <td>$${stakeN.toFixed(2)}</td>
          <td><strong style="color: var(--gold);">$${cumStakeRequired.toFixed(2)}</strong></td>
          <td><span class="val-green">${count}</span></td>
          <td>${pctInd}%</td>
          <td>${cumCycles}</td>
          <td><strong>${pctCum}%</strong></td>
        `;
        tbody.appendChild(tr);
      }

      if (maxGales > 0) {
        const lossTot = outcomes['TOTAL_LOSS'] || 0;
        const pctLoss = totalCycles > 0 ? (lossTot / totalCycles * 100).toFixed(2) : '0.00';
        const trLoss = document.createElement('tr');
        trLoss.innerHTML = `
          <td><strong class="val-red">LOSS TOTAL (Stop Ciclo)</strong></td>
          <td>-</td>
          <td><strong class="val-red">-$${totalBancaNeeded.toFixed(2)}</strong></td>
          <td><span class="val-red">${lossTot}</span></td>
          <td>${pctLoss}%</td>
          <td>-</td>
          <td>-</td>
        `;
        tbody.appendChild(trLoss);
      }

      renderPnLChart(pnlLabels, pnlPoints);
      filterTrades();
    }

    function renderPnLChart(labels, dataPoints) {
      const ctx = document.getElementById('chartPnL').getContext('2d');
      if (chartPnLInstance) chartPnLInstance.destroy();

      const step = Math.max(1, Math.ceil(labels.length / 250));
      const subLabels = labels.filter((_, i) => i % step === 0);
      const subData = dataPoints.filter((_, i) => i % step === 0);

      chartPnLInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels: subLabels,
          datasets: [{
            label: 'Saldo Real Acumulado ($)',
            data: subData,
            borderColor: function(context) {
              const chart = context.chart;
              const {ctx: c, chartArea, scales} = chart;
              if (!chartArea || !scales || !scales.y) return '#2ea043';
              const y0 = scales.y.getPixelForValue(0);
              const gradient = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
              if (y0 <= chartArea.top) return '#da3633';
              if (y0 >= chartArea.bottom) return '#2ea043';
              const stopGreen = Math.max(0, Math.min(1, y0 / chartArea.bottom));
              gradient.addColorStop(0, '#2ea043');
              gradient.addColorStop(stopGreen, '#2ea043');
              gradient.addColorStop(stopGreen, '#da3633');
              gradient.addColorStop(1, '#da3633');
              return gradient;
            },
            borderWidth: 2,
            tension: 0.1,
            fill: false,
            pointRadius: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => ` Saldo: $${parseFloat(ctx.parsed.y).toFixed(2)}`
              }
            }
          },
          scales: {
            x: {
              grid: { color: '#21262d' },
              ticks: { color: '#8b949e', maxRotation: 0, autoSkip: true, maxTicksLimit: 12 }
            },
            y: {
              grid: { color: '#21262d' },
              ticks: {
                color: '#8b949e',
                callback: (val) => `$${val}`
              }
            }
          }
        }
      });
    }

    function filterTrades() {
      const accFilter = document.getElementById('filterAccount').value;
      const resFilter = document.getElementById('filterResult').value;
      const galeFilter = document.getElementById('filterGale').value;
      const search = (document.getElementById('searchTrade').value || '').toLowerCase();

      filteredTrades = simulatedTrades.filter(t => {
        if (accFilter !== 'ALL' && t.account !== accFilter) return false;
        if (resFilter !== 'ALL' && t.result !== resFilter) return false;
        if (galeFilter !== 'ALL') {
          if (t.account !== 'REAL') return false;
          if (String(t.galeLevel) !== galeFilter) return false;
        }
        if (search && !t.time.toLowerCase().includes(search)) return false;
        return true;
      });

      currentPage = 1;
      renderTablePage();
    }

    function renderTablePage() {
      const tbody = document.getElementById('tradesTableBody');
      tbody.innerHTML = '';

      const total = filteredTrades.length;
      const start = (currentPage - 1) * pageSize;
      const end = Math.min(start + pageSize, total);
      const pageItems = filteredTrades.slice(start, end);

      pageItems.forEach((t, i) => {
        const tr = document.createElement('tr');
        const isWin = t.result === 'WIN';
        const isReal = t.account === 'REAL';

        let pnlText = '-';
        if (isReal) {
          const pVal = t.pnlDelta;
          pnlText = `<span class="${pVal >= 0 ? 'val-green' : 'val-red'}"><strong>${pVal >= 0 ? '+' : ''}$${pVal.toFixed(2)}</strong></span>`;
        }

        const badgeAcc = isReal 
          ? `<span class="badge" style="background: rgba(227, 179, 65, 0.2); color: var(--gold); border: 1px solid rgba(227, 179, 65, 0.4);">⭐ REAL (G${t.galeLevel})</span>`
          : '<span class="badge" style="background: rgba(110, 118, 129, 0.2); color: #8b949e;">🛡️ DEMO</span>';

        tr.innerHTML = `
          <td>${start + i + 1}</td>
          <td>${badgeAcc}</td>
          <td><strong>${t.time}</strong></td>
          <td style="color: #8b949e; font-size: 12px;">${t.prev_dir}</td>
          <td><strong style="color: ${t.contract === 'RISE' ? 'var(--green-light)' : 'var(--red-light)'}">${t.contract}</strong></td>
          <td>${t.entry.toFixed(2)}</td>
          <td>${t.exit.toFixed(2)}</td>
          <td class="${t.delta >= 0 ? 'val-green' : 'val-red'}">${t.delta >= 0 ? '+' : ''}${t.delta.toFixed(2)}</td>
          <td><span class="${isWin ? 'val-green' : 'val-red'}"><strong>${t.result}</strong></span></td>
          <td>${isReal ? `$${t.stake.toFixed(2)}` : '-'}</td>
          <td>${pnlText}</td>
        `;
        tbody.appendChild(tr);
      });

      document.getElementById('paginationInfo').innerText = total > 0 
        ? `Exibindo ${start + 1} a ${end} de ${total.toLocaleString()} ordens filtradas`
        : 'Nenhuma ordem encontrada';

      document.getElementById('btnPrev').disabled = currentPage <= 1;
      document.getElementById('btnNext').disabled = end >= total;
    }

    function prevPage() {
      if (currentPage > 1) {
        currentPage--;
        renderTablePage();
      }
    }

    function nextPage() {
      const totalPages = Math.ceil(filteredTrades.length / pageSize);
      if (currentPage < totalPages) {
        currentPage++;
        renderTablePage();
      }
    }

    function exportCSV() {
      if (!simulatedTrades || simulatedTrades.length === 0) {
        alert('Nenhum dado para exportar.');
        return;
      }
      let csv = 'ID,Conta,Horario_GMT,Contexto,Contrato,Entrada,Saida,Variacao,Resultado,Stake,Impacto_Saldo\\n';
      simulatedTrades.forEach((t, i) => {
        csv += `${i+1},${t.account},${t.time},"${t.prev_dir}",${t.contract},${t.entry},${t.exit},${t.delta},${t.result},${t.stake},${t.pnlDelta}\\n`;
      });
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.setAttribute('href', url);
      link.setAttribute('download', `trades_backtest_${RAW_DATA.symbol}_5dias.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  </script>
</body>
</html>
"""

def generate():
    json_path = os.path.join("data", "backtest_result.json")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    json_str = json.dumps(data)
    final_html = HTML_TEMPLATE.replace("__DATA_JSON__", json_str)

    web_path = os.path.join("web", "backtest_rise_15s.html")
    with open(web_path, "w", encoding="utf-8") as f:
        f.write(final_html)

    print(f"Sucesso! Arquivo gerado em {web_path} ({len(final_html):,} bytes)")

if __name__ == "__main__":
    generate()
