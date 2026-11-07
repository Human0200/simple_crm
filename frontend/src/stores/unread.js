import { defineStore } from "pinia";
import { fetchUnreadSummary, markTaskRead as apiMarkRead } from "../api/tasks";

const empty = () => ({
  comments: 0,
  results: 0,
  timeline: 0,
  email: 0,
  total: 0,
});

export const useUnreadStore = defineStore("unread", {
  state: () => ({
    total: 0,
    items: [],
    byTask: {},
  }),
  getters: {
    forTask: (state) => (taskId) => state.byTask[taskId] || empty(),
  },
  actions: {
    applyTaskUnread(taskId, unread) {
      if (!unread) return;
      this.byTask = {
        ...this.byTask,
        [taskId]: {
          comments: unread.comments || 0,
          results: unread.results || 0,
          timeline: unread.timeline || 0,
          email: unread.email || 0,
          total: unread.total || 0,
        },
      };
    },
    hydrateFromTasks(tasks) {
      const map = { ...this.byTask };
      for (const t of tasks || []) {
        if (t.unread) {
          map[t.id] = {
            comments: t.unread.comments || 0,
            results: t.unread.results || 0,
            timeline: t.unread.timeline || 0,
            email: t.unread.email || 0,
            total: t.unread.total || 0,
          };
        }
      }
      this.byTask = map;
      this.total = Object.values(map).reduce((s, u) => s + (u.total || 0), 0);
    },
    async refresh() {
      try {
        const data = await fetchUnreadSummary();
        this.total = data.total || 0;
        this.items = data.items || [];
        const map = {};
        for (const item of this.items) {
          map[item.task_id] = {
            comments: item.comments,
            results: item.results,
            timeline: item.timeline,
            email: item.email,
            total: item.total,
          };
        }
        // keep known zeroed tasks from hydrate
        for (const [id, val] of Object.entries(this.byTask)) {
          if (!(id in map) && !(Number(id) in map)) {
            map[id] = val.total ? empty() : val;
          }
        }
        for (const item of this.items) {
          map[item.task_id] = {
            comments: item.comments,
            results: item.results,
            timeline: item.timeline,
            email: item.email,
            total: item.total,
          };
        }
        this.byTask = map;
      } catch {
        // ignore on login page
      }
    },
    async markRead(taskId, tabs) {
      const unread = await apiMarkRead(taskId, tabs);
      this.applyTaskUnread(taskId, unread);
      await this.refresh();
      return unread;
    },
    clear() {
      this.total = 0;
      this.items = [];
      this.byTask = {};
    },
  },
});
