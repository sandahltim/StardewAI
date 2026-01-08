function postJSON(url, data) {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }).then((res) => res.json());
}

function patchJSON(url, data) {
  return fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }).then((res) => res.json());
}

function formatDetails(details) {
  if (!details) return "";
  const entries = Object.entries(details).filter(([, value]) => value);
  if (!entries.length) return "";
  return entries.map(([key, value]) => `${key}: ${value}`).join(" · ");
}

function renderMessage(msg) {
  const article = document.createElement("article");
  article.className = `message message--${msg.role}`;
  article.dataset.messageId = msg.id;

  const header = document.createElement("header");
  const role = document.createElement("span");
  role.className = "role";
  role.textContent = msg.role;
  const timestamp = document.createElement("span");
  timestamp.className = "timestamp";
  timestamp.textContent = msg.created_at || new Date().toISOString();
  header.append(role, timestamp);

  if (msg.role === "agent") {
    const speak = document.createElement("button");
    speak.className = "button small speak-button";
    speak.textContent = "Speak";
    speak.dataset.messageId = msg.id;
    header.append(speak);
  }

  const content = document.createElement("p");
  content.textContent = msg.content;

  article.append(header, content);

  if (msg.reasoning) {
    const details = document.createElement("details");
    details.className = "reasoning";
    const summary = document.createElement("summary");
    summary.textContent = "Reasoning";
    const reasoningBody = document.createElement("div");
    reasoningBody.textContent = msg.reasoning;
    details.append(summary, reasoningBody);
    article.append(details);
  }

  return article;
}

function formatRelativeTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const diffSeconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diffSeconds < 30) return "just now";
  if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`;
  if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)}h ago`;
  if (diffSeconds < 604800) return `${Math.floor(diffSeconds / 86400)}d ago`;
  return date.toLocaleString();
}

function renderTeamMessage(msg) {
  const wrapper = document.createElement("div");
  wrapper.className = "team-message";
  wrapper.dataset.messageId = msg.id;

  const header = document.createElement("div");
  header.className = "team-message__header";
  const sender = document.createElement("span");
  sender.className = "team-message__sender";
  const badge = document.createElement("span");
  badge.className = `team-badge team-badge--${msg.sender || "codex"}`;
  const name = document.createElement("span");
  name.textContent = msg.sender || "codex";
  sender.append(badge, name);
  const timestamp = document.createElement("span");
  timestamp.textContent = formatRelativeTime(msg.created_at);
  header.append(sender, timestamp);

  const content = document.createElement("div");
  content.textContent = msg.content;

  wrapper.append(header, content);
  return wrapper;
}

function renderTask(task) {
  const wrapper = document.createElement("div");
  wrapper.className = "task";
  wrapper.dataset.taskId = task.id;

  const left = document.createElement("div");
  const title = document.createElement("input");
  title.className = "input task-title";
  title.value = task.title;

  const meta = document.createElement("div");
  meta.className = "meta";
  const label = document.createElement("label");
  label.textContent = "Priority";
  const priority = document.createElement("input");
  priority.className = "input task-priority";
  priority.type = "number";
  priority.min = "0";
  priority.max = "5";
  priority.value = task.priority;
  const mode = document.createElement("span");
  mode.textContent = task.mode || "";
  meta.append(label, priority, mode);

  const details = document.createElement("div");
  details.className = "details";
  const notes = document.createElement("input");
  notes.className = "input task-notes";
  notes.placeholder = "Notes";
  notes.value = task.details?.notes || "";
  const location = document.createElement("input");
  location.className = "input task-location";
  location.placeholder = "Location";
  location.value = task.details?.location || "";
  const tool = document.createElement("input");
  tool.className = "input task-tool";
  tool.placeholder = "Tool";
  tool.value = task.details?.tool || "";
  const due = document.createElement("input");
  due.className = "input task-due";
  due.placeholder = "Due";
  due.value = task.details?.due || "";
  details.append(notes, location, tool, due);

  left.append(title, meta, details);

  const right = document.createElement("div");
  right.className = "task-actions";
  const select = document.createElement("select");
  select.className = "input task-status";
  ["queued", "active", "done", "blocked"].forEach((status) => {
    const option = document.createElement("option");
    option.value = status;
    option.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    if (task.status === status) option.selected = true;
    select.append(option);
  });
  const button = document.createElement("button");
  button.className = "button small task-save";
  button.textContent = "Save";
  right.append(select, button);

  wrapper.append(left, right);
  return wrapper;
}

function upsertMessage(msg) {
  const feed = document.getElementById("chatFeed");
  if (!feed || !msg.id) return;
  const existing = feed.querySelector(`[data-message-id='${msg.id}']`);
  if (existing) {
    const content = existing.querySelector("p");
    if (content) content.textContent = msg.content;
    let details = existing.querySelector("details.reasoning");
    if (msg.reasoning) {
      if (!details) {
        details = document.createElement("details");
        details.className = "reasoning";
        const summary = document.createElement("summary");
        summary.textContent = "Reasoning";
        const body = document.createElement("div");
        body.textContent = msg.reasoning;
        details.append(summary, body);
        existing.append(details);
      } else {
        const body = details.querySelector("div");
        if (body) body.textContent = msg.reasoning;
      }
    }
    return;
  }
  feed.prepend(renderMessage(msg));
  while (feed.children.length > 10) {
    feed.removeChild(feed.lastElementChild);
  }
  feed.scrollTop = 0;
}

function upsertTask(task) {
  const list = document.getElementById("taskList");
  if (!list || !task.id) return;
  const existing = list.querySelector(`[data-task-id='${task.id}']`);
  if (existing) {
    const title = existing.querySelector(".task-title");
    if (title) title.value = task.title;
    const priority = existing.querySelector(".task-priority");
    if (priority) priority.value = task.priority;
    const statusSelect = existing.querySelector(".task-status");
    if (statusSelect) statusSelect.value = task.status;
    const notes = existing.querySelector(".task-notes");
    if (notes) notes.value = task.details?.notes || "";
    const location = existing.querySelector(".task-location");
    if (location) location.value = task.details?.location || "";
    const tool = existing.querySelector(".task-tool");
    if (tool) tool.value = task.details?.tool || "";
    const due = existing.querySelector(".task-due");
    if (due) due.value = task.details?.due || "";
    return;
  }
  list.append(renderTask(task));
}

function updateStatus(status) {
  const mode = document.getElementById("statusMode");
  const running = document.getElementById("statusRunning");
  const tick = document.getElementById("statusTick");
  const confirm = document.getElementById("statusConfirm");
  const grant = document.getElementById("statusGrant");
  const error = document.getElementById("statusError");
  const pendingText = document.getElementById("pendingText");
  const pendingAt = document.getElementById("pendingAt");
  const pendingBannerText = document.getElementById("pendingBannerText");
  const pendingBannerAt = document.getElementById("pendingBannerAt");
  const pendingBannerId = document.getElementById("pendingBannerId");
  const pendingBanner = document.getElementById("pendingBanner");
  const confirmGrant = document.getElementById("confirmGrant");
  const confirmApprove = document.getElementById("confirmApprove");
  const pendingBannerApprove = document.getElementById("pendingBannerApprove");
  const stateLocation = document.getElementById("stateLocation");
  const stateTime = document.getElementById("stateTime");
  const stateEnergy = document.getElementById("stateEnergy");
  const stateHolding = document.getElementById("stateHolding");
  const stateWeather = document.getElementById("stateWeather");
  const stateMenu = document.getElementById("stateMenu");
  const stateMood = document.getElementById("stateMood");
  const stateNearby = document.getElementById("stateNearby");
  const planList = document.getElementById("planList");
  const planUpdated = document.getElementById("planUpdated");
  const vlmStatus = document.getElementById("vlmStatus");
  const vlmPerception = document.getElementById("vlmPerception");
  const vlmReasoning = document.getElementById("vlmReasoning");
  const vlmActions = document.getElementById("vlmActions");
  const movementList = document.getElementById("movementList");
  const movementStuck = document.getElementById("movementStuck");
  const movementTrail = document.getElementById("movementTrail");
  const compassUp = document.getElementById("compassUp");
  const compassDown = document.getElementById("compassDown");
  const compassLeft = document.getElementById("compassLeft");
  const compassRight = document.getElementById("compassRight");
  const compassNote = document.getElementById("compassNote");
  const sessionTimeline = document.getElementById("sessionTimeline");

  if (mode) mode.textContent = `Mode: ${status.mode || "helper"}`;
  if (running) running.textContent = `Running: ${status.running ? "yes" : "no"}`;
  if (tick) tick.textContent = `Last tick: ${status.last_tick || "-"}`;
  if (confirm) confirm.textContent = `Confirm: ${status.confirm_before_execute ? "on" : "off"}`;
  if (grant) grant.textContent = `Grant: ${status.confirm_granted ? "yes" : "no"}`;
  if (error) error.textContent = status.last_error || "";
  if (pendingText) pendingText.textContent = status.pending_action || "None";
  if (pendingAt) pendingAt.textContent = status.pending_action_at || "";
  if (pendingBannerText) pendingBannerText.textContent = status.pending_action || "";
  if (pendingBannerAt) pendingBannerAt.textContent = status.pending_action_at || "";
  if (pendingBannerId) pendingBannerId.textContent = status.pending_action_id || "";
  if (confirmGrant) confirmGrant.disabled = !status.confirm_before_execute;
  if (confirmApprove) confirmApprove.disabled = !status.confirm_before_execute;
  if (pendingBannerApprove) pendingBannerApprove.disabled = !status.confirm_before_execute;
  if (pendingBanner) {
    const hasPending = Boolean(status.pending_action);
    pendingBanner.classList.toggle("hidden", !hasPending);
  }
  if (stateLocation) stateLocation.textContent = status.location || "-";
  if (stateTime) stateTime.textContent = status.time_of_day || "-";
  if (stateEnergy) stateEnergy.textContent = status.energy || "-";
  if (stateHolding) stateHolding.textContent = status.holding || "-";
  if (stateWeather) stateWeather.textContent = status.weather || "-";
  if (stateMenu) stateMenu.textContent = status.menu_open ? "yes" : "no";
  if (stateMood) stateMood.textContent = status.mood || "-";
  if (stateNearby) {
    const nearby = status.nearby && status.nearby.length ? status.nearby.join(", ") : "-";
    stateNearby.textContent = nearby;
  }
  if (planUpdated) planUpdated.textContent = status.last_tick || "";
  if (planList) {
    planList.innerHTML = "";
    const plan = status.action_plan && status.action_plan.length ? status.action_plan : ["None"];
    plan.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      planList.append(li);
    });
  }
  if (vlmStatus) vlmStatus.textContent = status.vlm_status || "Idle";
  if (vlmPerception) {
    const location = status.location || "-";
    const time = status.time_of_day || "-";
    const energy = status.energy || "-";
    const holding = status.holding || "-";
    vlmPerception.textContent = `${location} | ${time} | Energy ${energy} | Holding ${holding}`;
  }
  if (vlmReasoning) vlmReasoning.textContent = status.last_reasoning || "None";
  if (vlmActions) {
    vlmActions.innerHTML = "";
    const actions = status.last_actions && status.last_actions.length ? status.last_actions : ["None"];
    actions.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      vlmActions.append(li);
    });
  }
}

function init() {
  const chatFeed = document.getElementById("chatFeed");
  const chatInput = document.getElementById("chatInput");
  const chatSend = document.getElementById("chatSend");
  const teamFeed = document.getElementById("teamFeed");
  const teamSender = document.getElementById("teamSender");
  const teamInput = document.getElementById("teamInput");
  const teamSend = document.getElementById("teamSend");
  const goalInput = document.getElementById("goalInput");
  const goalUpdate = document.getElementById("goalUpdate");
  const taskAdd = document.getElementById("taskAdd");
  const taskList = document.getElementById("taskList");
  const modeSelect = document.getElementById("modeSelect");
  const modeUpdate = document.getElementById("modeUpdate");
  const modeFree = document.getElementById("modeFree");
  const modeConfirm = document.getElementById("modeConfirm");
  const confirmGrant = document.getElementById("confirmGrant");
  const confirmApprove = document.getElementById("confirmApprove");
  const confirmClear = document.getElementById("confirmClear");
  const ttsToggle = document.getElementById("ttsToggle");
  const ttsVoice = document.getElementById("ttsVoice");
  const ttsTest = document.getElementById("ttsTest");
  const pendingBannerApprove = document.getElementById("pendingBannerApprove");
  const pendingBannerDeny = document.getElementById("pendingBannerDeny");
  const quickMode = document.getElementById("quickMode");
  const quickModeSet = document.getElementById("quickModeSet");
  const quickGoal = document.getElementById("quickGoal");
  const quickGoalSet = document.getElementById("quickGoalSet");
  const quickFree = document.getElementById("quickFree");
  const quickConfirm = document.getElementById("quickConfirm");

  const spokenMessages = new Set();
  const seenTeamMessages = new Set();
  const seenChatMessages = new Set();
  let currentStatus = {};

  const updateMovementHistory = (events) => {
    if (!movementList || !movementStuck || !movementTrail) return;
    const positions = events
      .map((event) => event.data || {})
      .filter((pos) => Number.isFinite(pos.x) && Number.isFinite(pos.y));

    movementList.innerHTML = "";
    if (!positions.length) {
      const li = document.createElement("li");
      li.textContent = "None";
      movementList.append(li);
      movementStuck.textContent = "Idle";
      movementStuck.classList.remove("stuck");
      movementTrail.textContent = "-";
      return;
    }

    positions.slice(-10).forEach((pos) => {
      const li = document.createElement("li");
      const label = pos.location ? `${pos.x},${pos.y} (${pos.location})` : `${pos.x},${pos.y}`;
      li.textContent = label;
      movementList.append(li);
    });

    const lastThree = positions.slice(-3);
    const stuck = lastThree.length === 3 &&
      lastThree.every((pos) => pos.x === lastThree[0].x && pos.y === lastThree[0].y);
    movementStuck.textContent = stuck ? "Stuck" : "Moving";
    movementStuck.classList.toggle("stuck", stuck);

    const trail = [];
    for (let i = 1; i < positions.length; i += 1) {
      const prev = positions[i - 1];
      const next = positions[i];
      const dx = next.x - prev.x;
      const dy = next.y - prev.y;
      if (dx > 0) trail.push("→");
      else if (dx < 0) trail.push("←");
      else if (dy > 0) trail.push("↓");
      else if (dy < 0) trail.push("↑");
    }
    movementTrail.textContent = trail.length ? trail.join(" ") : "-";
  };

  const updateCompassCell = (el, direction, info) => {
    if (!el || !info) return;
    el.classList.remove("compass-cell--clear", "compass-cell--blocked");
    if (info.clear) {
      el.classList.add("compass-cell--clear");
      el.textContent = `${direction} ${info.tiles_until_blocked}`;
    } else {
      el.classList.add("compass-cell--blocked");
      el.textContent = `✗ ${info.tiles_until_blocked}`;
    }
  };

  const updateCompass = (surroundings) => {
    if (!surroundings || !surroundings.directions) return;
    updateCompassCell(compassUp, "↑", surroundings.directions.up);
    updateCompassCell(compassDown, "↓", surroundings.directions.down);
    updateCompassCell(compassLeft, "←", surroundings.directions.left);
    updateCompassCell(compassRight, "→", surroundings.directions.right);

    if (compassNote) {
      const blockers = ["up", "down", "left", "right"]
        .map((dir) => {
          const info = surroundings.directions[dir];
          if (!info || info.clear || !info.blocker) return null;
          return `${dir}: ${info.blocker}`;
        })
        .filter(Boolean);
      compassNote.textContent = blockers.length ? `Blocked by ${blockers.join(", ")}` : "All clear";
    }
  };

  const updateSessionTimeline = (events) => {
    if (!sessionTimeline) return;
    sessionTimeline.innerHTML = "";
    if (!events.length) {
      const li = document.createElement("li");
      li.textContent = "None";
      sessionTimeline.append(li);
      return;
    }

    const sorted = [...events].reverse();
    sorted.slice(0, 20).forEach((event) => {
      const li = document.createElement("li");
      const data = event.data || {};
      let summary = "";
      if (event.event_type === "position") {
        summary = `Position ${data.x},${data.y}${data.location ? ` (${data.location})` : ""}`;
      } else if (event.event_type === "action") {
        const status = data.success === false ? "failed" : "ok";
        summary = `Action ${data.action_type || "unknown"} (${status})`;
      } else if (event.event_type === "tool_use") {
        summary = `Tool ${data.tool || "unknown"} (${data.action_type || "use"})`;
      } else {
        summary = `${event.event_type}`;
      }
      li.textContent = summary;
      sessionTimeline.append(li);
    });
  };

  const scrollTeamFeed = () => {
    if (teamFeed) {
      teamFeed.scrollTop = teamFeed.scrollHeight;
    }
  };

  const appendTeamMessage = (msg) => {
    if (!teamFeed || !msg || !msg.id) return;
    if (seenTeamMessages.has(msg.id)) return;
    seenTeamMessages.add(msg.id);
    teamFeed.append(renderTeamMessage(msg));
    scrollTeamFeed();
  };

  const scrollChatFeed = () => {
    if (chatFeed) {
      chatFeed.scrollTop = 0;
    }
  };

  const appendChatMessage = (msg) => {
    if (!msg || !msg.id) return;
    if (seenChatMessages.has(msg.id)) return;
    seenChatMessages.add(msg.id);
    upsertMessage(msg);
    scrollChatFeed();
  };

  if (chatFeed) {
    chatFeed.querySelectorAll("[data-message-id]").forEach((el) => {
      const id = Number(el.dataset.messageId);
      if (id) {
        seenChatMessages.add(id);
      }
    });
    scrollChatFeed();
  }

  if (teamFeed) {
    fetch("/api/team?limit=100")
      .then((res) => res.json())
      .then((messages) => {
        if (!Array.isArray(messages)) return;
        messages.forEach(appendTeamMessage);
      });
  }

  if (chatSend) {
    chatSend.addEventListener("click", () => {
      const content = chatInput.value.trim();
      if (!content) return;

      postJSON("/api/messages", { role: "user", content }).then((msg) => {
        appendChatMessage(msg);
        chatInput.value = "";
      });
    });
  }

  const sendTeamMessage = () => {
    if (!teamInput || !teamSender) return;
    const content = teamInput.value.trim();
    if (!content) return;
    postJSON("/api/team", { sender: teamSender.value, content }).then((msg) => {
      appendTeamMessage(msg);
      teamInput.value = "";
    });
  };

  if (teamSend) {
    teamSend.addEventListener("click", sendTeamMessage);
  }

  if (teamInput) {
    teamInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        sendTeamMessage();
      }
    });
  }

  if (goalUpdate) {
    goalUpdate.addEventListener("click", () => {
      const text = goalInput.value.trim();
      if (!text) return;
      postJSON("/api/goals", { text }).then(() => {
        goalInput.value = text;
      });
    });
  }

  if (modeUpdate) {
    modeUpdate.addEventListener("click", () => {
      postJSON("/api/status", { desired_mode: modeSelect.value });
    });
  }

  if (modeFree) {
    modeFree.addEventListener("change", () => {
      if (modeFree.checked) {
        postJSON("/api/status", { confirm_before_execute: false, confirm_granted: false });
      }
    });
  }

  if (modeConfirm) {
    modeConfirm.addEventListener("change", () => {
      if (modeConfirm.checked) {
        postJSON("/api/status", { confirm_before_execute: true, confirm_granted: false });
      }
    });
  }

  if (confirmGrant) {
    confirmGrant.addEventListener("click", () => {
      postJSON("/api/confirm", {});
    });
  }

  if (confirmApprove) {
    confirmApprove.addEventListener("click", () => {
      postJSON("/api/confirm", {});
    });
  }

  if (confirmClear) {
    confirmClear.addEventListener("click", () => {
      postJSON("/api/action/clear", {});
    });
  }

  if (ttsToggle) {
    ttsToggle.addEventListener("change", () => {
      postJSON("/api/status", { tts_enabled: ttsToggle.checked });
    });
  }

  if (ttsVoice) {
    ttsVoice.addEventListener("change", () => {
      postJSON("/api/status", { tts_voice: ttsVoice.value.trim() });
    });
  }

  if (ttsTest) {
    ttsTest.addEventListener("click", () => {
      fetch("/api/messages")
        .then((res) => res.json())
        .then((messages) => {
          const lastAgent = [...messages].reverse().find((msg) => msg.role === "agent");
          if (lastAgent) {
            postJSON("/api/tts", { message_id: lastAgent.id });
          }
        });
    });
  }

  if (pendingBannerApprove) {
    pendingBannerApprove.addEventListener("click", () => {
      postJSON("/api/confirm", {});
    });
  }

  if (pendingBannerDeny) {
    pendingBannerDeny.addEventListener("click", () => {
      postJSON("/api/action/clear", {});
    });
  }

  if (quickModeSet) {
    quickModeSet.addEventListener("click", () => {
      postJSON("/api/status", { desired_mode: quickMode.value });
    });
  }

  if (quickGoalSet) {
    quickGoalSet.addEventListener("click", () => {
      const text = quickGoal.value.trim();
      if (!text) return;
      postJSON("/api/goals", { text });
    });
  }

  if (quickFree) {
    quickFree.addEventListener("change", () => {
      if (quickFree.checked) {
        postJSON("/api/status", { confirm_before_execute: false, confirm_granted: false });
      }
    });
  }

  if (quickConfirm) {
    quickConfirm.addEventListener("change", () => {
      if (quickConfirm.checked) {
        postJSON("/api/status", { confirm_before_execute: true, confirm_granted: false });
      }
    });
  }

  if (taskAdd) {
    taskAdd.addEventListener("click", () => {
      const title = document.getElementById("taskTitle").value.trim();
      if (!title) return;

      const details = {
        location: document.getElementById("taskLocation").value.trim(),
        tool: document.getElementById("taskTool").value.trim(),
        due: document.getElementById("taskDue").value.trim(),
        notes: document.getElementById("taskNotes").value.trim(),
      };

      const priority = Number(document.getElementById("taskPriority").value || 0);
      const mode = document.getElementById("taskMode").value || null;

      postJSON("/api/tasks", { title, details, priority, mode }).then((task) => {
        upsertTask(task);
        [
          "taskTitle",
          "taskLocation",
          "taskTool",
          "taskPriority",
          "taskDue",
          "taskNotes",
        ].forEach((id) => {
          const el = document.getElementById(id);
          if (el) el.value = "";
        });
        document.getElementById("taskMode").value = "";
      });
    });
  }

  if (taskList) {
    taskList.addEventListener("click", (event) => {
      if (event.target.classList.contains("task-save")) {
        const taskEl = event.target.closest(".task");
        if (!taskEl) return;
        const taskId = taskEl.dataset.taskId;
        const status = taskEl.querySelector(".task-status").value;
        const title = taskEl.querySelector(".task-title").value.trim();
        const priority = Number(taskEl.querySelector(".task-priority").value || 0);
        const details = {
          notes: taskEl.querySelector(".task-notes").value.trim(),
          location: taskEl.querySelector(".task-location").value.trim(),
          tool: taskEl.querySelector(".task-tool").value.trim(),
          due: taskEl.querySelector(".task-due").value.trim(),
        };
        patchJSON(`/api/tasks/${taskId}`, { status, title, priority, details });
      }
    });
  }

  if (chatFeed) {
    chatFeed.addEventListener("click", (event) => {
      if (!event.target.classList.contains("speak-button")) return;
      const messageId = event.target.dataset.messageId;
      if (messageId) {
        postJSON("/api/tts", { message_id: Number(messageId) });
      }
    });
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${window.location.host}/ws`);
  ws.onmessage = (event) => {
    let data = null;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      return;
    }
    if (!data) return;
    if (data.type === "message_created" || data.type === "message_updated") {
      appendChatMessage(data.payload);
      if (
        data.payload &&
        data.payload.role === "agent" &&
        currentStatus.tts_enabled &&
        data.payload.content &&
        !spokenMessages.has(data.payload.id)
      ) {
        spokenMessages.add(data.payload.id);
        postJSON("/api/tts", { message_id: data.payload.id, voice: currentStatus.tts_voice });
      }
    } else if (data.type === "task_created" || data.type === "task_updated") {
      upsertTask(data.payload);
    } else if (data.type === "status_updated") {
      currentStatus = data.payload || {};
      updateStatus(currentStatus);
      if (modeSelect && currentStatus.desired_mode) {
        modeSelect.value = currentStatus.desired_mode;
      }
      if (quickMode && currentStatus.desired_mode) {
        quickMode.value = currentStatus.desired_mode;
      }
      if (modeFree && modeConfirm) {
        modeFree.checked = !currentStatus.confirm_before_execute;
        modeConfirm.checked = Boolean(currentStatus.confirm_before_execute);
      }
      if (quickFree && quickConfirm) {
        quickFree.checked = !currentStatus.confirm_before_execute;
        quickConfirm.checked = Boolean(currentStatus.confirm_before_execute);
      }
      if (ttsToggle) {
        ttsToggle.checked = Boolean(currentStatus.tts_enabled);
      }
      if (ttsVoice && currentStatus.tts_voice) {
        ttsVoice.value = currentStatus.tts_voice;
      }
    } else if (data.type === "goal_updated") {
      if (goalInput && data.payload && data.payload.text) {
        goalInput.value = data.payload.text;
      }
      if (quickGoal && data.payload && data.payload.text) {
        quickGoal.value = data.payload.text;
      }
    } else if (data.type === "team_message_created") {
      appendTeamMessage(data.payload);
    }
  };

  const pollIntervalMs = 5000;
  setInterval(() => {
    const lastChatId = Math.max(...seenChatMessages, 0);
    fetch(`/api/messages?limit=50&since_id=${lastChatId}`)
      .then((res) => res.json())
      .then((messages) => {
        if (!Array.isArray(messages)) return;
        messages.forEach(appendChatMessage);
      })
      .catch(() => {});

    const lastTeamId = Math.max(...seenTeamMessages, 0);
    fetch(`/api/team?limit=100&since_id=${lastTeamId}`)
      .then((res) => res.json())
      .then((messages) => {
        if (!Array.isArray(messages)) return;
        messages.forEach(appendTeamMessage);
      })
      .catch(() => {});

    fetch("/api/session-memory?event_type=position&limit=10")
      .then((res) => res.json())
      .then((events) => {
        if (!Array.isArray(events)) return;
        updateMovementHistory(events);
      })
      .catch(() => {});

    fetch("/api/session-memory?limit=20")
      .then((res) => res.json())
      .then((events) => {
        if (!Array.isArray(events)) return;
        updateSessionTimeline(events);
      })
      .catch(() => {});

    fetch("http://localhost:8790/surroundings")
      .then((res) => res.json())
      .then((payload) => {
        if (!payload || !payload.success) return;
        updateCompass(payload.data);
      })
      .catch(() => {});
  }, pollIntervalMs);
}

window.addEventListener("DOMContentLoaded", init);
