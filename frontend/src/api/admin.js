import client from "./client";

export function listAllUsers() {
  return client.get("/admin/users").then((r) => r.data);
}

export function createUser(payload) {
  return client.post("/admin/users", payload).then((r) => r.data);
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
