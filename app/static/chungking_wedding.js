const transcriptEl = document.getElementById("transcript");
const usageEl = document.getElementById("usage");
const healthEl = document.getElementById("health");
const commandForm = document.getElementById("command-form");
const commandInput = document.getElementById("command");
const resetBtn = document.getElementById("reset");
const activeLabel = document.getElementById("active-label");
const scenarioButtons = document.querySelectorAll("[data-activate]");

const scenarios = {
  chungking: {
    name: "Chungking",
    tone: "neon, schnelle Schnitte, Agentenfilm",
    profile: `Du bist ein Regie- und Szenen-Coach für eine neon-getränkte Hongkong-Montage à la Chungking Express. Arbeite mit knappen Shots, Close-Ups, Street-Geräuschen und schnellen Perspektivwechseln. Biete klare Regieanweisungen, spreche in dynamischem Deutsch mit kurzen, kraftvollen Sätzen.`,
  },
  wedding: {
    name: "Wedding",
    tone: "Berlin-Nord, Doku-Drama, sozial",
    profile: `Du bist ein Regie- und Szenen-Coach für ein authentisches Doku-Drama im Berliner Stadtteil Wedding. Arbeite mit beobachtenden Kameraeinstellungen, Dialogfetzen vom Kiez, Späti-Licht und Nahaufnahmen. Sprich direkt, bodenständig und konkret – Fokus auf Menschen, Milieu und Handlung.`,
  },
};

let activeScenario = "chungking";
let history = [];

function systemPromptForScenario() {
  const scenario = scenarios[activeScenario];
  return [
    `${scenario.profile}`,
    `Aktive Szene: ${scenario.name}`,
    `Tonfall: ${scenario.tone}`,
    "Liefer: (1) eine knappe Zusammenfassung dessen, was du tust, (2) konkrete Regie-/Ton-/Storyboard-Cues in 2-4 Bullet-Points.",
  ].join("\n");
}

function renderHistory(conversation) {
  transcriptEl.innerHTML = "";
  conversation.forEach((turn) => {
    const wrapper = document.createElement("article");
    wrapper.classList.add("message", turn.role);

    const role = document.createElement("span");
    role.classList.add("role");
    role.textContent = turn.role === "assistant" ? "Agent" : "Du";

    const text = document.createElement("p");
    text.textContent = turn.content;

    wrapper.appendChild(role);
    wrapper.appendChild(text);
    transcriptEl.appendChild(wrapper);
  });
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

function setUsage(usage) {
  if (!usage) {
    usageEl.textContent = "";
    return;
  }
  const parts = [
    usage.prompt_tokens != null ? `Prompt: ${usage.prompt_tokens}` : null,
    usage.completion_tokens != null ? `Antwort: ${usage.completion_tokens}` : null,
    usage.total_tokens != null ? `Gesamt: ${usage.total_tokens}` : null,
  ].filter(Boolean);
  usageEl.textContent = parts.join(" · ");
}

async function fetchHealth() {
  try {
    const response = await fetch("/api/health");
    const data = await response.json();
    if (data.status === "ok") {
      healthEl.textContent = `Backend ok · Modell: ${data.model}`;
    } else {
      healthEl.textContent = "Backend meldet ein Problem";
    }
  } catch (error) {
    healthEl.textContent = `Backend nicht erreichbar: ${error.message}`;
  }
}

async function sendCommand(message) {
  const system_prompt = systemPromptForScenario();
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, system_prompt }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || "Unbekannter Fehler");
  }
  const data = await response.json();
  history = data.history;
  renderHistory(history);
  setUsage(data.usage);
}

commandForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = commandInput.value.trim();
  if (!text) return;

  renderHistory([...history, { role: "user", content: text }]);
  setUsage(null);
  healthEl.textContent = "LLM denkt …";
  commandInput.value = "";

  try {
    await sendCommand(text);
    healthEl.textContent = "Antwort erhalten.";
  } catch (error) {
    healthEl.textContent = `Fehler: ${error.message}`;
  } finally {
    commandInput.focus();
  }
});

resetBtn.addEventListener("click", () => {
  history = [];
  renderHistory(history);
  setUsage(null);
  healthEl.textContent = "Verlauf zurückgesetzt.";
  commandInput.focus();
});

scenarioButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const target = button.getAttribute("data-activate");
    if (!target || !scenarios[target]) return;
    activeScenario = target;
    activeLabel.textContent = scenarios[target].name;
    history = [];
    renderHistory(history);
    setUsage(null);
    healthEl.textContent = `${scenarios[target].name} aktiviert – System-Prompt gesetzt.`;
    commandInput.placeholder = target === "chungking"
      ? 'z. B. "Baue eine Voice-Over-Szene im Regen"'
      : 'z. B. "Beschreibe eine Impro-Szene vorm Späti"';
    commandInput.focus();
  });
});

fetchHealth();
renderHistory(history);
commandInput.focus();
