import json
import os

def generate():
    json_path = os.path.join("data", "backtest_result.json")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    json_str = json.dumps(data)

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Deriv Quant - Backtest Seguidor de Vela M1 (50s) | R_100</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
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
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 24px;
    }}
    .container {{ max-width: 1400px; margin: 0 auto; }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 16px;
    }}
    .header-title h1 {{
      font-size: 24px;
      color: var(--text-bright);
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
    }}
    .badge-symbol {{ background: rgba(88, 166, 255, 0.15); color: var(--blue-light); border: 1px solid rgba(88, 166, 255, 0.3); }}
    .badge-date {{ background: rgba(210, 153, 34, 0.15); color: var(--yellow); border: 1px solid rgba(210, 153, 34, 0.3); }}
    .badge-strategy {{ background: rgba(46, 160, 67, 0.15); color: var(--green-light); border: 1px solid rgba(46, 160, 67, 0.3); }}
    .badge-shield {{ background: rgba(137, 87, 229, 0.15); color: var(--purple); border: 1px solid rgba(137, 87, 229, 0.3); }}
    
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .kpi-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 18px;
    }}
    .kpi-title {{ font-size: 13px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
    .kpi-value {{ font-size: 28px; font-weight: 700; color: var(--text-bright); }}
    .kpi-sub {{ font-size: 12px; margin-top: 4px; color: #8b949e; }}
    .val-green {{ color: var(--green-light); }}
    .val-red {{ color: var(--red-light); }}
    .val-blue {{ color: var(--blue-light); }}
    .val-gold {{ color: #e3b341; }}

    .section-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 20px;
      margin-bottom: 24px;
    }}
    .section-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .section-title {{ font-size: 18px; font-weight: 600; color: var(--text-bright); display: flex; align-items: center; gap: 8px; }}

    .streaks-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 16px;
    }}
    .streak-badge {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 14px;
      border-radius: 8px;
      font-weight: 600;
      font-size: 14px;
      border: 1px solid;
    }}
    .streak-loss {{
      background: rgba(248, 81, 73, 0.1);
      border-color: rgba(248, 81, 73, 0.3);
      color: var(--red-light);
    }}
    .streak-win {{
      background: rgba(46, 160, 67, 0.1);
      border-color: rgba(46, 160, 67, 0.3);
      color: var(--green-light);
    }}
    .streak-count {{
      background: rgba(255, 255, 255, 0.12);
      padding: 2px 7px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 700;
    }}

    .controls-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 16px;
      background: rgba(255,255,255,0.02);
      padding: 16px;
      border-radius: 8px;
      border: 1px solid var(--border);
      margin-bottom: 20px;
    }}
    .control-group label {{
      display: block;
      font-size: 12px;
      font-weight: 600;
      color: #8b949e;
      margin-bottom: 6px;
    }}
    .control-group input, .control-group select {{
      width: 100%;
      background: #0d1117;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 12px;
      color: var(--text-bright);
      font-size: 14px;
      outline: none;
    }}
    .control-group input:focus, .control-group select:focus {{
      border-color: var(--blue-light);
    }}
    .control-group select:disabled {{
      opacity: 0.4;
      cursor: not-allowed;
    }}

    .shield-banner {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      background: rgba(137, 87, 229, 0.08);
      border: 1px solid rgba(137, 87, 229, 0.3);
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 20px;
    }}
    .shield-stat-title {{ font-size: 11px; text-transform: uppercase; color: #8b949e; }}
    .shield-stat-val {{ font-size: 18px; font-weight: 700; color: var(--text-bright); margin-top: 2px; }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      padding: 10px 14px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    th {{
      background: rgba(255, 255, 255, 0.03);
      color: #8b949e;
      font-weight: 600;
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.5px;
    }}
    tr:hover {{ background: rgba(255, 255, 255, 0.02); }}
    .tag-win {{ color: var(--green-light); font-weight: 600; }}
    .tag-loss {{ color: var(--red-light); font-weight: 600; }}
    .tag-rise {{ color: var(--green-light); font-weight: 600; }}
    .tag-fall {{ color: var(--red-light); font-weight: 600; }}

    .acc-demo {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      background: rgba(88, 166, 255, 0.15);
      color: var(--blue-light);
      border: 1px solid rgba(88, 166, 255, 0.3);
    }}
    .acc-real {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      background: rgba(227, 179, 65, 0.15);
      color: var(--val-gold);
      border: 1px solid rgba(227, 179, 65, 0.4);
    }}

    .table-footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 14px;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .btn {{
      background: #21262d;
      color: var(--text-bright);
      border: 1px solid var(--border);
      padding: 6px 14px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 13px;
      transition: background 0.2s;
    }}
    .btn:hover {{ background: #30363d; }}
    .btn:disabled {{ opacity: 0.4; cursor: not-allowed; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="header-title">
        <h1>Dashboard Quantitativo: Backtest Deriv</h1>
        <span class="badge badge-symbol" id="headerSymbol">R_100</span>
        <span class="badge badge-strategy" id="headerStrategyBadge">Estratégia: Seguidor de Vela (50s)</span>
        <span class="badge badge-shield" id="headerModeBadge">🛡️ Escudo Master/Slave</span>
        <span class="badge badge-date" id="headerDate">21/11/2026 (00:00:00 às 23:59:59 GMT Deriv)</span>
        <span class="badge" style="background: rgba(46, 160, 67, 0.15); color: #3fb950; border: 1px solid rgba(46, 160, 67, 0.4);">🕒 Horário Oficial Deriv (GMT)</span>
      </div>
      <div>
        <button class="btn" onclick="exportCSV()">📥 Exportar CSV dos Trades</button>
      </div>
    </header>

    <!-- KPIs -->
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
        <div class="kpi-sub">Geral do ativo no dia</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Maior Sequência de Vitórias</div>
        <div class="kpi-value val-green" id="kpiMaxWinStreak">-</div>
        <div class="kpi-sub">Geral do ativo no dia</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Resultado Líquido (Conta Real)</div>
        <div class="kpi-value val-red" id="kpiPnL">-</div>
        <div class="kpi-sub" id="kpiPnLSub">-</div>
      </div>
    </div>

    <!-- Seção de Streaks -->
    <div class="section-card">
      <div class="section-header">
        <div class="section-title">
          <span>🔥 Sequências Consecutivas (Streaks) da Estratégia</span>
        </div>
        <span style="font-size: 13px; color: #8b949e;">Contagem exata de quantas vezes cada sequência consecutiva ocorreu no dia</span>
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
        <!-- Seletor de Estratégia -->
        <div class="control-group">
          <label>Estratégia Operacional</label>
          <select id="ctrlStrategy" onchange="onStrategyChange()">
            <option value="REV_STREAK" selected>🔁 Reversão por Streaks de Cores (Exaustão 6 a 15 Velas) [50s]</option>
            <option value="ALTERNADA_RISE_FALL">🔀 Alternância Contínua (Inicia RISE -> FALL -> RISE...) [50s]</option>
            <option value="ALTERNADA_FALL_RISE">🔀 Alternância Contínua (Inicia FALL -> RISE -> FALL...) [50s]</option>
            <option value="TRES_MOSQUETEIROS">⚔️ Três Mosqueteiros (2 Velas Iguais -> 3ª na Mesma Direção) [50s]</option>
            <option value="CONTRA_MOSQUETEIROS">🛡️ Contra Mosqueteiros (2 Velas Iguais -> Reversão na 3ª) [50s]</option>
            <option value="TRES_MOSQUETEIROS_ESTRITO">🎯 Três Mosqueteiros Estrito (Ciclos Fechados de 3 Velas) [50s]</option>
            <option value="MILHAO_MINORIA_M5">🎯 Milhão Minoria (Blocos 5 min / M5) [50s]</option>
            <option value="MILHAO_MAIORIA_M5">🔥 Milhão Maioria (Blocos 5 min / M5) [50s]</option>
            <option value="MILHAO_MINORIA_MOVEL">⚡ Milhão Minoria Móvel (5 velas contínuas) [50s]</option>
            <option value="MILHAO_MAIORIA_MOVEL">⚡ Milhão Maioria Móvel (5 velas contínuas) [50s]</option>
            <option value="TREND_50S">🟢 Seguidor de Cor M1 (Verde=Rise / Vermelho=Fall) [50s]</option>
            <option value="REVERSAL_50S">🔄 Reversão de Cor M1 (Verde=Fall / Vermelho=Rise) [50s]</option>
            <option value="RISE_15S">📈 Fixo Rise 15s (Estratégia anterior)</option>
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
            <option value="RED">Apenas após Vermelhos (Entra RISE)</option>
            <option value="GREEN">Apenas após Verdes (Entra FALL)</option>
          </select>
        </div>

        <!-- 1 - Modo de Operação -->
        <div class="control-group">
          <label>Modo de Operação</label>
          <select id="ctrlMode" onchange="onModeChange()">
            <option value="LOSS_STREAK">1 - Streaks de Derrotas (Loss)</option>
            <option value="WIN_STREAK">2 - Streaks de Vitórias (Win)</option>
            <option value="DIRECT" selected>3 - Sem Escudo (Direto na Real)</option>
          </select>
        </div>

        <!-- 2 - Quantidade de Streaks (1 a 15) -->
        <div class="control-group" id="groupStreakCount">
          <label>Quantidade de Streaks (Gatilho)</label>
          <select id="ctrlStreakCount" onchange="recalcSimulation()">
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
            <option value="11">11 ocorrências consecutivas (11x)</option>
            <option value="12">12 ocorrências consecutivas (12x)</option>
            <option value="13">13 ocorrências consecutivas (13x)</option>
            <option value="14">14 ocorrências consecutivas (14x)</option>
            <option value="15">15 ocorrências consecutivas (15x)</option>
          </select>
        </div>

        <!-- 3 - Gales na Conta Real -->
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
          <input type="number" id="ctrlPayout" value="0.88" step="0.01" min="0.1" max="2.0" oninput="recalcSimulation()">
        </div>

        <!-- Multiplicador -->
        <div class="control-group" id="groupMultiplier">
          <label>Multiplicador do Gale</label>
          <input type="number" id="ctrlMultiplier" value="2.40" step="0.05" min="1.5" max="5.0" oninput="recalcSimulation()">
        </div>
      </div>

      <!-- Banner de Eficiência do Escudo -->
      <div class="shield-banner" id="shieldBanner">
        <div>
          <div class="shield-stat-title">Ordens no Escudo (Demo)</div>
          <div class="shield-stat-val val-blue" id="statSlaveOrders">-</div>
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

      <!-- Resumo dos Ciclos de Gale da Master -->
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
          <input type="text" id="searchTrade" placeholder="Filtrar hora (ex: 14:2)..." style="background: #0d1117; border: 1px solid var(--border); color: #fff; padding: 4px 10px; border-radius: 4px; font-size: 12px;" oninput="filterTrades()">
          <select id="filterResult" style="background: #0d1117; border: 1px solid var(--border); color: #fff; padding: 4px 10px; border-radius: 4px; font-size: 12px;" onchange="filterTrades()">
            <option value="ALL">Todos os Resultados</option>
            <option value="WIN">Apenas Wins</option>
            <option value="LOSS">Apenas Losses</option>
          </select>
          <select id="filterGale" style="background: #0d1117; border: 1px solid var(--border); color: #fff; padding: 4px 10px; border-radius: 4px; font-size: 12px;" onchange="filterTrades()">
            <option value="ALL">Todos os Níveis de Gale</option>
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
              <th>Saída (:50)</th>
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
        <div id="paginationInfo" style="font-size: 13px; color: #8b949e;">Exibindo 1 a 50 de 1.426</div>
        <div style="display: flex; gap: 8px;">
          <button class="btn" id="btnPrev" onclick="prevPage()">Anterior</button>
          <button class="btn" id="btnNext" onclick="nextPage()">Próxima</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    const RAW_DATA = {json_str};

    let chartPnLInstance = null;
    let simulatedTrades = [];
    let filteredTrades = [];
    let currentPage = 1;
    const pageSize = 50;

    function getActiveDataset() {{
      const st = document.getElementById('ctrlStrategy').value;
      if (st === 'REV_STREAK') {{
        const n = document.getElementById('ctrlCandleStreakCount').value;
        const dir = document.getElementById('ctrlCandleStreakDir').value;
        const key = `REV_STREAK_${{n}}_${{dir}}`;
        return RAW_DATA.strategies[key] || {{
          total_trades: 0,
          direct_wins: 0,
          direct_losses: 0,
          direct_rate: 0,
          loss_streaks: [],
          win_streaks: [],
          trades: []
        }};
      }}
      return RAW_DATA.strategies[st] || RAW_DATA.strategies['TREND_50S'];
    }}

    window.addEventListener('DOMContentLoaded', () => {{
      document.getElementById('headerSymbol').innerText = RAW_DATA.symbol;
      document.getElementById('headerDate').innerText = `${{RAW_DATA.date}} (24h)`;

      onStrategyChange();
    }});

    function onStrategyChange() {{
      const st = document.getElementById('ctrlStrategy').value;
      const stBadge = document.getElementById('headerStrategyBadge');
      const grpStreakCount = document.getElementById('groupCandleStreakCount');
      const grpStreakDir = document.getElementById('groupCandleStreakDir');

      if (st === 'REV_STREAK') {{
        grpStreakCount.style.display = 'block';
        grpStreakDir.style.display = 'block';
        const n = document.getElementById('ctrlCandleStreakCount').value;
        const dir = document.getElementById('ctrlCandleStreakDir').value;
        const dirLabel = dir === 'BOTH' ? 'Ambas as Cores' : (dir === 'RED' ? 'Após Vermelhos (RISE)' : 'Após Verdes (FALL)');
        stBadge.innerText = `Estratégia: Reversão após ${{n}} Velas (${{dirLabel}}) [50s]`;
      }} else {{
        grpStreakCount.style.display = 'none';
        grpStreakDir.style.display = 'none';
        if (st === 'ALTERNADA_RISE_FALL') {{
          stBadge.innerText = 'Estratégia: Alternância Contínua (Inicia RISE -> FALL) [50s]';
        }} else if (st === 'ALTERNADA_FALL_RISE') {{
          stBadge.innerText = 'Estratégia: Alternância Contínua (Inicia FALL -> RISE) [50s]';
        }} else if (st === 'TRES_MOSQUETEIROS') {{
          stBadge.innerText = 'Estratégia: Três Mosqueteiros (Seguindo 3º Candle) [50s]';
        }} else if (st === 'CONTRA_MOSQUETEIROS') {{
          stBadge.innerText = 'Estratégia: Contra Mosqueteiros (Reversão no 3º Candle) [50s]';
        }} else if (st === 'TRES_MOSQUETEIROS_ESTRITO') {{
          stBadge.innerText = 'Estratégia: Três Mosqueteiros Estrito (Ciclos Fechados) [50s]';
        }} else if (st === 'MILHAO_MINORIA_M5') {{
          stBadge.innerText = 'Estratégia: Milhão Minoria (Blocos M5 / 50s)';
        }} else if (st === 'MILHAO_MAIORIA_M5') {{
          stBadge.innerText = 'Estratégia: Milhão Maioria (Blocos M5 / 50s)';
        }} else if (st === 'MILHAO_MINORIA_MOVEL') {{
          stBadge.innerText = 'Estratégia: Milhão Minoria Móvel (5 Velas / 50s)';
        }} else if (st === 'MILHAO_MAIORIA_MOVEL') {{
          stBadge.innerText = 'Estratégia: Milhão Maioria Móvel (5 Velas / 50s)';
        }} else if (st === 'TREND_50S') {{
          stBadge.innerText = 'Estratégia: Seguidor de Vela (50s)';
        }} else if (st === 'REVERSAL_50S') {{
          stBadge.innerText = 'Estratégia: Reversão de Vela (50s)';
        }} else {{
          stBadge.innerText = 'Estratégia: Rise Fixo 15s';
        }}
      }}

      renderStreakBadges();
      onModeChange();
    }}

    function onModeChange() {{
      const mode = document.getElementById('ctrlMode').value;
      const countSelect = document.getElementById('ctrlStreakCount');
      const badgeMode = document.getElementById('headerModeBadge');

      if (mode === 'DIRECT') {{
        countSelect.disabled = true;
        badgeMode.innerText = '⚠️ Sem Escudo (100% Real)';
        badgeMode.className = 'badge badge-date';
      }} else if (mode === 'LOSS_STREAK') {{
        countSelect.disabled = false;
        badgeMode.innerText = '🛡️ Escudo: Streaks de Loss';
        badgeMode.className = 'badge badge-shield';
      }} else {{
        countSelect.disabled = false;
        badgeMode.innerText = '🛡️ Escudo: Streaks de Win';
        badgeMode.className = 'badge badge-shield';
      }}

      recalcSimulation();
    }}

    function renderStreakBadges() {{
      const ds = getActiveDataset();
      const lossContainer = document.getElementById('lossStreaksBadges');
      const winContainer = document.getElementById('winStreaksBadges');

      lossContainer.innerHTML = '';
      winContainer.innerHTML = '';

      let maxL = 0;
      ds.loss_streaks.forEach(s => {{
        if (s.length > maxL) maxL = s.length;
        const div = document.createElement('div');
        div.className = 'streak-badge streak-loss';
        div.innerHTML = `<span>${{s.length}}L</span> <span class="streak-count">x${{s.count}}</span>`;
        lossContainer.appendChild(div);
      }});
      document.getElementById('kpiMaxLossStreak').innerText = `${{maxL}}L`;

      let maxW = 0;
      ds.win_streaks.forEach(s => {{
        if (s.length > maxW) maxW = s.length;
        const div = document.createElement('div');
        div.className = 'streak-badge streak-win';
        div.innerHTML = `<span>${{s.length}}W</span> <span class="streak-count">x${{s.count}}</span>`;
        winContainer.appendChild(div);
      }});
      document.getElementById('kpiMaxWinStreak').innerText = `${{maxW}}W`;
    }}

    function recalcSimulation() {{
      const ds = getActiveDataset();
      const mode = document.getElementById('ctrlMode').value;
      const targetCount = parseInt(document.getElementById('ctrlStreakCount').value) || 1;
      const maxGales = parseInt(document.getElementById('ctrlGaleLevel').value) || 0;
      const baseStake = parseFloat(document.getElementById('ctrlStake').value) || 1.0;
      const payoutVal = parseFloat(document.getElementById('ctrlPayout').value) || 0.88;
      const payoutFactor = payoutVal > 1.5 ? payoutVal / 100.0 : payoutVal;
      const multiplier = parseFloat(document.getElementById('ctrlMultiplier').value) || 2.15;

      const outcomes = {{}};
      for (let i = 0; i <= maxGales; i++) outcomes[`G${{i}}`] = 0;
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

      ds.trades.forEach((t) => {{
        const isMaster = (mode === 'DIRECT') || (state === 'MASTER');

        if (isMaster) {{
          masterOrdersCount++;
          const stake = baseStake * Math.pow(multiplier, masterGale);
          let pnlDelta = 0;

          if (t.win === 1) {{
            const winProfit = stake * payoutFactor;
            const cycleNet = winProfit - masterAccumLoss;
            currentRealPnl += winProfit;
            pnlDelta = winProfit;
            masterWins++;
            outcomes[`G${{masterGale}}`] = (outcomes[`G${{masterGale}}`] || 0) + 1;
            totalCycles++;

            simulatedTrades.push({{
              ...t,
              account: 'REAL',
              stake: stake,
              pnlDelta: pnlDelta,
              cycleNet: cycleNet,
              galeLevel: masterGale
            }});

            state = (mode === 'DIRECT') ? 'MASTER' : 'SLAVE';
            consecLossesSlave = 0;
            consecWinsSlave = 0;
            masterGale = 0;
            masterAccumLoss = 0.0;
          }} else {{
            masterAccumLoss += stake;
            currentRealPnl -= stake;
            pnlDelta = -stake;
            masterLosses++;

            simulatedTrades.push({{
              ...t,
              account: 'REAL',
              stake: stake,
              pnlDelta: pnlDelta,
              cycleNet: -masterAccumLoss,
              galeLevel: masterGale
            }});

            if (masterGale < maxGales) {{
              masterGale++;
            }} else {{
              outcomes['TOTAL_LOSS'] = (outcomes['TOTAL_LOSS'] || 0) + 1;
              totalCycles++;
              state = (mode === 'DIRECT') ? 'MASTER' : 'SLAVE';
              consecLossesSlave = 0;
              consecWinsSlave = 0;
              masterGale = 0;
              masterAccumLoss = 0.0;
            }}
          }}

          pnlPoints.push(parseFloat(currentRealPnl.toFixed(2)));
          pnlLabels.push(t.time);
        }} else {{
          slaveOrdersCount++;
          simulatedTrades.push({{
            ...t,
            account: 'DEMO',
            stake: 0,
            pnlDelta: 0,
            galeLevel: '-'
          }});

          if (t.win === 1) {{
            consecWinsSlave++;
            consecLossesSlave = 0;
            if (mode === 'WIN_STREAK' && consecWinsSlave >= targetCount) {{
              state = 'MASTER';
              masterGale = 0;
              masterAccumLoss = 0.0;
            }}
          }} else {{
            consecLossesSlave++;
            consecWinsSlave = 0;
            if (mode === 'LOSS_STREAK' && consecLossesSlave >= targetCount) {{
              state = 'MASTER';
              masterGale = 0;
              masterAccumLoss = 0.0;
            }}
          }}
        }}
      }});

      // Atualiza KPIs
      document.getElementById('kpiRealTrades').innerText = masterOrdersCount.toLocaleString();
      const expSavedPct = ((slaveOrdersCount / ds.total_trades) * 100).toFixed(1);
      document.getElementById('kpiFilteredSub').innerText = mode === 'DIRECT' 
        ? 'Sem filtro (100% exposto)' 
        : `Economizou ${{slaveOrdersCount}} ordens na Demo (${{expSavedPct}}%)`;

      if (maxGales === 0) {{
        const directRate = masterOrdersCount > 0 ? ((masterWins / masterOrdersCount) * 100).toFixed(1) : '0.0';
        document.getElementById('kpiWinRate').innerText = `${{directRate}}%`;
        document.getElementById('kpiCyclesSub').innerText = `${{masterWins}} Wins / ${{masterLosses}} Losses`;
      }} else {{
        const winCycles = totalCycles - (outcomes['TOTAL_LOSS'] || 0);
        const cycleRate = totalCycles > 0 ? ((winCycles / totalCycles) * 100).toFixed(1) : '0.0';
        document.getElementById('kpiWinRate').innerText = `${{cycleRate}}%`;
        document.getElementById('kpiCyclesSub').innerText = `${{winCycles}} Wins / ${{outcomes['TOTAL_LOSS'] || 0}} Stops`;
      }}

      const pnlEl = document.getElementById('kpiPnL');
      pnlEl.innerText = `${{currentRealPnl >= 0 ? '+' : ''}}$${{currentRealPnl.toFixed(2)}}`;
      pnlEl.className = `kpi-value ${{currentRealPnl >= 0 ? 'val-green' : 'val-red'}}`;

      let modeLabel = 'Sem Escudo';
      if (mode === 'LOSS_STREAK') modeLabel = `Escudo: ${{targetCount}}L`;
      else if (mode === 'WIN_STREAK') modeLabel = `Escudo: ${{targetCount}}W`;
      const galeLabel = maxGales === 0 ? 'Mão Fixa' : `Até G${{maxGales}}`;
      document.getElementById('kpiPnLSub').innerText = `${{modeLabel}} | ${{galeLabel}} | Payout: ${{(payoutFactor * 100).toFixed(0)}}%`;

      const titleEl = document.getElementById('logSectionTitle');
      if (titleEl) titleEl.innerText = `📋 Log Individual das Ordens (${{ds.trades.length}} Sinais / Entradas)`;

      let totalBancaNeeded = 0;
      for (let i = 0; i <= maxGales; i++) {{
        totalBancaNeeded += baseStake * Math.pow(multiplier, i);
      }}

      const tableTitleEl = document.getElementById('martingaleTableTitle');
      if (tableTitleEl) tableTitleEl.innerText = maxGales === 0 ? '📊 Simulação Mão Fixa na Conta Real' : `📊 Ciclos de Gale na Conta Real (G0 até G${{maxGales}})`;
      const tableSumEl = document.getElementById('martingaleTableSummary');
      if (tableSumEl) {{
        tableSumEl.innerHTML = `Total de Ciclos: ${{totalCycles}} | Stops de Ciclo: ${{outcomes['TOTAL_LOSS'] || 0}} &nbsp;|&nbsp; <span style="background: rgba(227, 179, 65, 0.15); color: var(--val-gold); border: 1px solid rgba(227, 179, 65, 0.4); padding: 3px 8px; border-radius: 6px; font-weight: 700;">💰 Saldo Necessário: $${{totalBancaNeeded.toFixed(2)}}</span>`;
      }}

      document.getElementById('statSlaveOrders').innerText = slaveOrdersCount.toLocaleString();
      document.getElementById('statMasterOrders').innerText = masterOrdersCount.toLocaleString();
      document.getElementById('statExposureSaved').innerText = `${{expSavedPct}}%`;
      
      const currentStops = outcomes['TOTAL_LOSS'] || 0;
      document.getElementById('statStopsAvoided').innerText = mode === 'DIRECT' ? '0 stops' : `${{currentStops}} stops na Real`;

      const tbody = document.getElementById('martingaleTableBody');
      tbody.innerHTML = '';
      let cumCycles = 0;
      let cumStakeRequired = 0;

      for (let i = 0; i <= maxGales; i++) {{
        const count = outcomes[`G${{i}}`] || 0;
        cumCycles += count;
        const stakeN = baseStake * Math.pow(multiplier, i);
        cumStakeRequired += stakeN;
        const pctInd = totalCycles > 0 ? (count / totalCycles * 100).toFixed(2) : '0.00';
        const pctCum = totalCycles > 0 ? (cumCycles / totalCycles * 100).toFixed(2) : '0.00';

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${{i === 0 ? (maxGales === 0 ? 'Mão Fixa (G0)' : 'G0 (1ª Mão)') : `G${{i}} (${{i}}º Gale)`}}</strong></td>
          <td>$${{stakeN.toFixed(2)}}</td>
          <td><strong style="color: var(--val-gold);">$${{cumStakeRequired.toFixed(2)}}</strong></td>
          <td><span class="val-green">${{count}}</span></td>
          <td>${{pctInd}}%</td>
          <td>${{cumCycles}}</td>
          <td><strong>${{pctCum}}%</strong></td>
        `;
        tbody.appendChild(tr);
      }}

      if (maxGales > 0) {{
        const lossTot = outcomes['TOTAL_LOSS'] || 0;
        const pctLoss = totalCycles > 0 ? (lossTot / totalCycles * 100).toFixed(2) : '0.00';
        const trLoss = document.createElement('tr');
        trLoss.innerHTML = `
          <td><strong class="val-red">LOSS TOTAL (Stop Ciclo)</strong></td>
          <td>-</td>
          <td><strong class="val-red">-$${{totalBancaNeeded.toFixed(2)}}</strong></td>
          <td><span class="val-red">${{lossTot}}</span></td>
          <td>${{pctLoss}}%</td>
          <td>-</td>
          <td>-</td>
        `;
        tbody.appendChild(trLoss);
      }}

      renderPnLChart(pnlLabels, pnlPoints);
      filterTrades();
    }}

    function renderPnLChart(labels, dataPoints) {{
      const ctx = document.getElementById('chartPnL').getContext('2d');
      if (chartPnLInstance) chartPnLInstance.destroy();

      const step = Math.max(1, Math.ceil(labels.length / 250));
      const subLabels = labels.filter((_, i) => i % step === 0);
      const subData = dataPoints.filter((_, i) => i % step === 0);

      chartPnLInstance = new Chart(ctx, {{
        type: 'line',
        data: {{
          labels: subLabels,
          datasets: [{{
            label: 'Saldo Real Acumulado ($)',
            data: subData,
            borderColor: function(context) {{
              const chart = context.chart;
              const {{ctx: c, chartArea, scales}} = chart;
              if (!chartArea || !scales || !scales.y) return '#2ea043';
              const y0 = scales.y.getPixelForValue(0);
              const top = chartArea.top;
              const bottom = chartArea.bottom;
              const ratio = Math.max(0, Math.min(1, (y0 - top) / (bottom - top)));
              const grad = c.createLinearGradient(0, top, 0, bottom);
              grad.addColorStop(0, '#2ea043');
              grad.addColorStop(ratio, '#2ea043');
              grad.addColorStop(ratio, '#f85149');
              grad.addColorStop(1, '#f85149');
              return grad;
            }},
            backgroundColor: function(context) {{
              const chart = context.chart;
              const {{ctx: c, chartArea, scales}} = chart;
              if (!chartArea || !scales || !scales.y) return 'rgba(46, 160, 67, 0.15)';
              const y0 = scales.y.getPixelForValue(0);
              const top = chartArea.top;
              const bottom = chartArea.bottom;
              const ratio = Math.max(0, Math.min(1, (y0 - top) / (bottom - top)));
              const grad = c.createLinearGradient(0, top, 0, bottom);
              grad.addColorStop(0, 'rgba(46, 160, 67, 0.25)');
              grad.addColorStop(ratio, 'rgba(46, 160, 67, 0.05)');
              grad.addColorStop(ratio, 'rgba(248, 81, 73, 0.05)');
              grad.addColorStop(1, 'rgba(248, 81, 73, 0.25)');
              return grad;
            }},
            segment: {{
              borderColor: ctx => {{
                const y0 = ctx.p0.parsed.y;
                const y1 = ctx.p1.parsed.y;
                if (y0 >= 0 && y1 >= 0) return '#2ea043';
                if (y0 < 0 && y1 < 0) return '#f85149';
                return y1 >= 0 ? '#2ea043' : '#f85149';
              }}
            }},
            fill: 'origin',
            borderWidth: 2,
            tension: 0.1,
            pointRadius: 0
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{
              callbacks: {{
                label: ctx => `Saldo: ${{ctx.parsed.y >= 0 ? '+' : ''}}$${{ctx.parsed.y.toFixed(2)}}`
              }}
            }}
          }},
          scales: {{
            x: {{
              grid: {{ color: 'rgba(255,255,255,0.05)' }},
              ticks: {{ color: '#8b949e', maxTicksLimit: 12 }}
            }},
            y: {{
              grid: {{
                color: context => (context.tick && context.tick.value === 0) ? 'rgba(255, 255, 255, 0.35)' : 'rgba(255, 255, 255, 0.05)',
                lineWidth: context => (context.tick && context.tick.value === 0) ? 1.5 : 1
              }},
              ticks: {{
                color: '#8b949e',
                callback: v => `$${{v}}`
              }}
            }}
          }}
        }}
      }});
    }}

    function filterTrades() {{
      const query = document.getElementById('searchTrade').value.trim().toLowerCase();
      const resFilter = document.getElementById('filterResult').value;
      const accFilter = document.getElementById('filterAccount').value;
      const galeFilter = document.getElementById('filterGale') ? document.getElementById('filterGale').value : 'ALL';

      filteredTrades = simulatedTrades.filter(t => {{
        const matchTime = !query || t.time.toLowerCase().includes(query);
        const matchRes = resFilter === 'ALL' || t.result === resFilter;
        const matchAcc = accFilter === 'ALL' || t.account === accFilter;
        const matchGale = galeFilter === 'ALL' || (t.account === 'REAL' && String(t.galeLevel) === galeFilter);
        return matchTime && matchRes && matchAcc && matchGale;
      }});

      currentPage = 1;
      renderTradesTable();
    }}

    function renderTradesTable() {{
      const tbody = document.getElementById('tradesTableBody');
      tbody.innerHTML = '';

      const maxGales = parseInt(document.getElementById('ctrlGaleLevel').value) || 0;
      const total = filteredTrades.length;
      const start = (currentPage - 1) * pageSize;
      const end = Math.min(start + pageSize, total);
      const pageItems = filteredTrades.slice(start, end);

      pageItems.forEach((t, i) => {{
        const tr = document.createElement('tr');
        const tagClass = t.result === 'WIN' ? 'tag-win' : 'tag-loss';
        const contractBadge = t.contract === 'RISE'
          ? '<span class="tag-rise">▲ RISE</span>'
          : '<span class="tag-fall">▼ FALL</span>';

        const prevDirBadge = t.prev_dir ? t.prev_dir : '-';

        const accBadge = t.account === 'REAL' 
          ? '<span class="acc-real">⭐ MASTER (REAL)</span>' 
          : '<span class="acc-demo">🛡️ SLAVE (DEMO)</span>';

        let pnlText = '<span style="color:#8b949e;">$0.00 (Escudo)</span>';
        if (t.account === 'REAL') {{
          if (t.win === 1) {{
            const netBadge = (t.cycleNet !== undefined && t.galeLevel > 0)
              ? ` <span style="font-size:11px;color:#8b949e;">(Líq: +$${{t.cycleNet.toFixed(2)}})</span>`
              : '';
            pnlText = `<strong class="val-green">+$${{t.pnlDelta.toFixed(2)}}</strong>${{netBadge}}`;
          }} else {{
            pnlText = `<strong class="val-red">-$${{Math.abs(t.pnlDelta).toFixed(2)}}</strong>`;
          }}
        }}

        let galeBadgeText = '-';
        if (t.account === 'REAL') {{
          if (maxGales === 0) {{
            galeBadgeText = 'Mão Fixa';
          }} else if (t.galeLevel === 0) {{
            galeBadgeText = '<span style="color:var(--blue-light);font-weight:600;">G0</span>';
          }} else {{
            galeBadgeText = `<span style="color:var(--val-gold);font-weight:700;">G${{t.galeLevel}}</span>`;
          }}
        }}
        const stakeText = t.account === 'REAL' ? `$${{t.stake.toFixed(2)}} (${{galeBadgeText}})` : '-';

        tr.innerHTML = `
          <td>${{start + i + 1}}</td>
          <td>${{accBadge}}</td>
          <td>${{t.time}}</td>
          <td>${{prevDirBadge}}</td>
          <td>${{contractBadge}}</td>
          <td>${{t.entry.toFixed(2)}}</td>
          <td>${{t.exit.toFixed(2)}}</td>
          <td class="${{tagClass}}">${{t.delta > 0 ? '+' : ''}}${{t.delta.toFixed(2)}}</td>
          <td><span class="${{tagClass}}">${{t.result}}</span></td>
          <td>${{stakeText}}</td>
          <td>${{pnlText}}</td>
        `;
        tbody.appendChild(tr);
      }});

      document.getElementById('paginationInfo').innerText = total > 0
        ? `Exibindo ${{start + 1}} a ${{end}} de ${{total.toLocaleString()}} ordens`
        : 'Nenhuma ordem encontrada para os filtros selecionados';

      document.getElementById('btnPrev').disabled = currentPage === 1;
      document.getElementById('btnNext').disabled = end >= total;
    }}

    function prevPage() {{
      if (currentPage > 1) {{
        currentPage--;
        renderTradesTable();
      }}
    }}

    function nextPage() {{
      if (currentPage * pageSize < filteredTrades.length) {{
        currentPage++;
        renderTradesTable();
      }}
    }}

    function exportCSV() {{
      const st = document.getElementById('ctrlStrategy').value;
      let csv = 'Timestamp,Conta,VelaAnterior,Contrato,Entrada,Saida,Delta,Resultado,Stake,PnlReal\\n';
      simulatedTrades.forEach(t => {{
        csv += `${{t.time}},${{t.account}},${{t.prev_dir}},${{t.contract}},${{t.entry}},${{t.exit}},${{t.delta}},${{t.result}},${{t.stake}},${{t.pnlDelta}}\\n`;
      }});
      const blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8;' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `backtest_${{st}}_${{RAW_DATA.symbol}}_${{RAW_DATA.date}}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }}
  </script>
</body>
</html>
"""
    out_path = os.path.join("web", "backtest_rise_15s.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Sucesso! Arquivo gerado em {out_path} ({len(html_content)} bytes)")

if __name__ == "__main__":
    generate()
