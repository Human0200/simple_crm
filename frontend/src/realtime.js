import { useAuthStore } from "./stores/auth";
import { API_ORIGIN } from "./api/client";

function wsBase() {
  if (API_ORIGIN) {
    return API_ORIGIN.replace(/^http/, "ws");
  }
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}`;
}

let socket = null;
const listeners = new Set();

/** Один Audio: браузер блокирует play() без жеста; разблокируем на первый клик/клавишу. */
let notifyAudio = null;
let audioUnlocked = false;
let unlockBound = false;

function ensureNotifyAudio() {
  if (!notifyAudio) {
    notifyAudio = new Audio("/message.mp3");
    notifyAudio.preload = "auto";
  }
  return notifyAudio;
}

function unlockNotificationAudio() {
  if (audioUnlocked) return;
  const audio = ensureNotifyAudio();
  audio.muted = true;
  const p = audio.play();
  if (p && typeof p.then === "function") {
    p.then(() => {
      audio.pause();
      audio.currentTime = 0;
      audio.muted = false;
      audioUnlocked = true;
    }).catch(() => {
      audio.muted = false;
    });
  } else {
    audio.muted = false;
    audioUnlocked = true;
  }
}

function bindAudioUnlock() {
  if (unlockBound || typeof window === "undefined") return;
  unlockBound = true;
  const once = () => {
    unlockNotificationAudio();
    window.removeEventListener("pointerdown", once, true);
    window.removeEventListener("keydown", once, true);
  };
  window.addEventListener("pointerdown", once, true);
  window.addEventListener("keydown", once, true);
}

export function onTaskEvent(callback) {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

function playNotificationSound() {
  try {
    bindAudioUnlock();
    const audio = ensureNotifyAudio();
    audio.currentTime = 0;
    audio.muted = false;
    audio.play().catch(() => {
      // ещё не разблокирован — следующий жест разблокирует
    });
  } catch (e) {
    // звук не критичен
  }
}

export function connectRealtime() {
  const auth = useAuthStore();
  if (!auth.token || socket) return;

  bindAudioUnlock();
  ensureNotifyAudio();

  socket = new WebSocket(`${wsBase()}/ws?token=${encodeURIComponent(auth.token)}`);

  socket.onmessage = (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      return;
    }
    // Звук только другим участникам — инициатор действия уже в курсе
    const me = auth.user?.id;
    const actorId = data?.actor_id;
    const isActor =
      me != null && actorId != null && Number(actorId) === Number(me);
    if (!isActor) {
      playNotificationSound();
    }
    listeners.forEach((cb) => cb(data));
  };

  socket.onclose = () => {
    socket = null;
  };

  socket.onerror = () => {
    socket?.close();
  };
}

export function disconnectRealtime() {
  if (socket) {
    socket.close();
    socket = null;
  }
}
