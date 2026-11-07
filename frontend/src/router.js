import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "./stores/auth";
import Login from "./views/Login.vue";
import Board from "./views/Board.vue";
import Profile from "./views/Profile.vue";
import Calendar from "./views/Calendar.vue";
import Admin from "./views/Admin.vue";
import Clients from "./views/Clients.vue";

const routes = [
  { path: "/login", name: "login", component: Login, meta: { title: "Вход" } },
  {
    path: "/",
    name: "board",
    component: Board,
    meta: { requiresAuth: true, title: "Канбан задач" },
  },
  {
    path: "/profile",
    name: "profile",
    component: Profile,
    meta: { requiresAuth: true, title: "Профиль" },
  },
  {
    path: "/calendar",
    name: "calendar",
    component: Calendar,
    meta: { requiresAuth: true, title: "Календарь" },
  },
  {
    path: "/clients",
    name: "clients",
    component: Clients,
    meta: { requiresAuth: true, title: "Клиенты" },
  },
  {
    path: "/admin",
    name: "admin",
    component: Admin,
    meta: { requiresAuth: true, requiresAdmin: true, title: "Администрирование" },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: "login" };
  }
  if (to.name === "login" && auth.isAuthenticated) {
    return { name: "board" };
  }
  if (to.meta.requiresAdmin && !auth.user?.is_admin) {
    return { name: "board" };
  }
  return true;
});

router.afterEach((to) => {
  document.title = to.meta.title || "Канбан задач";
});

export default router;
