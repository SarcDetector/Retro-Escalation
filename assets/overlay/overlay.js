(function () {
  "use strict";

  const SUPPORTED_VERSION = 1;
  const MAX_HEADERS = 12;
  const MAX_ROWS = 64;
  const MAX_TEXT_LENGTH = 160;
  const MIN_RECONNECT_MS = 500;
  const MAX_RECONNECT_MS = 10000;
  const RECONNECT_JITTER = 0.2;
  const HEX_COLOR = /^#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$/i;
  const THEME_VARIABLES = new Set([
    "--re-surface-void",
    "--re-surface-base",
    "--re-surface-raised",
    "--re-surface-overlay",
    "--re-surface-deep",
    "--re-border-hairline",
    "--re-border-control",
    "--re-text-primary",
    "--re-text-secondary",
    "--re-text-muted",
    "--re-text-eyebrow",
    "--re-text-inverse",
    "--re-accent",
    "--re-accent-dim",
    "--re-accent-edge",
    "--re-accent-tint",
    "--re-accent-track",
    "--re-success",
    "--re-warning",
    "--re-danger"
  ]);

  const overlay = document.getElementById("overlay");
  const duration = document.getElementById("duration");
  const status = document.getElementById("status");
  const headers = document.getElementById("headers");
  const rows = document.getElementById("rows");
  const empty = document.getElementById("empty");
  const connection = document.getElementById("connection");

  let socket = null;
  let reconnectTimer = null;
  let reconnectAttempt = 0;
  let incompatible = false;
  let presentationVisible = true;

  function safeText(value) {
    if (typeof value !== "string") {
      return "";
    }
    return value.slice(0, MAX_TEXT_LENGTH);
  }

  function safeColor(value, fallback) {
    return typeof value === "string" && HEX_COLOR.test(value) ? value : fallback;
  }

  function setConnection(text, connected) {
    connection.textContent = text;
    overlay.dataset.connected = connected ? "true" : "false";
  }

  function setStatus(text, state) {
    status.textContent = text;
    status.dataset.state = state;
  }

  function clearTable() {
    headers.replaceChildren();
    rows.replaceChildren();
  }

  function showEmpty(message) {
    empty.textContent = message;
    empty.dataset.visible = "true";
  }

  function hideEmpty() {
    empty.dataset.visible = "false";
  }

  function setPresentationVisible(visible) {
    presentationVisible = visible;
    if (visible) {
      overlay.hidden = false;
      overlay.setAttribute("aria-hidden", "false");
      return;
    }

    clearTable();
    hideEmpty();
    overlay.hidden = true;
    overlay.setAttribute("aria-hidden", "true");
  }

  function applyTheme(theme) {
    if (!theme || typeof theme !== "object" || Array.isArray(theme)) {
      return;
    }

    for (const variable of THEME_VARIABLES) {
      const value = theme[variable];
      if (typeof value === "string" && HEX_COLOR.test(value)) {
        document.documentElement.style.setProperty(variable, value);
      }
    }
  }

  function normalizedHeaders(payloadHeaders) {
    if (!Array.isArray(payloadHeaders)) {
      return null;
    }
    return payloadHeaders
      .slice(0, MAX_HEADERS)
      .map(safeText);
  }

  function normalizedRows(payloadRows, columnCount) {
    if (!Array.isArray(payloadRows)) {
      return null;
    }

    const result = [];
    for (const row of payloadRows.slice(0, MAX_ROWS)) {
      if (!row || typeof row !== "object" || Array.isArray(row)) {
        continue;
      }
      if (typeof row.label !== "string" || !Array.isArray(row.values)) {
        continue;
      }

      const values = [];
      for (let index = 0; index < columnCount; index += 1) {
        const value = row.values[index];
        values.push(typeof value === "number" && Number.isFinite(value) ? value : null);
      }
      result.push({
        label: safeText(row.label),
        values: values,
        color: safeColor(row.color, "var(--re-accent)")
      });
    }
    return result;
  }

  function formatMetric(value, header) {
    if (value === null) {
      return "—";
    }

    const metric = header.toLocaleLowerCase("en-US");
    if (metric.includes("time")) {
      return value.toLocaleString("en-US", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1
      }) + "s";
    }
    if (metric.includes("debuff") || metric.includes("attacks-in") || metric.includes("%")) {
      return value.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }) + "%";
    }
    if (metric.includes("kills") || metric.includes("deaths")) {
      return Math.round(value).toLocaleString("en-US");
    }
    return value.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function renderTable(metricHeaders, playerRows) {
    clearTable();

    const operatorHeader = document.createElement("th");
    operatorHeader.scope = "col";
    operatorHeader.textContent = "OPERATOR";
    headers.appendChild(operatorHeader);

    for (const label of metricHeaders) {
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = label;
      headers.appendChild(cell);
    }

    for (const player of playerRows) {
      const tableRow = document.createElement("tr");
      tableRow.style.setProperty("--row-color", player.color);

      const labelCell = document.createElement("td");
      labelCell.textContent = player.label;
      tableRow.appendChild(labelCell);

      player.values.forEach(function (value, index) {
        const valueCell = document.createElement("td");
        valueCell.textContent = formatMetric(value, metricHeaders[index]);
        tableRow.appendChild(valueCell);
      });
      rows.appendChild(tableRow);
    }

    if (playerRows.length === 0) {
      showEmpty("WAITING FOR LIVE COMBAT TELEMETRY");
    } else {
      hideEmpty();
    }
  }

  function renderSnapshot(payload) {
    if (payload.type !== "snapshot" || Number(payload.version) !== SUPPORTED_VERSION) {
      incompatible = true;
      setPresentationVisible(true);
      clearTable();
      showEmpty("INCOMPATIBLE OVERLAY FEED");
      setStatus("VERSION ERROR", "error");
      setConnection("SUPPORTED SCHEMA: V" + SUPPORTED_VERSION, false);
      if (socket) {
        socket.close(1002, "Unsupported overlay schema");
      }
      return;
    }

    if (typeof payload.visible !== "boolean" || typeof payload.parserActive !== "boolean") {
      throw new TypeError("Invalid overlay state");
    }

    applyTheme(payload.theme);
    setPresentationVisible(payload.visible);
    if (!payload.visible) {
      reconnectAttempt = 0;
      return;
    }

    const metricHeaders = normalizedHeaders(payload.headers);
    if (metricHeaders === null) {
      throw new TypeError("Invalid overlay headers");
    }
    const playerRows = normalizedRows(payload.rows, metricHeaders.length);
    if (playerRows === null) {
      throw new TypeError("Invalid overlay rows");
    }

    const combatDuration = typeof payload.duration === "number" && Number.isFinite(payload.duration)
      ? Math.max(0, payload.duration)
      : 0;
    duration.textContent = combatDuration.toLocaleString("en-US", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1
    }) + "S";
    renderTable(metricHeaders, playerRows);

    if (!payload.parserActive) {
      setStatus("PARSER STOPPED", "waiting");
    } else if (playerRows.length === 0) {
      setStatus("LISTENING", "waiting");
    } else {
      const noun = playerRows.length === 1 ? "OPERATOR" : "OPERATORS";
      setStatus(playerRows.length + " " + noun, "live");
    }

    setConnection("FEED CONNECTED // SCHEMA V" + SUPPORTED_VERSION, true);
    reconnectAttempt = 0;
  }

  function showFrameError() {
    if (!presentationVisible) {
      return;
    }
    clearTable();
    showEmpty("INVALID TELEMETRY FRAME");
    setStatus("FEED ERROR", "error");
    setConnection("WAITING FOR VALID DATA", false);
  }

  function reconnectDelay() {
    const base = Math.min(
      MAX_RECONNECT_MS,
      MIN_RECONNECT_MS * Math.pow(2, Math.min(reconnectAttempt, 8))
    );
    const jitter = base * RECONNECT_JITTER * ((Math.random() * 2) - 1);
    return Math.max(MIN_RECONNECT_MS, Math.min(MAX_RECONNECT_MS, Math.round(base + jitter)));
  }

  function scheduleReconnect() {
    if (incompatible || reconnectTimer !== null) {
      return;
    }
    const delay = reconnectDelay();
    reconnectAttempt += 1;
    setConnection("RECONNECTING IN " + (delay / 1000).toFixed(1) + "S", false);
    if (presentationVisible) {
      setStatus("RECONNECTING", "waiting");
    }
    reconnectTimer = window.setTimeout(function () {
      reconnectTimer = null;
      connect();
    }, delay);
  }

  function configuredEndpoint() {
    const config = window.RE_OSCR_OVERLAY_CONFIG;
    if (!config || typeof config !== "object" || Array.isArray(config)) {
      return null;
    }
    if (typeof config.endpoint !== "string" || config.endpoint.length > 2048) {
      return null;
    }
    try {
      const endpoint = new URL(config.endpoint);
      if (endpoint.protocol !== "ws:" && endpoint.protocol !== "wss:") {
        return null;
      }
      return endpoint.href;
    } catch (error) {
      return null;
    }
  }

  function connect() {
    const endpoint = configuredEndpoint();
    if (endpoint === null) {
      clearTable();
      showEmpty("OVERLAY CONFIGURATION REQUIRED");
      setStatus("NOT CONFIGURED", "error");
      setConnection("OPEN THIS FILE FROM THE RE-OSCR LIVE PAGE", false);
      return;
    }

    if (socket !== null) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      socket.close();
    }

    setConnection("CONNECTING TO RE-OSCR", false);
    if (presentationVisible) {
      setStatus("CONNECTING", "connecting");
    }

    try {
      socket = new WebSocket(endpoint);
    } catch (error) {
      socket = null;
      if (presentationVisible) {
        setStatus("FEED ERROR", "error");
      }
      scheduleReconnect();
      return;
    }
    socket.onopen = function () {
      setConnection("CONNECTED // WAITING FOR SNAPSHOT", true);
      if (presentationVisible) {
        setStatus("WAITING", "waiting");
      }
    };
    socket.onmessage = function (event) {
      if (typeof event.data !== "string") {
        showFrameError();
        return;
      }
      try {
        const payload = JSON.parse(event.data);
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
          throw new TypeError("Invalid overlay payload");
        }
        renderSnapshot(payload);
      } catch (error) {
        showFrameError();
      }
    };
    socket.onerror = function () {
      if (presentationVisible) {
        setStatus("FEED ERROR", "error");
      }
    };
    socket.onclose = function () {
      socket = null;
      if (!incompatible && presentationVisible) {
        clearTable();
        showEmpty("LIVE FEED DISCONNECTED");
      }
      scheduleReconnect();
    };
  }

  connect();
}());
