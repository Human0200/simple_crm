import client, { API_ORIGIN } from "./client";

export function updateProfile(fullName, bio, email = "") {
  return client
    .patch("/users/me", { full_name: fullName, bio, email })
    .then((r) => r.data);
}

export function uploadAvatar(file) {
  const form = new FormData();
  form.append("file", file);
  return client
    .post("/users/me/avatar", form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    .then((r) => r.data);
}

export function avatarUrl(user) {
  if (!user?.avatar_url) return null;
  return API_ORIGIN ? API_ORIGIN + user.avatar_url : user.avatar_url;
}
