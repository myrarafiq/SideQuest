const dbStatus = document.querySelector("#db-status");
const message = document.querySelector("#message");
const roomSection = document.querySelector("#room");
const activitiesList = document.querySelector("#activities");

function showMessage(text) {
  message.hidden = !text;
  message.textContent = text || "";
}

function fillIntake(you) {
  const form = document.querySelector("#intake-form");
  form.hidden = !you;
  if (!you) return;
  form.dataset.roomCode = document.querySelector("#room-code").textContent;
  form.budget_hard.value = you.budget_hard ?? "";
  form.budget_ideal.value = you.budget_ideal ?? "";
  form.starting_area.value = you.starting_area ?? "";
  form.travel_limit_minutes.value = you.travel_limit_minutes ?? "";
  form.free_start.value = you.free_start_local ?? "";
  form.free_end.value = you.free_end_local ?? "";
}

function showRoom(room) {
  roomSection.hidden = false;
  document.querySelector("#room-name").textContent = room.name;
  document.querySelector("#room-code").textContent = room.code;
  document.querySelector("#room-status").textContent = room.status;
  const list = document.querySelector("#members");
  list.replaceChildren();
  for (const member of room.members) {
    const item = document.createElement("li");
    const role = member.role === "organizer" ? " (organizer)" : "";
    const ready = member.ready ? "ready" : "not ready";
    item.textContent = `${member.name}${role} · ${ready}`;
    list.append(item);
  }
  fillIntake(room.you || null);
  const url = new URL(window.location.href);
  url.searchParams.set("code", room.code);
  history.replaceState(null, "", url);
}

async function postJson(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  return data;
}

document.querySelector("#create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button");
  button.disabled = true;
  showMessage("");
  try {
    const room = await postJson("/api/rooms", {
      name: form.name.value,
      room_name: form.room_name.value,
    });
    showRoom(room);
    showMessage("Room created. Share the code.");
  } catch (error) {
    showMessage(error.message);
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#intake-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button");
  button.disabled = true;
  showMessage("");
  try {
    const room = await postJson("/api/rooms/" + encodeURIComponent(form.dataset.roomCode) + "/intake", {
      budget_hard: form.budget_hard.value,
      budget_ideal: form.budget_ideal.value,
      starting_area: form.starting_area.value,
      travel_limit_minutes: form.travel_limit_minutes.value,
      free_start: form.free_start.value,
      free_end: form.free_end.value,
    });
    showRoom(room);
    showMessage("Saved. You are ready. The room list does not show your budget or travel limit.");
  } catch (error) {
    showMessage(error.message);
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#join-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button");
  button.disabled = true;
  showMessage("");
  try {
    const room = await postJson("/api/rooms/join", {
      name: form.name.value,
      code: form.code.value,
    });
    showRoom(room);
    showMessage("You joined the room.");
  } catch (error) {
    showMessage(error.message);
  } finally {
    button.disabled = false;
  }
});

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const data = await response.json();
    if (!data.ok) {
      dbStatus.textContent = "Database is not reachable. " + (data.error || "");
      return;
    }
    dbStatus.textContent = data.tables_ready
      ? "Database connected."
      : "Database connected, but the tables are not created yet. Apply schema.sql to an empty database.";
  } catch (error) {
    dbStatus.textContent = "Could not reach the server.";
  }
}

function formatWhen(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("en-US", { timeZone: "America/New_York" });
}

async function loadActivities() {
  let data;
  try {
    const response = await fetch("/api/activities");
    data = await response.json();
  } catch (error) {
    activitiesList.replaceChildren();
    const item = document.createElement("li");
    item.textContent = "Could not load activities.";
    activitiesList.append(item);
    return;
  }
  activitiesList.replaceChildren();
  if (data.error) {
    const item = document.createElement("li");
    item.textContent = data.error;
    activitiesList.append(item);
    return;
  }
  if (!data.activities.length) {
    const item = document.createElement("li");
    item.textContent = "No activities loaded yet.";
    activitiesList.append(item);
    return;
  }
  for (const activity of data.activities) {
    const item = document.createElement("li");
    const when = formatWhen(activity.starttime);
    const bits = [activity.title, activity.location, when, activity.source].filter(Boolean);
    if (activity.url) {
      const link = document.createElement("a");
      link.href = activity.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = bits[0];
      item.append(link);
      if (bits.length > 1) {
        item.append(" — " + bits.slice(1).join(" · "));
      }
    } else {
      item.textContent = bits.join(" · ");
    }
    activitiesList.append(item);
  }
}

async function readJson(response) {
  try {
    return await response.json();
  } catch (error) {
    return {};
  }
}

async function loadRoomFromUrl() {
  const code = (new URLSearchParams(window.location.search).get("code") || "").trim().toUpperCase();
  if (!code) return;
  document.querySelector("#join-form [name=code]").value = code;
  const response = await fetch("/api/rooms/" + encodeURIComponent(code));
  const data = await readJson(response);
  if (!response.ok) {
    showMessage(data.error || "Could not open that room.");
    return;
  }
  showRoom(data);
}

loadHealth();
loadActivities();
loadRoomFromUrl();
