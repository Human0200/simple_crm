import client from "./client";

export function listStages(funnelId) {
  const params = funnelId ? { funnel_id: funnelId } : {};
  return client.get("/stages", { params }).then((r) => r.data);
}

export function createStage(payload) {
  return client.post("/stages", payload).then((r) => r.data);
}

export function updateStage(id, payload) {
  return client.put(`/stages/${id}`, payload).then((r) => r.data);
}

export function reorderStages(stageIds, funnelId) {
  return client
    .post("/stages/reorder", {
      stage_ids: stageIds,
      funnel_id: funnelId || null,
    })
    .then((r) => r.data);
}

export function deleteStage(id) {
  return client.delete(`/stages/${id}`);
}
