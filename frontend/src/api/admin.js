import client from "./client";

export function listAllUsers() {
  return client.get("/admin/users").then((r) => r.data);
}

export function createUser(payload) {
  return client.post("/admin/users", payload).then((r) => r.data);
}

export function updateUser(id, payload) {
  return client.put(`/admin/users/${id}`, payload).then((r) => r.data);
}

export function deleteUser(id) {
  return client.delete(`/admin/users/${id}`);
}

export function updateUserRole(id, role) {
  return client.patch(`/admin/users/${id}/role`, { role }).then((r) => r.data);
}

export function listTeams() {
  return client.get("/admin/teams").then((r) => r.data);
}

export function createTeam(name) {
  return client.post("/admin/teams", { name }).then((r) => r.data);
}

export function deleteTeam(id) {
  return client.delete(`/admin/teams/${id}`);
}

export function addTeamMember(teamId, userId) {
  return client.post(`/admin/teams/${teamId}/members`, { user_id: userId }).then((r) => r.data);
}

export function removeTeamMember(teamId, userId) {
  return client.delete(`/admin/teams/${teamId}/members/${userId}`).then((r) => r.data);
}

export function listPermissions() {
  return client.get("/admin/permissions").then((r) => r.data);
}

export function createPermission(fromTeamId, toTeamId) {
  return client
    .post("/admin/permissions", { from_team_id: fromTeamId, to_team_id: toTeamId })
    .then((r) => r.data);
}

export function deletePermission(id) {
  return client.delete(`/admin/permissions/${id}`);
}

export function listFunnelPermissions() {
  return client.get("/admin/funnel-permissions").then((r) => r.data);
}

export function createFunnelPermission(teamId, funnelId) {
  return client
    .post("/admin/funnel-permissions", { team_id: teamId, funnel_id: funnelId })
    .then((r) => r.data);
}

export function deleteFunnelPermission(id) {
  return client.delete(`/admin/funnel-permissions/${id}`);
}

export function listRolePermissions() {
  return client.get("/admin/role-permissions").then((r) => r.data);
}

export function updateRolePermission(role, payload) {
  return client.put(`/admin/role-permissions/${role}`, payload).then((r) => r.data);
}

export function getEmailSettings() {
  return client.get("/admin/email").then((r) => r.data);
}

export function saveEmailSettings(payload) {
  return client.put("/admin/email", payload).then((r) => r.data);
}

export function testEmail(toEmail) {
  return client.post("/admin/email/test", { to_email: toEmail }).then((r) => r.data);
}

export function listAutomationRules() {
  return client.get("/admin/automation").then((r) => r.data);
}

export function createAutomationRule(payload) {
  return client.post("/admin/automation", payload).then((r) => r.data);
}

export function updateAutomationRule(id, payload) {
  return client.put(`/admin/automation/${id}`, payload).then((r) => r.data);
}

export function deleteAutomationRule(id) {
  return client.delete(`/admin/automation/${id}`);
}

export function listApiTokens() {
  return client.get("/admin/api-tokens").then((r) => r.data);
}

export function createApiToken(payload) {
  return client.post("/admin/api-tokens", payload).then((r) => r.data);
}

export function revokeApiToken(id) {
  return client.post(`/admin/api-tokens/${id}/revoke`).then((r) => r.data);
}

export function deleteApiToken(id) {
  return client.delete(`/admin/api-tokens/${id}`);
}

export function listMessageTemplates() {
  return client.get("/admin/message-templates").then((r) => r.data);
}

export function createMessageTemplate(payload) {
  return client.post("/admin/message-templates", payload).then((r) => r.data);
}

export function updateMessageTemplate(id, payload) {
  return client.put(`/admin/message-templates/${id}`, payload).then((r) => r.data);
}

export function deleteMessageTemplate(id) {
  return client.delete(`/admin/message-templates/${id}`);
}
