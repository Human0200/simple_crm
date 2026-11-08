import axios from "axios";

// По умолчанию same-origin (/api через nginx). Для Vite-dev задайте VITE_API_ORIGIN=http://localhost:8000
const raw = import.meta.env.VITE_API_ORIGIN;
export const API_ORIGIN =
  raw === undefined || raw === null || raw === ""
    ? ""
    : String(raw).replace(/\/$/, "");

const client = axios.create({
  baseURL: API_ORIGIN ? `${API_ORIGIN}/api` : "/api",
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default client;
