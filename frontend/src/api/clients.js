import client from "./client";

export function listClients() {
  return client.get("/clients").then((r) => r.data);
}

export function getClient(id) {
  return client.get(`/clients/${id}`).then((r) => r.data);
}

export function createClient(payload) {
  return client.post("/clients", payload).then((r) => r.data);
}

export function updateClient(id, payload) {
  return client.put(`/clients/${id}`, payload).then((r) => r.data);
}

export function deleteClient(id) {
  return client.delete(`/clients/${id}`);
}

export function addClientNote(id, text) {
  return client.post(`/clients/${id}/notes`, { text }).then((r) => r.data);
}

export function listClientEmails(id) {
  return client.get(`/clients/${id}/emails`).then((r) => r.data);
}
