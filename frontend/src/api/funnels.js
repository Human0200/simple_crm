import client from "./client";

export function listFunnels() {
  return client.get("/funnels").then((r) => r.data);
}

export function getPreferredFunnel() {
  return client.get("/funnels/preferred").then((r) => r.data);
}

export function getFunnel(id) {
  return client.get(`/funnels/${id}`).then((r) => r.data);
}

export function createFunnel(payload) {
  return client.post("/funnels", payload).then((r) => r.data);
}

export function updateFunnel(id, payload) {
  return client.put(`/funnels/${id}`, payload).then((r) => r.data);
}

export function reorderFunnels(funnelIds) {
  return client
    .post("/funnels/reorder", { funnel_ids: funnelIds })
    .then((r) => r.data);
}

export function deleteFunnel(id) {
  return client.delete(`/funnels/${id}`);
}
