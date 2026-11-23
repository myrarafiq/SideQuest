const form = document.querySelector("#plan-form");
const membersBox = document.querySelector("#members");
const message = document.querySelector("#message");
const results = document.querySelector("#results");
const deckList = document.querySelector("#deck");
const FIELD_LABELS = {
  cuisine: "Cuisine", type: "Type", price_range: "Price", price_note: "Price", rating: "Rating",
  neighborhood: "Where", open_until: "Hours", inspection_grade: "Health", free: "Price", free_if_library: "Price",
  size: "Size", nearest_subway: "Subway", official_label: "", famous: "", venue_note: "",
};
let options = null;

function showMessage(text) {
  message.hidden = !text;
  message.textContent = text || "";
}

function checkbox(name, value, label, checked = false) {
  const wrap = document.createElement("label");
  wrap.className = "check";
  const box = document.createElement("input");
  box.type = "checkbox";
  box.name = name;
  box.value = value;
  box.checked = checked;
  wrap.append(box, " " + label);
  return wrap;
}

function renderMembers() {
  const size = Number(document.querySelector("#group-size").value);
  const existing = membersBox.querySelectorAll(".member").length;
  for (let i = existing; i < size; i++) {
    const node = document.querySelector("#member-template").content.cloneNode(true);
    node.querySelector("legend").textContent = `Person ${i + 1}`;
    node.querySelector("[name=name]").value = `Person ${i + 1}`;
    const price = node.querySelector("[name=max_price]");
    for (const p of options.prices) {
      const opt = document.createElement("option");
      opt.value = p.value;
      opt.textContent = p.label;
      opt.selected = p.value === 2;
      price.append(opt);
    }
    for (const c of options.categories) node.querySelector(".categories").append(checkbox("categories", c, c));
    for (const t of options.toggles) node.querySelector(".toggles").append(checkbox("toggles", t.id, t.label));
    membersBox.append(node);
  }
  membersBox.querySelectorAll(".member").forEach((el, i) => { el.hidden = i >= size; });
}

function readForm() {
  const size = Number(document.querySelector("#group-size").value);
  const members = [...membersBox.querySelectorAll(".member")].slice(0, size).map((el) => ({
    name: el.querySelector("[name=name]").value,
    max_price: Number(el.querySelector("[name=max_price]").value),
    categories: [...el.querySelectorAll("[name=categories]:checked")].map((b) => b.value),
    toggles: [...el.querySelectorAll("[name=toggles]:checked")].map((b) => b.value),
    needs_wheelchair: el.querySelector("[name=needs_wheelchair]").checked,
  }));
  return {
    room: {
      boroughs: [...document.querySelectorAll("#boroughs input:checked")].map((b) => b.value),
      group_size: size,
      when: document.querySelector("#when").value,
    },
    members,
  };
}

function renderDeck(data) {
  deckList.replaceChildren();
  const l = data.room_limits;
  document.querySelector("#limits").textContent =
    `${l.boroughs.join(", ")} · ${l.when} · up to ${l.max_price}` + (l.wheelchair_access ? " · wheelchair accessible" : "");
  if (!data.deck.length) {
    showMessage(data.message || "Nothing fits. Try another time, more boroughs or a higher budget.");
    results.hidden = true;
    return;
  }
  for (const card of data.deck) {
    const li = document.createElement("li");
    li.className = "card";
    const title = document.createElement("h3");
    if (card.maps_uri) {
      const a = document.createElement("a");
      a.href = card.maps_uri;
      a.target = "_blank";
      a.rel = "noreferrer";
      a.textContent = card.name;
      title.append(a);
    } else {
      title.textContent = card.name;
    }
    const cat = document.createElement("p");
    cat.className = "category";
    cat.textContent = card.category;
    const facts = document.createElement("ul");
    facts.className = "facts";
    for (const [key, value] of Object.entries(card.fields)) {
      if (key === "summary" || key === "tags") continue;
      const item = document.createElement("li");
      item.textContent = FIELD_LABELS[key] ? `${FIELD_LABELS[key]}: ${value}` : value;
      facts.append(item);
    }
    li.append(title, cat, facts);
    if (card.fields.tags && card.fields.tags.length) {
      const tags = document.createElement("p");
      tags.className = "tags";
      tags.textContent = card.fields.tags.join(" · ");
      li.append(tags);
    }
    if (card.fields.summary) {
      const s = document.createElement("p");
      s.className = "summary";
      s.textContent = card.fields.summary;
      li.append(s);
    }
    const who = document.createElement("p");
    who.className = "for";
    who.textContent = card.for.length ? `Good for: ${card.for.join(", ")}` : "A shared pick for the group";
    li.append(who);
    deckList.append(li);
  }
  const notes = Object.entries(data.unserved_members || {}).map(([who, why]) => `No card for ${who}: ${why}.`);
  if (data.deck.length < 10) {
    notes.unshift(`Only ${data.deck.length} place${data.deck.length === 1 ? "" : "s"} fit everyone's limits at that time. ` +
                  "A different time, another borough or a higher budget would give more options.");
  }
  showMessage(notes.join(" "));
  results.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  showMessage("");
  try {
    const response = await fetch("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(readForm()),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Something went wrong.");
    renderDeck(data);
    results.scrollIntoView({ behavior: "smooth" });
  } catch (error) {
    results.hidden = true;
    showMessage(error.message);
  } finally {
    button.disabled = false;
  }
});

async function init() {
  options = await (await fetch("/api/options")).json();
  for (const b of options.boroughs) {
    document.querySelector("#boroughs").append(checkbox("boroughs", b, b, b === "Manhattan"));
  }
  const next = new Date();
  next.setDate(next.getDate() + ((5 - next.getDay() + 7) % 7 || 7));   // next Friday, 7:30 pm
  next.setHours(19, 30, 0, 0);
  const pad = (n) => String(n).padStart(2, "0");
  document.querySelector("#when").value =
    `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}T${pad(next.getHours())}:${pad(next.getMinutes())}`;
  document.querySelector("#group-size").addEventListener("change", renderMembers);
  renderMembers();
}

init();
