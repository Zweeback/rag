const chatEl = document.getElementById("chat");
const formEl = document.getElementById("chat-form");
const messageEl = document.getElementById("message");
const systemPromptEl = document.getElementById("system-prompt");
const statusEl = document.getElementById("status");
const usageEl = document.getElementById("usage");
const clearEl = document.getElementById("clear");
const sendButton = document.getElementById("send");

let history = [];

function roleLabel(role) {
  if (role === "assistant") return "DeepSeek";
  if (role === "user") return "Du";
  return "System";
}

function setStatus(text, state = "info") {
  statusEl.textContent = text;
  statusEl.dataset.state = state;
}

function setUsage(usage) {
  if (!usage) {
    usageEl.textContent = "";
    return;
  }
  const tokens = [
    usage.prompt_tokens != null ? `Prompt: ${usage.prompt_tokens}` : null,
    usage.completion_tokens != null ? `Antwort: ${usage.completion_tokens}` : null,
    usage.total_tokens != null ? `Gesamt: ${usage.total_tokens}` : null,
  ].filter(Boolean);
  usageEl.textContent = tokens.join(" · ");
}

function renderHistory(conversation) {
  chatEl.innerHTML = "";
  conversation
    .filter((turn) => turn.role !== "system")
    .forEach((turn) => {
      const wrapper = document.createElement("article");
      wrapper.classList.add("message", turn.role);

      const roleSpan = document.createElement("span");
      roleSpan.classList.add("role");
      roleSpan.textContent = roleLabel(turn.role);

      const paragraph = document.createElement("p");
      paragraph.textContent = turn.content;

      wrapper.appendChild(roleSpan);
      wrapper.appendChild(paragraph);
      chatEl.appendChild(wrapper);
    });
  chatEl.scrollTop = chatEl.scrollHeight;
}

async function fetchHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    const state = data.status === "ok" ? "success" : "error";
    setStatus(data.status === "ok" ? "Bereit." : "Backend meldet ein Problem.", state);
    if (data.system_prompt === "preset" && !systemPromptEl.value) {
      systemPromptEl.placeholder = "Server-Preset aktiv – optional überschreiben.";
    }
  } catch (error) {
    setStatus(`Backend nicht erreichbar: ${error.message}`, "error");
  }
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = messageEl.value.trim();
  if (!text) return;

  const systemPrompt = systemPromptEl.value.trim();
  renderHistory([...history, { role: "user", content: text }]);
  messageEl.value = "";
  setUsage(null);
  setStatus("DeepSeek denkt …", "info");
  sendButton.disabled = true;
  clearEl.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        history,
        system_prompt: systemPrompt || undefined,
      }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(err.detail || "Unbekannter Fehler");
    }

    const data = await response.json();
    history = data.history;
    renderHistory(history);
    setUsage(data.usage);
    setStatus("Bereit.", "success");
  } catch (error) {
    setStatus(`Fehler: ${error.message}`, "error");
  } finally {
    sendButton.disabled = false;
    clearEl.disabled = false;
    messageEl.focus();
  }
});

clearEl.addEventListener("click", () => {
  history = [];
  renderHistory(history);
  setUsage(null);
  setStatus("Verlauf zurückgesetzt.", "success");
  messageEl.value = "";
  messageEl.focus();
});

fetchHealth().finally(() => {
  if (!statusEl.textContent) {
    setStatus("Bereit.");
  }
});

messageEl.focus();
