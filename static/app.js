"use strict";

const byId = (id) => document.getElementById(id);
const statuses = ["Open", "In progress", "Resolved"];
const nextStatus = {"Open": "In progress", "In progress": "Resolved", "Resolved": "Open"};
const labels = {"Open": "Start work", "In progress": "Resolve ticket", "Resolved": "Reopen ticket"};
let tickets = [];

function element(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

async function api(path, options = {}) {
  const response = await fetch("/api" + path, options);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === "string" ? data.detail : "Request failed. Check your inputs and try again.");
  }
  return response.json();
}

function send(path, method, body) {
  return api(path, {method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
}

function renderQueue() {
  byId("metrics").replaceChildren(...statuses.map((status) => {
    const metric = element("div", status, "metric");
    metric.append(element("strong", tickets.filter((ticket) => ticket.status === status).length));
    return metric;
  }));

  const search = byId("search").value.trim().toLowerCase();
  const status = byId("status").value;
  const visible = tickets.filter((ticket) =>
    (!status || ticket.status === status) &&
    [ticket.title, ticket.description, "RD-" + ticket.id].some((text) => text.toLowerCase().includes(search))
  );
  const rows = visible.map((ticket) => {
    const row = document.createElement("tr");
    const title = row.insertCell();
    const link = element("button", ticket.title, "ticket-link");
    link.type = "button";
    link.addEventListener("click", () => openTicket(ticket.id));
    title.append(element("span", "RD-" + ticket.id, "ticket-id"), link);
    row.insertCell().textContent = ticket.category;
    row.insertCell().textContent = ticket.priority;
    const badge = element("span", ticket.status, "badge");
    badge.dataset.status = ticket.status;
    row.insertCell().append(badge);
    return row;
  });
  if (!rows.length) {
    const empty = document.createElement("tr");
    const cell = empty.insertCell();
    cell.colSpan = 4;
    cell.textContent = "No tickets match your filters.";
    rows.push(empty);
  }
  byId("tickets").replaceChildren(...rows);
}

async function loadQueue() {
  byId("page-error").textContent = "";
  try {
    tickets = await api("/tickets");
    renderQueue();
  } catch (error) {
    byId("page-error").textContent = error.message;
  }
}

async function showTicket(id) {
  const ticket = await api("/tickets/" + id);
  byId("detail-title").textContent = "RD-" + id + " · " + ticket.title;
  const metadata = element("p", [ticket.status, ticket.category, ticket.priority + " priority"].join(" · "));
  const description = element("p", ticket.description, "description");
  const action = element("button", labels[ticket.status]);
  action.type = "button";
  action.addEventListener("click", () => submit(action, "detail-error", async () => {
    await send("/tickets/" + id + "/status", "PATCH", {status: nextStatus[ticket.status], version: ticket.version});
    await Promise.all([showTicket(id), loadQueue()]);
  }));

  const form = document.createElement("form");
  const label = element("label", "Troubleshooting note");
  const input = document.createElement("textarea");
  input.required = true;
  input.minLength = 3;
  input.maxLength = 2000;
  label.append(input);
  const save = element("button", "Add note");
  form.append(label, save);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submit(save, "detail-error", async () => {
      await send("/tickets/" + id + "/notes", "POST", {body: input.value});
      input.value = "";
      await showTicket(id);
    });
  });

  const activity = element("ol", "", "activity");
  for (const entry of ticket.activity) {
    const item = element("li", entry.body);
    const date = new Date(entry.created_at.replace(" ", "T") + "Z");
    item.append(element("time", date.toLocaleString()));
    activity.append(item);
  }
  byId("detail-body").replaceChildren(metadata, description, action, form, element("h3", "Activity"), activity);
}

async function openTicket(id) {
  byId("page-error").textContent = "";
  byId("detail-error").textContent = "";
  try {
    await showTicket(id);
    byId("details").showModal();
  } catch (error) {
    byId("page-error").textContent = error.message;
  }
}

async function submit(button, errorId, task) {
  button.disabled = true;
  byId(errorId).textContent = "";
  try {
    await task();
  } catch (error) {
    byId(errorId).textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

byId("new").addEventListener("click", () => byId("editor").showModal());
for (const close of document.querySelectorAll(".close")) {
  close.addEventListener("click", () => close.closest("dialog").close());
}
byId("create").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  submit(event.submitter, "create-error", async () => {
    const ticket = await send("/tickets", "POST", Object.fromEntries(new FormData(form)));
    form.reset();
    byId("editor").close();
    await loadQueue();
    await openTicket(ticket.id);
  });
});
byId("search").addEventListener("input", renderQueue);
byId("status").addEventListener("change", renderQueue);
loadQueue();
