const BRIDGE = "http://127.0.0.1:8765";

const GESTURES = [
  { id: "POINT_UP", name: "Index up", key: "ArrowUp", action: "Next video", test: "up", keyLabel: "↑" },
  { id: "POINT_DOWN", name: "Index down", key: "ArrowDown", action: "Previous video", test: "down", keyLabel: "↓" },
  { id: "THUMBS_UP", name: "Thumbs up", key: "KeyL", action: "Like", test: "l", keyLabel: "L" },
  { id: "OPEN_PALM", name: "Open palm", key: "Space", action: "Play / pause", test: "space", keyLabel: "Space" },
];

const SAMPLE_METRICS = [
  ["91%", "Accuracy"],
  ["148 ms", "Inference"],
  ["210 ms", "Response"],
  ["186 KB", "Free RAM"],
  ["1.2 MB", "Flash"],
  ["0.42 W", "Power"],
];

const state = {
  mode: "demo",
  gesture: "NO_GESTURE",
  confidence: 0,
  decision: "neutral",
  activity: [],
  live: null,
  bridgeUp: false,
};

const settings = loadSettings();

function loadSettings() {
  try {
    return Object.assign(
      { threshold: 0.7, floor: 0.4, cooldown: 700, enabled: { POINT_UP: true, POINT_DOWN: true, THUMBS_UP: true, OPEN_PALM: true }, vflip: false, hmirror: false, swap: false, pause: false },
      JSON.parse(localStorage.getItem("touchless-settings-v1") || "{}")
    );
  } catch {
    return { threshold: 0.7, floor: 0.4, cooldown: 700, enabled: {}, vflip: false, hmirror: false, swap: false, pause: false };
  }
}

function saveSettings() {
  localStorage.setItem("touchless-settings-v1", JSON.stringify(settings));
}

function gestureMeta(id) {
  return GESTURES.find((item) => item.id === id) || null;
}

function diagram(id) {
  const stroke = "#e2f56a";
  const common = `fill="none" stroke="${stroke}" stroke-width="3" stroke-linecap="round"`;
  if (id === "POINT_UP") return `<svg viewBox="0 0 120 120"><circle cx="60" cy="86" r="16" ${common}/><path d="M60 70 V22" ${common}/></svg>`;
  if (id === "POINT_DOWN") return `<svg viewBox="0 0 120 120"><circle cx="60" cy="34" r="16" ${common}/><path d="M60 50 V98" ${common}/></svg>`;
  if (id === "THUMBS_UP") return `<svg viewBox="0 0 120 120"><path d="M48 78 V46 h18 v32" ${common}/><path d="M48 58 H34 v20 h14" ${common}/></svg>`;
  if (id === "OPEN_PALM") return `<svg viewBox="0 0 120 120"><path d="M30 78 V46 M46 78 V34 M62 78 V30 M78 78 V38 M94 78 V50" ${common}/><path d="M28 78 H96" ${common}/></svg>`;
  return `<svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="28" ${common} stroke-dasharray="4 8"/></svg>`;
}

function setDot(card, kind) {
  const dot = card.querySelector(".dot");
  dot.className = "dot " + (kind || "");
}

function renderBanner() {
  const banner = document.getElementById("banner");
  banner.className = "banner";
  if (state.mode === "demo") {
    banner.textContent = "Demo mode. The connection, picture, gestures, and performance numbers on this page are sample data for the interface. They are not coming from the ESP32.";
    return;
  }
  if (!state.bridgeUp) {
    banner.classList.add("live-wait");
    banner.textContent = "Live mode. The laptop bridge is not running, so this page is not receiving the board. Start tools/serial_bridge.py, then refresh. Recognition still happens on the ESP32, not here.";
    return;
  }
  if (!state.live || !state.live.serial_open) {
    banner.classList.add("live-wait");
    banner.textContent = "The bridge is up, but the serial port is not open. Plug in the Freenove board and check the COM port. Nothing below is a live camera result until the port opens.";
    return;
  }
  banner.classList.add("live-ok");
  banner.textContent = "Live link. Thumbnails and labels are copied from the ESP32 for display. Gesture recognition is running on the board, not on this laptop.";
}

function renderStatus() {
  const live = state.mode === "live" && state.live && state.live.serial_open;
  const status = live ? state.live.status || {} : null;
  const waiting = state.mode === "live";
  const cards = [
    ["cardBoard", live ? "on" : waiting ? "off" : "wait", live ? `Serial ${state.live.port}` : waiting ? "No serial port" : "Sample · not connected"],
    ["cardBle", live && status.ble === "connected" ? "on" : "wait", live ? `HID ${status.ble || "unknown"}` : waiting ? "Waiting for the board" : "Sample · advertising"],
    ["cardCamera", live ? (status.camera ? "on" : "off") : "wait", live ? (status.camera ? `${status.sensor || "sensor"} ${status.frame_w || "?"}×${status.frame_h || "?"}` : "Camera failed") : waiting ? "Waiting for the board" : "Sample · diagram only"],
    ["cardModel", live ? (status.model_trained ? "on" : "wait") : "wait", live ? (status.model_trained ? status.model_domain : "Not trained — keys stay off") : waiting ? "Waiting for the board" : "Sample · recognizer idle"],
  ];
  cards.forEach(([id, kind, text]) => {
    const card = document.getElementById(id);
    setDot(card, kind);
    card.querySelector(".detail").textContent = text;
  });
}

function renderFinder() {
  const liveFrame = state.mode === "live" && state.live && state.live.frame && state.live.serial_open;
  const canvas = document.getElementById("preview");
  const diagramBox = document.getElementById("diagram");
  const note = document.getElementById("finderNote");
  const pill = document.getElementById("gesturePill");
  if (liveFrame) {
    canvas.hidden = false;
    diagramBox.hidden = true;
    drawGray(canvas, state.live.frame);
    note.textContent = "64×64 thumbnail from the ESP32. The model uses this scale on the board. This view is only a monitor.";
  } else {
    canvas.hidden = true;
    diagramBox.hidden = false;
    diagramBox.innerHTML = diagram(state.gesture);
    note.textContent = state.mode === "demo" ? "Diagram, not a camera frame." : "Waiting for a thumbnail from the board.";
  }
  const meta = gestureMeta(state.gesture);
  pill.textContent = meta ? meta.name : "No gesture";
  document.querySelectorAll(".gesture").forEach((button) => {
    button.classList.toggle("is-hot", button.dataset.id === state.gesture);
  });
}

function drawGray(canvas, frame) {
  const bytes = Uint8Array.from(atob(frame.data), (char) => char.charCodeAt(0));
  const width = frame.w;
  const height = frame.h;
  if (bytes.length !== width * height) return;
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  const image = context.createImageData(width, height);
  for (let i = 0; i < bytes.length; i += 1) {
    const value = bytes[i];
    image.data[i * 4] = value;
    image.data[i * 4 + 1] = value;
    image.data[i * 4 + 2] = value;
    image.data[i * 4 + 3] = 255;
  }
  context.putImageData(image, 0, 0);
}

function renderDetection() {
  const chip = document.getElementById("detectChip");
  const name = document.getElementById("gestureName");
  const sub = document.getElementById("gestureSub");
  const meter = document.getElementById("meter");
  const confidence = document.getElementById("confidence");
  const reason = document.getElementById("reason");
  const meta = gestureMeta(state.gesture);
  const sample = state.mode === "demo";
  chip.textContent = sample ? "Sample" : "Device";
  chip.className = sample ? "chip" : "chip quiet";
  name.textContent = meta ? meta.name : "No gesture";
  sub.textContent = meta ? `${meta.keyLabel} · ${meta.action}` : "No key is sent.";
  const value = sample && state.gesture !== "NO_GESTURE" ? state.confidence : state.mode === "live" ? state.confidence : 0;
  meter.style.width = `${Math.round(value * 100)}%`;
  confidence.textContent = value ? `Confidence ${Math.round(value * 100)}%` : "Confidence —";
  reason.textContent = reasonText(state.decision, sample);
}

function reasonText(decision, sample) {
  if (sample && state.gesture === "NO_GESTURE") return "Choose a pose below to preview the interface.";
  const map = {
    ok: "Threshold met. One key is sent, then the pose has to relax before it can repeat.",
    hold: "Same pose is still held. Waiting for no gesture.",
    cooldown: "A key was just sent. Cooldown is still running.",
    low_confidence: "Below the confidence threshold. No key.",
    uncertain: "Too unsure to call a pose. Treated as neutral.",
    neutral: "No gesture. The next pose can fire.",
    offline: "The board is not connected, so this is not a detection.",
    untrained: "The on-device model has not been trained, so keys stay off.",
    no_ble: "The laptop has not connected to the Bluetooth keyboard.",
    disabled: "This gesture is switched off.",
    suspended: "Keys are paused.",
    manual: "Manual key test. The camera was not involved.",
  };
  return map[decision] || decision || "";
}

function renderActivity() {
  const list = document.getElementById("activity");
  const chip = document.getElementById("activityChip");
  chip.textContent = state.mode === "demo" ? "Sample" : "Laptop clock";
  chip.className = state.mode === "demo" ? "chip" : "chip quiet";
  list.innerHTML = "";
  if (!state.activity.length) {
    const item = document.createElement("li");
    item.textContent = state.mode === "demo" ? "No sample events yet." : "No device events yet.";
    list.appendChild(item);
    return;
  }
  state.activity.slice(0, 8).forEach((entry) => {
    const item = document.createElement("li");
    const left = document.createElement("div");
    const title = document.createElement("div");
    title.textContent = `${entry.gesture}${entry.key ? " → " + entry.key : ""}`;
    const small = document.createElement("small");
    small.textContent = `${entry.decision || ""} · ${entry.when}`;
    left.append(title, small);
    const flag = document.createElement("small");
    flag.textContent = entry.source === "sample" ? "Sample" : entry.fired ? "Sent" : "Held";
    item.append(left, flag);
    list.appendChild(item);
  });
}

function renderMetrics() {
  const chip = document.getElementById("metricChip");
  const box = document.getElementById("metrics");
  box.innerHTML = "";
  const connected = state.mode === "live" && state.live && state.live.serial_open;
  const sample = state.mode === "demo";
  chip.textContent = sample ? "Sample" : connected ? "Device" : "Waiting";
  chip.className = sample ? "chip" : "chip quiet";
  const rows = sample ? SAMPLE_METRICS : connected ? liveMetrics() : [
    ["—", "Accuracy"],
    ["—", "Inference"],
    ["—", "Response"],
    ["—", "Free RAM"],
    ["—", "Flash"],
    ["Not on chip", "Power needs a USB meter"],
  ];
  rows.forEach(([value, label]) => {
    const card = document.createElement("div");
    card.className = "metric";
    const strong = document.createElement("b");
    strong.textContent = value;
    const span = document.createElement("span");
    span.textContent = label;
    card.append(strong, span);
    box.appendChild(card);
  });
}

function liveMetrics() {
  const status = (state.live && state.live.status) || {};
  const inference = (state.live && state.live.inference) || {};
  const evaluation = state.live && state.live.evaluation;
  const accuracy = evaluation && evaluation.float32 ? `${Math.round(evaluation.float32.accuracy * 100)}%` : "Not measured";
  const infer = inference.inference_us ? `${Math.round(inference.inference_us / 1000)} ms` : "—";
  const response = inference.e2e_us ? `${Math.round(inference.e2e_us / 1000)} ms` : "—";
  const heap = status.heap ? `${Math.round(status.heap / 1024)} KB` : "—";
  const flash = status.sketch ? `${(status.sketch / (1024 * 1024)).toFixed(2)} MB` : "—";
  return [
    [accuracy, evaluation ? "Held-out accuracy" : "Accuracy not measured"],
    [infer, "Last inference"],
    [response, "Last key path"],
    [heap, "Free internal RAM"],
    [flash, "Sketch size"],
    ["Not on chip", "Power needs a USB meter"],
  ];
}

function render() {
  renderBanner();
  renderStatus();
  renderFinder();
  renderDetection();
  renderActivity();
  renderMetrics();
  document.getElementById("modeDemo").classList.toggle("is-on", state.mode === "demo");
  document.getElementById("modeLive").classList.toggle("is-on", state.mode === "live");
  document.getElementById("modeDemo").setAttribute("aria-pressed", String(state.mode === "demo"));
  document.getElementById("modeLive").setAttribute("aria-pressed", String(state.mode === "live"));
}

function pushActivity(entry) {
  state.activity.unshift(entry);
  state.activity = state.activity.slice(0, 12);
}

function selectGesture(id, source) {
  state.gesture = id;
  const meta = gestureMeta(id);
  if (!meta) {
    state.confidence = 0;
    state.decision = "neutral";
  } else if (source === "sample") {
    state.confidence = 0.86;
    state.decision = settings.enabled[id] === false ? "disabled" : settings.pause ? "suspended" : "ok";
    pushActivity({
      gesture: id,
      key: state.decision === "ok" ? meta.key : "",
      decision: state.decision,
      fired: state.decision === "ok",
      source: "sample",
      when: "Sample",
    });
  }
  pulsePipeline(state.decision === "ok");
  render();
}

function pulsePipeline(fired) {
  const steps = [...document.querySelectorAll("#pipeline li")];
  steps.forEach((step) => step.classList.remove("on"));
  steps.forEach((step, index) => {
    setTimeout(() => {
      if (index === steps.length - 1 && !fired) return;
      step.classList.add("on");
    }, index * 90);
  });
}

function applyLive(payload) {
  state.live = payload;
  state.bridgeUp = true;
  const inference = payload.inference;
  if (inference) {
    state.gesture = inference.gesture || "NO_GESTURE";
    state.confidence = Number(inference.confidence || 0);
    state.decision = inference.decision || "";
  }
  state.activity = (payload.activity || []).map((entry) => ({
    gesture: entry.gesture,
    key: entry.key,
    decision: entry.decision,
    fired: entry.fired,
    source: "device",
    when: new Date(entry.t * 1000).toLocaleTimeString(),
  }));
  render();
}

async function poll() {
  if (state.mode !== "live") return;
  try {
    const response = await fetch(`${BRIDGE}/state`);
    if (!response.ok) throw new Error("bad status");
    applyLive(await response.json());
  } catch {
    state.bridgeUp = false;
    state.live = null;
    state.gesture = "NO_GESTURE";
    state.confidence = 0;
    state.decision = "offline";
    state.activity = [];
    render();
  }
}

async function sendCommand(command) {
  if (state.mode !== "live") return;
  try {
    await fetch(`${BRIDGE}/command`, {
      method: "POST",
      headers: { "Content-Type": "text/plain" },
      body: JSON.stringify(command),
    });
  } catch {
    // The bridge is not running. The banner already says so.
  }
}

function bindSettings() {
  const threshold = document.getElementById("threshold");
  const floor = document.getElementById("floor");
  const cooldown = document.getElementById("cooldown");
  threshold.value = settings.threshold;
  floor.value = settings.floor;
  cooldown.value = settings.cooldown;
  const show = () => {
    document.getElementById("thresholdLabel").textContent = Number(threshold.value).toFixed(2);
    document.getElementById("floorLabel").textContent = Number(floor.value).toFixed(2);
    document.getElementById("cooldownLabel").textContent = `${cooldown.value} ms`;
    document.getElementById("settingsNote").textContent = state.mode === "demo"
      ? "These sliders change the demo only."
      : "Releasing a slider sends it to the ESP32.";
  };
  const persist = () => {
    settings.threshold = Number(threshold.value);
    settings.floor = Number(floor.value);
    settings.cooldown = Number(cooldown.value);
    saveSettings();
    show();
  };
  [threshold, floor, cooldown].forEach((input) => input.addEventListener("input", persist));
  threshold.addEventListener("change", () => sendCommand({ cmd: "set", name: "threshold", value: Number(threshold.value) }));
  floor.addEventListener("change", () => sendCommand({ cmd: "set", name: "neutral_floor", value: Number(floor.value) }));
  cooldown.addEventListener("change", () => sendCommand({ cmd: "set", name: "cooldown_ms", value: Number(cooldown.value) }));

  const toggles = document.getElementById("toggles");
  GESTURES.forEach((gesture) => {
    const label = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = settings.enabled[gesture.id] !== false;
    box.addEventListener("change", () => {
      settings.enabled[gesture.id] = box.checked;
      saveSettings();
      sendCommand({ cmd: "gesture", name: gesture.id, enabled: box.checked ? 1 : 0 });
    });
    label.append(box, document.createTextNode(` ${gesture.name}`));
    toggles.appendChild(label);
  });

  ["vflip", "hmirror", "swap", "pause"].forEach((id) => {
    const input = document.getElementById(id === "pause" ? "pauseKeys" : id);
    const key = id === "pause" ? "pause" : id;
    input.checked = Boolean(settings[key]);
    input.addEventListener("change", () => {
      settings[key] = input.checked;
      saveSettings();
      if (id === "pause") sendCommand({ cmd: "suspend", value: input.checked ? 1 : 0 });
      else sendCommand({ cmd: "orient", v: settings.vflip ? 1 : 0, h: settings.hmirror ? 1 : 0, swap: settings.swap ? 1 : 0 });
    });
  });
  show();
}

function bindGestures() {
  const grid = document.getElementById("gestures");
  GESTURES.forEach((gesture) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "gesture";
    button.dataset.id = gesture.id;
    button.innerHTML = `<strong></strong><span></span><kbd></kbd>`;
    button.querySelector("strong").textContent = gesture.name;
    button.querySelector("span").textContent = gesture.action;
    button.querySelector("kbd").textContent = gesture.keyLabel;
    button.addEventListener("click", () => {
      if (state.mode === "demo") selectGesture(gesture.id, "sample");
    });
    grid.appendChild(button);
  });
  const tests = document.getElementById("keyTests");
  GESTURES.forEach((gesture) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `Send ${gesture.keyLabel}`;
    button.addEventListener("click", () => sendCommand({ cmd: "keytest", key: gesture.test }));
    tests.appendChild(button);
  });
}

function setMode(mode) {
  state.mode = mode;
  state.gesture = "NO_GESTURE";
  state.confidence = 0;
  state.decision = mode === "live" ? "offline" : "neutral";
  state.activity = [];
  if (mode === "demo") state.live = null;
  document.getElementById("settingsNote").textContent = mode === "demo"
    ? "These sliders change the demo only."
    : "Releasing a slider sends it to the ESP32.";
  document.querySelectorAll("#keyTests button, #forget").forEach((button) => {
    button.disabled = mode !== "live";
  });
  render();
}

document.getElementById("modeDemo").addEventListener("click", () => setMode("demo"));
document.getElementById("modeLive").addEventListener("click", () => setMode("live"));
document.getElementById("clearPose").addEventListener("click", () => {
  if (state.mode === "demo") selectGesture("NO_GESTURE", "sample");
});
document.getElementById("forget").addEventListener("click", () => sendCommand({ cmd: "forget" }));
document.addEventListener("keydown", (event) => {
  if (state.mode !== "demo") return;
  const index = Number(event.key) - 1;
  if (index >= 0 && index < GESTURES.length) selectGesture(GESTURES[index].id, "sample");
  if (event.key === "0") selectGesture("NO_GESTURE", "sample");
});

bindGestures();
bindSettings();
setMode("demo");
setInterval(poll, 500);
