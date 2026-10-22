import { useAuthStore } from "./stores/auth";

const WS_URL = "ws://localhost:8000/ws";

let socket = null;
const listeners = new Set();

export function onTaskEvent(callback) {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

function playNotificationSound() {
  try {
    const audio = new Audio("/message.mp3");
    audio.play().catch(() => {});
  } catch (e) {
    // игнорируем — звук не критичен для работы приложения
  }
}

export function connectRealtime() {
  const auth = useAuthStore();
  if (!auth.token || socket) return;

  socket = new WebSocket(`${WS_URL}?token=${encodeURIComponent(auth.token)}`);

  socket.onmessage = (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      return;
    }
    playNotificationSound();
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
