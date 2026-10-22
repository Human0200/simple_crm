import client from "./client";

export const STATUSES = [
  { value: "backlog", label: "К выполнению" },
  { value: "in_progress", label: "В работе" },
  { value: "review", label: "На проверке" },
  { value: "done", label: "Готово" },
];

export function listTasks() {
  return client.get("/tasks").then((r) => r.data);
}

export function getTask(id) {
  return client.get(`/tasks/${id}`).then((r) => r.data);
}

export function createTask(payload) {
  return client.post("/tasks", payload).then((r) => r.data);
}

export function updateTask(id, payload) {
  return client.put(`/tasks/${id}`, payload).then((r) => r.data);
}

export function addComment(id, text, isResult = false) {
  return client
    .post(`/tasks/${id}/comments`, { text, is_result: isResult })
    .then((r) => r.data);
}

export function setCommentResult(taskId, commentId, isResult) {
  return client
    .patch(`/tasks/${taskId}/comments/${commentId}`, { is_result: isResult })
    .then((r) => r.data);
}

export const REQUIRES_RESULT_STATUSES = ["review", "done"];

export function changeStatus(id, status) {
  return client.patch(`/tasks/${id}/status`, { status }).then((r) => r.data);
}

export function listUsers() {
  return client.get("/users").then((r) => r.data);
}

export function listAssignableUsers() {
  return client.get("/users/assignable").then((r) => r.data);
}

export function listObservableUsers() {
  return client.get("/users/observable").then((r) => r.data);
}
