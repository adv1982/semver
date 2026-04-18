"use strict";

const socket = io();
const messagesEl = document.getElementById("messages");
const inputEl    = document.getElementById("userInput");
const sendBtn    = document.getElementById("sendBtn");
const micBtn     = document.getElementById("micBtn");
const listenInd  = document.getElementById("listeningIndicator");
const voiceOut   = document.getElementById("voiceOutputToggle");
const voiceIn    = document.getElementById("voiceInputToggle");
const voiceRate  = document.getElementById("voiceRate");
const voicePitch = document.getElementById("voicePitch");

// ── Voice Output (TTS) ────────────────────────────────────────────────────────

let selectedVoice = null;

function loadVoices() {
  const voices = speechSynthesis.getVoices();
  // Preferir voz feminina em pt-BR, depois en-US feminina
  selectedVoice =
    voices.find(v => v.lang.startsWith("pt") && v.name.toLowerCase().includes("female")) ||
    voices.find(v => v.lang.startsWith("pt")) ||
    voices.find(v => v.name.toLowerCase().includes("female") && v.lang.startsWith("en")) ||
    voices.find(v => v.lang.startsWith("en")) ||
    voices[0] || null;
}

speechSynthesis.addEventListener("voiceschanged", loadVoices);
loadVoices();

function speak(text) {
  if (!voiceOut.checked) return;
  speechSynthesis.cancel();
  const clean = text.replace(/[*_`~#>]/g, "").replace(/\n+/g, " ").trim();
  const utt = new SpeechSynthesisUtterance(clean);
  utt.voice = selectedVoice;
  utt.rate  = parseFloat(voiceRate.value);
  utt.pitch = parseFloat(voicePitch.value);
  utt.volume = 1;
  speechSynthesis.speak(utt);
}

// ── Voice Input (STT) ─────────────────────────────────────────────────────────

let recognition = null;
let isListening = false;

if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.lang = "pt-BR";
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onresult = (e) => {
    const transcript = e.results[0][0].transcript;
    inputEl.value = transcript;
    stopListening();
    sendMessage();
  };

  recognition.onerror = () => stopListening();
  recognition.onend   = () => stopListening();
}

function startListening() {
  if (!recognition || !voiceIn.checked) return;
  isListening = true;
  micBtn.classList.add("listening");
  listenInd.classList.add("active");
  recognition.start();
}

function stopListening() {
  isListening = false;
  micBtn.classList.remove("listening");
  listenInd.classList.remove("active");
  try { recognition && recognition.stop(); } catch (_) {}
}

micBtn.addEventListener("click", () => {
  if (isListening) stopListening();
  else startListening();
});

voiceIn.addEventListener("change", () => {
  if (!voiceIn.checked && isListening) stopListening();
});

// ── Chat ──────────────────────────────────────────────────────────────────────

function appendMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = markdownToHtml(text);
  div.appendChild(bubble);
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function showTyping() {
  const div = document.createElement("div");
  div.className = "msg lilith typing-indicator";
  div.id = "typing";
  div.innerHTML = '<div class="bubble"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>';
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById("typing");
  if (el) el.remove();
}

function sendMessage() {
  const text = inputEl.value.trim();
  if (!text) return;
  appendMessage("user", text);
  inputEl.value = "";
  inputEl.style.height = "auto";
  showTyping();
  socket.emit("message", { text });
}

socket.on("response", (data) => {
  hideTyping();
  if (data.error) {
    appendMessage("lilith", `⚠️ ${data.error}`);
    return;
  }
  appendMessage("lilith", data.text);
  if (data.speak) speak(data.text);

  // Verificar evoluções pendentes após cada resposta
  checkPendingEvolutions();
});

socket.on("connect_error", () => {
  hideTyping();
  appendMessage("lilith", "⚠️ Perdi a conexão com o servidor. Recarregue a página.");
});

// ── Input handlers ────────────────────────────────────────────────────────────

sendBtn.addEventListener("click", sendMessage);

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + "px";
});

// ── Status check ──────────────────────────────────────────────────────────────

async function checkStatus() {
  try {
    const r = await fetch("/api/status");
    const data = await r.json();
    document.getElementById("modelStatus").textContent = data.model_ready ? "✅ Online" : "⏳ Carregando";
    document.getElementById("torStatus").textContent   = data.tor_up     ? "✅ Ativo"   : "❌ Inativo";
    document.getElementById("statusDot").textContent   = data.model_ready ? "● Online" : "● Carregando";
    document.getElementById("statusDot").style.color   = data.model_ready ? "#a855f7" : "#9180b0";
  } catch (_) {}
}

// ── Pending Evolutions ────────────────────────────────────────────────────────

async function checkPendingEvolutions() {
  try {
    const r = await fetch("/api/evolution/pending");
    const list = await r.json();
    const section = document.getElementById("evolutionSection");
    const container = document.getElementById("evolutionList");
    if (!list.length) { section.style.display = "none"; return; }

    section.style.display = "block";
    container.innerHTML = "";
    list.forEach(p => {
      const card = document.createElement("div");
      card.className = "evo-card";
      card.id = `evo-${p.id}`;
      card.innerHTML = `
        <strong>${p.feature}</strong><br>
        <span style="color:#9180b0;font-size:11px">${p.description.slice(0,80)}...</span>
        ${p.new_deps.length ? `<br><span style="color:#6b5880;font-size:11px">Deps: ${p.new_deps.join(", ")}</span>` : ""}
        <div class="evo-actions">
          <button class="evo-btn approve" onclick="approveEvo('${p.id}')">✅ Aprovar</button>
          <button class="evo-btn reject"  onclick="rejectEvo('${p.id}')">❌ Rejeitar</button>
        </div>`;
      container.appendChild(card);
    });
  } catch (_) {}
}

async function approveEvo(id) {
  const r = await fetch(`/api/evolution/approve/${id}`, { method: "POST" });
  const data = await r.json();
  appendMessage("lilith", data.ok ? `✅ ${data.message}` : `❌ Erro: ${data.error}`);
  checkPendingEvolutions();
}

async function rejectEvo(id) {
  const r = await fetch(`/api/evolution/reject/${id}`, { method: "POST" });
  const data = await r.json();
  appendMessage("lilith", `🚫 ${data.message || data.error}`);
  checkPendingEvolutions();
}

// ── Markdown básico ───────────────────────────────────────────────────────────

function markdownToHtml(text) {
  return text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
}

// ── Init ──────────────────────────────────────────────────────────────────────

checkStatus();
setInterval(checkStatus, 30000);
setInterval(checkPendingEvolutions, 15000);
inputEl.focus();
