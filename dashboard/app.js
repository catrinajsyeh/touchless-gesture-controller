const BRIDGE = "http://127.0.0.1:8765";

const POSES = [
  { id: "POINT_UP", name: "Index up", how: "Point one finger up" },
  { id: "POINT_DOWN", name: "Index down", how: "Point one finger down" },
  { id: "THUMBS_UP", name: "Thumbs up", how: "Thumb up, other fingers closed" },
  { id: "OPEN_PALM", name: "Open palm", how: "Open hand, fingers spread" },
  { id: "NO_GESTURE", name: "No gesture", how: "No hand in the picture" },
];

const NAMES = Object.fromEntries(POSES.map((pose) => [pose.id, pose.name]));

const state = {
  tab: "train",
  pose: "POINT_UP",
  live: null,
  busy: false,
  photoStamp: "",
};

const poses = document.getElementById("poses");
const saveButton = document.getElementById("save");
const trainButton = document.getElementById("train");
const trainMsg = document.getElementById("trainMsg");
const photo = document.getElementById("photo");
const empty = document.getElementById("empty");
const linkStatus = document.getElementById("linkStatus");
const guess = document.getElementById("guess");
const confidence = document.getElementById("confidence");
const scores = document.getElementById("scores");

function poseButtons() {
  poses.innerHTML = "";
  const counts = (state.live && state.live.dataset) || {};
  POSES.forEach((pose) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pose" + (state.pose === pose.id ? " is-on" : "");
    const count = counts[pose.id] || 0;
    button.innerHTML = `<strong>${pose.name}</strong><span>${pose.how}</span><em>${count} / 20 photos</em>`;
    button.addEventListener("click", () => {
      state.pose = pose.id;
      poseButtons();
    });
    poses.appendChild(button);
  });
}

function showPhoto(frame) {
  if (!frame || frame.fmt !== "jpeg" || !frame.data) {
    photo.style.display = "none";
    empty.hidden = false;
    return;
  }
  const stamp = `${frame.w}x${frame.h}:${frame.data.length}:${frame.data.slice(-24)}`;
  if (stamp !== state.photoStamp) {
    state.photoStamp = stamp;
    photo.src = `data:image/jpeg;base64,${frame.data}`;
  }
  photo.style.display = "block";
  empty.hidden = true;
}

function renderTrain() {
  const train = (state.live && state.live.train) || {};
  const running = train.status === "running" || state.busy;
  saveButton.disabled = running || !(state.live && state.live.serial_open);
  trainButton.disabled = running || !(state.live && state.live.serial_open);
  saveButton.textContent = state.busy ? `Saving ${NAMES[state.pose]}…` : `Save 10 photos of ${NAMES[state.pose]}`;
  trainButton.textContent = train.status === "running" ? "Training…" : "Train model";
  if (train.message) {
    const accuracy = typeof train.accuracy === "number" ? ` Held-out accuracy ${Math.round(train.accuracy * 100)}%.` : "";
    trainMsg.textContent = train.message + accuracy;
  }
}

async function post(path, body) {
  const response = await fetch(`${BRIDGE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "text/plain" },
    body: JSON.stringify(body || {}),
  });
  const payload = await response.json();
  if (!response.ok && !payload.detail && !payload.message) {
    throw new Error("Request failed");
  }
  return payload;
}

async function poll() {
  try {
    const response = await fetch(`${BRIDGE}/state`);
    if (!response.ok) throw new Error("offline");
    state.live = await response.json();
    const serial = state.live.serial_open;
    linkStatus.textContent = serial
      ? `Board connected on ${state.live.port}.`
      : "The board is not connected. Plug in the UART port and leave this page open.";
    showPhoto(state.live.frame);
    renderHand();
    poseButtons();
    renderTrain();
  } catch {
    state.live = null;
    linkStatus.textContent = "The camera bridge is not running.";
    showPhoto(null);
    poseButtons();
    renderTrain();
  }
}

function renderHand() {
  const inference = state.live && state.live.inference;
  const hand = state.live && state.live.hand;
  const seen = document.getElementById("seen");
  let text = "Looking for a hand…";
  let detail = "The skeleton is the hand. The word is the model on the board.";
  if (hand && hand.hand === false) {
    text = "No hand in frame";
    detail = "Your face is ignored until a hand is found.";
  } else if (inference && inference.gesture) {
    text = NAMES[inference.gesture] || inference.gesture;
    detail = `Model confidence ${Math.round((inference.confidence || 0) * 100)}%`;
  }
  if (seen) seen.textContent = text;
  if (state.tab !== "check") return;
  guess.textContent = text;
  confidence.textContent = detail;
  const values = inference && inference.scores;
  scores.innerHTML = Array.isArray(values)
    ? POSES.map((pose, index) => `<li><span>${pose.name}</span><span>${Math.round((values[index] || 0) * 100)}%</span></li>`).join("")
    : "";
}

function armKeys() {
  post("/keys", { value: state.tab === "check" }).catch(() => {});
}

document.getElementById("tabTrain").addEventListener("click", () => setTab("train"));
document.getElementById("tabCheck").addEventListener("click", () => setTab("check"));

function setTab(tab) {
  state.tab = tab;
  document.getElementById("tabTrain").classList.toggle("is-on", tab === "train");
  document.getElementById("tabCheck").classList.toggle("is-on", tab === "check");
  document.getElementById("trainPane").hidden = tab !== "train";
  document.getElementById("checkPane").hidden = tab !== "check";
  document.getElementById("title").textContent = tab === "train" ? "Train the gestures" : "Check the model";
  renderHand();
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function countdown() {
  const node = document.getElementById("countdown");
  for (const step of [3, 2, 1]) {
    node.hidden = false;
    node.textContent = String(step);
    trainMsg.textContent = `${NAMES[state.pose]} in ${step}. Get the pose in frame.`;
    await wait(1000);
  }
  node.textContent = "Hold";
  trainMsg.textContent = `Hold ${NAMES[state.pose]} still.`;
  await wait(600);
  node.hidden = true;
}

saveButton.addEventListener("click", async () => {
  state.busy = true;
  renderTrain();
  try {
    await countdown();
    const result = await post("/capture", { label: state.pose, count: 10 });
    trainMsg.textContent = result.ok ? `Saved ${result.saved.length} photos.` : result.detail;
    if (result.dataset && state.live) state.live.dataset = result.dataset;
  } catch (error) {
    document.getElementById("countdown").hidden = true;
    trainMsg.textContent = error.message;
  }
  state.busy = false;
  poseButtons();
  renderTrain();
});

trainButton.addEventListener("click", async () => {
  trainMsg.textContent = "Starting training…";
  try {
    const result = await post("/train");
    trainMsg.textContent = result.message || result.detail || "Training started.";
  } catch (error) {
    trainMsg.textContent = error.message;
  }
});

poseButtons();
setInterval(poll, 300);
poll();
