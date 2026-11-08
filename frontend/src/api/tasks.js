import client from "./client";

/** @deprecated используйте listStages(); оставлено для совместимости */
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

export function deleteTask(id) {
  return client.delete(`/tasks/${id}`);
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

export function changeStatus(id, stageIdOrKey) {
  const payload =
    typeof stageIdOrKey === "number"
      ? { stage_id: stageIdOrKey }
      : { status: stageIdOrKey };
  return client.patch(`/tasks/${id}/status`, payload).then((r) => r.data);
}

export function sendTaskEmail(id, payload) {
  return client.post(`/tasks/${id}/email`, payload).then((r) => r.data);
}

export function listTaskEmails(id) {
  return client.get(`/tasks/${id}/emails`).then((r) => r.data);
}

export function getEmailStatus() {
  return client.get("/email/status").then((r) => r.data);
}

export function listMessageTemplates() {
  return client.get("/email/templates").then((r) => r.data);
}

export function fetchUnreadSummary() {
  return client.get("/tasks/unread").then((r) => r.data);
}

export function markTaskRead(taskId, tabs) {
  return client.post(`/tasks/${taskId}/read`, { tabs }).then((r) => r.data);
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
