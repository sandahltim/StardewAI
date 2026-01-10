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
    details.open = true;
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
  const vlmParseStats = document.getElementById("vlmParseStats");
  const vlmParseLastTime = document.getElementById("vlmParseLastTime");
  const vlmParseError = document.getElementById("vlmParseError");
  const vlmParseRaw = document.getElementById("vlmParseRaw");
  const navTarget = document.getElementById("navTarget");
  const navBlocked = document.getElementById("navBlocked");
  const navAttempts = document.getElementById("navAttempts");
  const skillStatusCount = document.getElementById("skillStatusCount");
  const skillHistoryTotal = document.getElementById("skillHistoryTotal");
  const skillHistorySuccess = document.getElementById("skillHistorySuccess");
  const skillUsageBars = document.getElementById("skillUsageBars");
  const skillFailureList = document.getElementById("skillFailureList");
  const commentaryText = document.getElementById("commentaryText");
  const commentaryPersonality = document.getElementById("commentaryPersonality");
  const commentaryTts = document.getElementById("commentaryTts");
  const commentaryVolume = document.getElementById("commentaryVolume");
  const sessionUptime = document.getElementById("sessionUptime");
  const sessionThinks = document.getElementById("sessionThinks");
  const sessionActions = document.getElementById("sessionActions");
  const sessionFailures = document.getElementById("sessionFailures");
  const sessionDistance = document.getElementById("sessionDistance");
  const sessionWatered = document.getElementById("sessionWatered");
  const sessionHarvested = document.getElementById("sessionHarvested");
  const sessionActionTypes = document.getElementById("sessionActionTypes");
  const latencyGraph = document.getElementById("latencyGraph");
  const latencyStats = document.getElementById("latencyStats");
  const movementList = document.getElementById("movementList");
  const movementStuck = document.getElementById("movementStuck");
  const movementTrail = document.getElementById("movementTrail");
  const compassUp = document.getElementById("compassUp");
  const compassDown = document.getElementById("compassDown");
  const compassLeft = document.getElementById("compassLeft");
  const compassRight = document.getElementById("compassRight");
  const compassNote = document.getElementById("compassNote");
  const sessionTimeline = document.getElementById("sessionTimeline");
  const memorySearch = document.getElementById("memorySearch");
  const memorySearchBtn = document.getElementById("memorySearchBtn");
  const memoryList = document.getElementById("memoryList");
  const knowledgeList = document.getElementById("knowledgeList");
  const tileStatus = document.getElementById("tileStatus");
  const tileNote = document.getElementById("tileNote");
  const tileProgress = document.getElementById("tileProgress");
  const waterStatus = document.getElementById("waterStatus");
  const waterFill = document.getElementById("waterFill");
  const waterNote = document.getElementById("waterNote");
  const waterSourceStatus = document.getElementById("waterSourceStatus");
  const waterSourceNote = document.getElementById("waterSourceNote");
  const shippingStatus = document.getElementById("shippingStatus");
  const shippingNote = document.getElementById("shippingNote");
  const shippingList = document.getElementById("shippingList");
  const shippingTotal = document.getElementById("shippingTotal");
  const cropProgress = document.getElementById("cropProgress");
  const cropCountdown = document.getElementById("cropCountdown");
  const currentInstruction = document.getElementById("currentInstruction");
  const inventoryGrid = document.getElementById("inventoryGrid");
  const actionLog = document.getElementById("actionLog");
  const cropStatus = document.getElementById("cropStatus");
  const cropStatusNote = document.getElementById("cropStatusNote");
  const locationDisplay = document.getElementById("locationDisplay");
  const positionDisplay = document.getElementById("positionDisplay");
  const actionRepeat = document.getElementById("actionRepeat");
  const harvestStatus = document.getElementById("harvestStatus");
  const harvestNote = document.getElementById("harvestNote");
  const staminaStatus = document.getElementById("staminaStatus");
  const staminaFill = document.getElementById("staminaFill");
  const actionHistory = document.getElementById("actionHistory");
  const bedtimeStatus = document.getElementById("bedtimeStatus");
  const bedtimeNote = document.getElementById("bedtimeNote");
  const daySeasonStatus = document.getElementById("daySeasonStatus");
  const daySeasonFill = document.getElementById("daySeasonFill");
  const daySeasonNote = document.getElementById("daySeasonNote");
  const goalProgressSummary = document.getElementById("goalProgressSummary");
  const goalProgressList = document.getElementById("goalProgressList");
  const spatialMapGrid = document.getElementById("spatialMapGrid");
  const spatialMapNote = document.getElementById("spatialMapNote");
  const farmPlanMeta = document.getElementById("farmPlanMeta");
  const farmPlanWorkflow = document.getElementById("farmPlanWorkflow");
  const farmPlanBarFill = document.getElementById("farmPlanBarFill");
  const farmPlanPercent = document.getElementById("farmPlanPercent");
  const farmPlanGrid = document.getElementById("farmPlanGrid");
  const farmPlanRows = document.getElementById("farmPlanRows");
  const vlmObservation = document.getElementById("vlmObservation");
  const vlmProposed = document.getElementById("vlmProposed");
  const vlmValidation = document.getElementById("vlmValidation");
  const vlmExecuted = document.getElementById("vlmExecuted");
  const vlmOutcome = document.getElementById("vlmOutcome");
  const smapiStatus = document.getElementById("smapiStatus");
  const smapiLastSeen = document.getElementById("smapiLastSeen");
  const lessonsList = document.getElementById("lessonsList");
  const lessonsCount = document.getElementById("lessonsCount");
  const lessonsReset = document.getElementById("lessonsReset");

  const formatDuration = (seconds) => {
    if (!Number.isFinite(seconds) || seconds <= 0) return "-";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (mins === 0) return `${secs}s`;
    return `${mins}m ${secs}s`;
  };

  const updateLatencyGraph = (samples) => {
    if (!latencyGraph || !latencyStats) return;
    latencyGraph.innerHTML = "";
    if (!Array.isArray(samples) || samples.length === 0) {
      latencyStats.textContent = "No samples";
      return;
    }
    const max = Math.max(...samples);
    const avg = samples.reduce((sum, val) => sum + val, 0) / samples.length;
    const recent = samples.slice(-30);
    recent.forEach((val) => {
      const bar = document.createElement("div");
      const height = max ? Math.max(6, Math.round((val / max) * 60)) : 6;
      bar.className = "latency-bar";
      bar.style.height = `${height}px`;
      bar.title = `${Math.round(val)}ms`;
      latencyGraph.append(bar);
    });
    latencyStats.textContent = `Avg ${Math.round(avg)}ms | Max ${Math.round(max)}ms`;
  };

  let smapiOnline = false;
  let smapiLastOk = null;

  const updateSmapiStatus = (online, note) => {
    if (typeof online === "boolean") {
      smapiOnline = online;
      if (online) smapiLastOk = new Date();
    }
    if (smapiStatus) {
      smapiStatus.textContent = smapiOnline ? "Online" : "Offline";
      smapiStatus.classList.toggle("offline", !smapiOnline);
      smapiStatus.classList.toggle("online", smapiOnline);
      if (note) smapiStatus.textContent = note;
    }
    if (smapiLastSeen) {
      if (!smapiLastOk) {
        smapiLastSeen.textContent = "";
      } else {
        const time = smapiLastOk.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        smapiLastSeen.textContent = `(${time})`;
      }
    }
  };

  const applySmapiEmptyState = () => {
    if (compassNote) compassNote.textContent = "SMAPI offline";
    if (tileStatus) tileStatus.textContent = "No tile data";
    if (tileNote) tileNote.textContent = "SMAPI offline";
    if (waterStatus) waterStatus.textContent = "No state data";
    if (waterSourceStatus) waterSourceStatus.textContent = "No surroundings data";
    if (waterSourceNote) waterSourceNote.textContent = "SMAPI offline";
    if (shippingStatus) shippingStatus.textContent = "No state data";
    if (cropStatus) cropStatus.textContent = "No crop data";
    if (cropStatusNote) cropStatusNote.textContent = "SMAPI offline";
    if (harvestStatus) harvestStatus.textContent = "No crop data";
    if (harvestNote) harvestNote.textContent = "SMAPI offline";
    if (staminaStatus) staminaStatus.textContent = "No state data";
  };

  const formatAction = (value) => {
    if (!value) return "-";
    if (typeof value === "string") return value;
    if (typeof value !== "object") return String(value);
    const actionType = value.action_type || value.type || value.action || null;
    if (actionType) {
      const params = value.params ? JSON.stringify(value.params) : "";
      return params ? `${actionType} ${params}` : actionType;
    }
    return JSON.stringify(value);
  };

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
  if (commentaryText && status.commentary_text !== undefined) {
    commentaryText.textContent = status.commentary_text || "Waiting for commentary...";
  }
  if (commentaryPersonality && status.commentary_personality) {
    commentaryPersonality.value = status.commentary_personality;
  }
  if (commentaryTts && status.commentary_tts_enabled !== undefined) {
    commentaryTts.checked = Boolean(status.commentary_tts_enabled);
  }
  if (commentaryVolume && status.commentary_volume !== undefined) {
    commentaryVolume.value = status.commentary_volume;
  }
  if (vlmPerception) {
    const location = status.location || "-";
    const time = status.time_of_day || "-";
    const energy = status.energy || "-";
    const holding = status.holding || "-";
    vlmPerception.textContent = `${location} | ${time} | Energy ${energy} | Holding ${holding}`;
  }
  if (vlmReasoning) vlmReasoning.textContent = status.last_reasoning || "None";
  if (vlmObservation) {
    vlmObservation.textContent = status.vlm_observation || "Waiting for observation...";
  }
  if (vlmProposed) {
    vlmProposed.textContent = formatAction(status.proposed_action);
  }
  if (vlmValidation) {
    const validation = status.validation_status || "-";
    const reason = status.validation_reason ? ` (${status.validation_reason})` : "";
    vlmValidation.textContent = `${validation}${reason}`;
    vlmValidation.classList.remove("passed", "failed");
    if (validation === "passed") vlmValidation.classList.add("passed");
    if (validation === "failed") vlmValidation.classList.add("failed");
  }
  if (vlmExecuted) {
    vlmExecuted.textContent = formatAction(status.executed_action);
  }
  if (vlmOutcome) {
    const outcome = status.executed_outcome || "-";
    vlmOutcome.textContent = outcome;
    vlmOutcome.classList.remove("passed", "failed");
    if (outcome === "success") vlmOutcome.classList.add("passed");
    if (outcome === "failed") vlmOutcome.classList.add("failed");
  }
  if (vlmParseStats) {
    const ok = Number(status.vlm_parse_success || 0);
    const fail = Number(status.vlm_parse_fail || 0);
    vlmParseStats.textContent = `${ok} ok / ${fail} fail`;
  }
  if (vlmParseLastTime || vlmParseError || vlmParseRaw) {
    const errors = Array.isArray(status.vlm_errors) ? status.vlm_errors : [];
    const last = errors.length ? errors[errors.length - 1] : null;
    if (vlmParseLastTime) {
      vlmParseLastTime.textContent = last ? last.time : "No errors";
    }
    if (vlmParseError) {
      vlmParseError.textContent = last ? last.error : "None";
    }
    if (vlmParseRaw) {
      vlmParseRaw.textContent = last ? last.raw_response : "-";
    }
  }
  if (vlmActions) {
    vlmActions.innerHTML = "";
    const actions = status.last_actions && status.last_actions.length ? status.last_actions : ["None"];
    actions.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      vlmActions.append(li);
    });
  }
  if (navTarget) {
    navTarget.textContent = status.navigation_target || "No target";
  }
  if (navBlocked) {
    navBlocked.textContent = status.navigation_blocked ? `Blocked: ${status.navigation_blocked}` : "Blocked: none";
  }
  if (navAttempts) {
    const attempts = Number(status.navigation_attempts || 0);
    navAttempts.textContent = `Move attempts: ${attempts}`;
  }
  if (skillStatusCount) {
    const count = Number(status.available_skills_count || 0);
    skillStatusCount.textContent = `Skills available: ${count}`;
  }
  if (sessionUptime || sessionThinks || sessionActions || sessionFailures) {
    const startedAt = status.session_started_at ? Date.parse(status.session_started_at) : null;
    const seconds = startedAt ? (Date.now() - startedAt) / 1000 : 0;
    if (sessionUptime) sessionUptime.textContent = formatDuration(seconds);
    if (sessionThinks) sessionThinks.textContent = String(status.think_count || 0);
    if (sessionActions) sessionActions.textContent = String(status.action_count || 0);
    if (sessionFailures) sessionFailures.textContent = String(status.action_fail_count || 0);
  }
  if (sessionDistance) {
    sessionDistance.textContent = `${status.distance_traveled || 0} tiles`;
  }
  if (sessionWatered) {
    sessionWatered.textContent = String(status.crops_watered_count || 0);
  }
  if (sessionHarvested) {
    sessionHarvested.textContent = String(status.crops_harvested_count || 0);
  }
  if (sessionActionTypes) {
    sessionActionTypes.innerHTML = "";
    const counts = status.action_type_counts || {};
    const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    if (!entries.length) {
      const li = document.createElement("li");
      li.textContent = "None";
      sessionActionTypes.append(li);
    } else {
      entries.slice(0, 6).forEach(([name, count]) => {
        const li = document.createElement("li");
        li.textContent = `${name}: ${count}`;
        sessionActionTypes.append(li);
      });
    }
  }
  if (latencyGraph || latencyStats) {
    updateLatencyGraph(status.latency_history || []);
  }
  if (currentInstruction) {
    currentInstruction.textContent = status.current_instruction || "No instruction yet.";
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
  const commentaryText = document.getElementById("commentaryText");
  const commentaryPersonality = document.getElementById("commentaryPersonality");
  const commentaryTts = document.getElementById("commentaryTts");
  const commentaryVolume = document.getElementById("commentaryVolume");
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
  let latestState = null;
  let latestPlayer = null;
  const defaultPersonalities = ["sarcastic", "enthusiastic", "grumpy", "zen"];

  const updateMovementHistory = (events, actionEvents) => {
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

    const lastFive = positions.slice(-5);
    const positionStuck = lastFive.length === 5 &&
      lastFive.every((pos) => pos.x === lastFive[0].x && pos.y === lastFive[0].y);
    const recentActions = Array.isArray(actionEvents) ? actionEvents.slice(-5) : [];
    const hasRecentAction = recentActions.length > 0;
    const stuck = positionStuck && hasRecentAction;
    movementStuck.textContent = stuck ? "STUCK" : "Moving";
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

  const getCompassTiles = (info) => {
    if (!info) return null;
    if (Number.isFinite(info.tilesUntilBlocked)) return info.tilesUntilBlocked;
    if (Number.isFinite(info.tiles_until_blocked)) return info.tiles_until_blocked;
    return null;
  };

  const updateCompassCell = (el, direction, info) => {
    if (!el || !info) return;
    el.classList.remove("compass-cell--clear", "compass-cell--blocked");
    const tiles = getCompassTiles(info);
    if (info.clear) {
      el.classList.add("compass-cell--clear");
      el.textContent = tiles === null ? `${direction}` : `${direction} ${tiles}`;
    } else {
      el.classList.add("compass-cell--blocked");
      el.textContent = tiles === null ? "✗" : `✗ ${tiles}`;
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

  const updateTileState = (tile) => {
    if (!tileStatus || !tileProgress || !tileNote) return;
    if (!tile) {
      tileStatus.textContent = "Waiting for tile data...";
      tileNote.textContent = "-";
      tileStatus.className = "tile-status";
      tileProgress.querySelectorAll("span").forEach((span) => {
        span.classList.remove("active", "complete");
      });
      return;
    }

    const state = tile.state || "clear";
    const objectName = tile.object || "";
    const canTill = Boolean(tile.canTill);
    const canPlant = Boolean(tile.canPlant);

    tileStatus.className = "tile-status";
    if (state === "debris") {
      tileStatus.classList.add("debris");
      tileStatus.textContent = `Debris: ${objectName || "Blocked"}`;
      tileNote.textContent = "Clear the tile";
    } else if (state === "watered") {
      tileStatus.classList.add("done");
      tileStatus.textContent = "Watered - Done!";
      tileNote.textContent = "Tile is ready";
    } else if (state === "planted") {
      tileStatus.classList.add("ready-water");
      tileStatus.textContent = "Planted - Ready to Water";
      tileNote.textContent = "Next: water the crop";
    } else if (state === "tilled") {
      tileStatus.classList.add("ready-plant");
      tileStatus.textContent = canPlant ? "Tilled - Ready to Plant" : "Tilled";
      tileNote.textContent = canPlant ? "Plant seeds next" : "Tile tilled";
    } else {
      tileStatus.classList.add("ready-till");
      tileStatus.textContent = canTill ? "Clear - Ready to Till" : "Clear";
      tileNote.textContent = canTill ? "Till soil to plant seeds" : "Tile is clear";
    }

    const stepOrder = ["clear", "tilled", "planted", "watered", "done"];
    const currentIndex = state === "watered" ? 4 : stepOrder.indexOf(state);
    tileProgress.querySelectorAll("span").forEach((span, idx) => {
      span.classList.toggle("active", idx === currentIndex);
      span.classList.toggle("complete", idx < currentIndex);
    });
  };

  const updateWateringCan = (player) => {
    if (!waterStatus || !waterFill || !waterNote) return;
    if (!player) {
      waterStatus.textContent = "Waiting for state...";
      waterNote.textContent = "-";
      waterFill.style.width = "0%";
      waterFill.classList.remove("low", "empty");
      return;
    }
    const water = Number(player.wateringCanWater ?? 0);
    const max = Number(player.wateringCanMax ?? 0);
    if (!max) {
      waterStatus.textContent = "Watering can: unknown";
      waterNote.textContent = "-";
      waterFill.style.width = "0%";
      waterFill.classList.remove("low", "empty");
      return;
    }
    const pct = Math.max(0, Math.min(100, Math.round((water / max) * 100)));
    waterStatus.textContent = `Watering can: ${water}/${max}`;
    waterFill.style.width = `${pct}%`;
    waterFill.classList.remove("low", "empty");
    if (water === 0) {
      waterFill.classList.add("empty");
      waterNote.textContent = "Empty - refill at water source.";
    } else if (pct <= 25) {
      waterFill.classList.add("low");
      waterNote.textContent = "Low - consider refilling soon.";
    } else {
      waterNote.textContent = "OK";
    }
  };

  const formatDirection = (dx, dy) => {
    if (dx === 0 && dy === 0) return "here";
    if (Math.abs(dx) >= Math.abs(dy)) {
      return dx > 0 ? "east" : "west";
    }
    return dy > 0 ? "south" : "north";
  };

  const updateWaterSource = (nearestWater, player) => {
    if (!waterSourceStatus || !waterSourceNote) return;
    waterSourceStatus.classList.remove("low", "empty");
    if (!nearestWater) {
      waterSourceStatus.textContent = "No water data";
      waterSourceNote.textContent = "-";
      return;
    }
    const distance = nearestWater.distance ?? "?";
    const direction = nearestWater.direction || "?";
    waterSourceStatus.textContent = `Water: ${distance} tiles ${direction}`;

    const water = Number(player?.wateringCanWater ?? 0);
    if (water <= 0) {
      waterSourceStatus.classList.add("empty");
      waterSourceNote.textContent = "Empty - refill now.";
    } else if (water <= 10) {
      waterSourceStatus.classList.add("low");
      waterSourceNote.textContent = "Low - plan refill soon.";
    } else {
      waterSourceNote.textContent = "OK";
    }
  };

  const hasSellableItems = (items) => {
    if (!Array.isArray(items)) return false;
    return items.some((item) => item && item.type && item.type !== "tool" && item.stack > 0);
  };

  const updateShippingBin = (state) => {
    if (!shippingStatus || !shippingNote) return;
    shippingStatus.classList.remove("attention");
    if (!state) {
      shippingStatus.textContent = "No state data";
      shippingNote.textContent = "-";
      return;
    }
    const locationName = state.location?.name;
    const bin = state.location?.shippingBin;
    const player = state.player;
    const inventory = state.inventory;
    if (locationName !== "Farm") {
      shippingStatus.textContent = "Shipping bin: off-farm";
      shippingNote.textContent = "Only on Farm";
      return;
    }
    if (!bin || player?.tileX === undefined || player?.tileY === undefined) {
      shippingStatus.textContent = "Shipping bin: unknown";
      shippingNote.textContent = "-";
      return;
    }
    if (!hasSellableItems(inventory)) {
      shippingStatus.textContent = "Shipping bin: no sellables";
      shippingNote.textContent = "Hold onto items";
      return;
    }
    const dx = bin.x - player.tileX;
    const dy = bin.y - player.tileY;
    const distance = Math.abs(dx) + Math.abs(dy);
    const direction = formatDirection(dx, dy);
    shippingStatus.classList.add("attention");
    shippingStatus.textContent = `Bin: ${distance} tiles ${direction}`;
    shippingNote.textContent = "Ready to sell";
  };

  const updateShippingHistory = (items, gameDay) => {
    if (!shippingList || !shippingTotal) return;
    shippingList.innerHTML = "";
    if (!Array.isArray(items) || items.length === 0) {
      const li = document.createElement("li");
      li.textContent = "None";
      shippingList.append(li);
      shippingTotal.textContent = "0g";
      return;
    }
    const filtered = gameDay ? items.filter((item) => Number(item.game_day) === Number(gameDay)) : items;
    if (!filtered.length) {
      const li = document.createElement("li");
      li.textContent = "None";
      shippingList.append(li);
      shippingTotal.textContent = "0g";
      return;
    }
    let total = 0;
    filtered.slice(0, 10).forEach((item) => {
      const li = document.createElement("li");
      const quantity = Number(item.quantity ?? 1);
      const value = Number(item.value ?? 0);
      total += value;
      li.textContent = `${item.item_name} x${quantity} (${value}g)`;
      shippingList.append(li);
    });
    if (filtered.length > 10) {
      const li = document.createElement("li");
      li.textContent = `...and ${filtered.length - 10} more`;
      shippingList.append(li);
    }
    shippingTotal.textContent = `${total}g`;
  };

  const updateCropProgress = (crops) => {
    if (!cropProgress) return;
    cropProgress.innerHTML = "";
    if (!Array.isArray(crops) || !crops.length) {
      const li = document.createElement("li");
      li.textContent = "None";
      cropProgress.append(li);
      return;
    }
    const buckets = {};
    crops.forEach((crop) => {
      const days = Number(crop.daysUntilHarvest ?? 0);
      const key = days <= 0 ? "Ready" : `${days} day${days === 1 ? "" : "s"}`;
      buckets[key] = (buckets[key] || 0) + 1;
    });
    Object.entries(buckets).sort((a, b) => {
      if (a[0] === "Ready") return -1;
      if (b[0] === "Ready") return 1;
      return parseInt(a[0], 10) - parseInt(b[0], 10);
    }).forEach(([label, count]) => {
      const li = document.createElement("li");
      li.textContent = `${label}: ${count}`;
      cropProgress.append(li);
    });
  };

  const updateCropCountdown = (crops) => {
    if (!cropCountdown) return;
    cropCountdown.innerHTML = "";
    if (!Array.isArray(crops) || !crops.length) {
      const li = document.createElement("li");
      li.textContent = "None";
      cropCountdown.append(li);
      return;
    }
    const grouped = {};
    crops.forEach((crop) => {
      const name = crop.cropName || "Crop";
      const days = Number(crop.daysUntilHarvest ?? 0);
      const key = `${name}::${days}`;
      grouped[key] = grouped[key] || { name, days, count: 0 };
      grouped[key].count += 1;
    });
    Object.values(grouped)
      .sort((a, b) => a.days - b.days || a.name.localeCompare(b.name))
      .slice(0, 6)
      .forEach((entry) => {
        const li = document.createElement("li");
        const label = entry.days <= 0 ? "Ready now" : `${entry.days} day${entry.days === 1 ? "" : "s"}`;
        li.textContent = `${entry.name}: ${label} (x${entry.count})`;
        cropCountdown.append(li);
      });
  };

  const updateBedtime = (time, player) => {
    if (!bedtimeStatus || !bedtimeNote) return;
    if (!time) {
      bedtimeStatus.textContent = "Waiting for time...";
      bedtimeNote.textContent = "-";
      return;
    }
    const hour = Number(time.hour ?? time.Hour ?? time.hour24 ?? 0);
    const minute = Number(time.minute ?? time.Minute ?? 0);
    const timeLabel = time.timeString || time.TimeString || `${hour}:${String(minute).padStart(2, "0")}`;
    const stamina = Number(player?.energy ?? player?.stamina ?? 0);
    const max = Number(player?.maxEnergy ?? player?.maxStamina ?? 0);
    const lowEnergy = max ? stamina / max <= 0.25 : stamina <= 10;
    const late = hour >= 24 || (hour >= 22 && minute >= 0);
    let suggestion = "Plenty of time.";
    if (hour >= 26) {
      suggestion = "Too late! Pass out risk.";
    } else if (late && lowEnergy) {
      suggestion = "Low energy + late. Consider sleeping.";
    } else if (late) {
      suggestion = "It's getting late. Wrap up soon.";
    } else if (lowEnergy) {
      suggestion = "Energy is low. Plan to sleep soon.";
    }
    bedtimeStatus.textContent = `Time: ${timeLabel}`;
    bedtimeNote.textContent = suggestion;
  };

  const updateDaySeason = (time) => {
    if (!daySeasonStatus || !daySeasonFill || !daySeasonNote) return;
    if (!time) {
      daySeasonStatus.textContent = "Waiting for time...";
      daySeasonFill.style.width = "0%";
      daySeasonNote.textContent = "-";
      return;
    }
    const season = (time.season || time.Season || "").toString();
    const day = Number(time.day ?? time.Day ?? 0);
    const dayOfWeek = time.dayOfWeek || time.DayOfWeek || "";
    const labelSeason = season ? season.charAt(0).toUpperCase() + season.slice(1) : "Unknown";
    const pct = day ? Math.max(0, Math.min(100, Math.round((day / 28) * 100))) : 0;
    daySeasonStatus.textContent = `${labelSeason} Day ${day || "?"} ${dayOfWeek ? `(${dayOfWeek})` : ""}`.trim();
    daySeasonFill.style.width = `${pct}%`;
    daySeasonNote.textContent = `${day || 0}/28 days`;
  };

  const updateGoalProgress = (tasks) => {
    if (!goalProgressSummary || !goalProgressList) return;
    goalProgressList.innerHTML = "";
    if (!Array.isArray(tasks) || !tasks.length) {
      goalProgressSummary.textContent = "No tasks";
      const li = document.createElement("li");
      li.textContent = "None";
      goalProgressList.append(li);
      return;
    }
    const done = tasks.filter((task) => task.status === "done").length;
    goalProgressSummary.textContent = `${done}/${tasks.length} done`;
    tasks.slice(0, 6).forEach((task) => {
      const li = document.createElement("li");
      const mark = task.status === "done" ? "[x]" : "[ ]";
      li.textContent = `${mark} ${task.title}`;
      goalProgressList.append(li);
    });
  };

  const updateSkillHistory = (history) => {
    if (!skillFailureList) return;
    skillFailureList.innerHTML = "";
    if (!Array.isArray(history) || history.length === 0) {
      const li = document.createElement("li");
      li.textContent = "None";
      skillFailureList.append(li);
      return;
    }
    const failures = history.filter((entry) => !entry.success);
    if (!failures.length) {
      const li = document.createElement("li");
      li.textContent = "None";
      skillFailureList.append(li);
      return;
    }
    failures.slice(0, 5).forEach((entry) => {
      const li = document.createElement("li");
      const reason = entry.failure_reason ? ` - ${entry.failure_reason}` : " - failed";
      li.textContent = `${entry.skill_name}${reason}`;
      skillFailureList.append(li);
    });
  };

  const updateSkillStats = (stats) => {
    if (!skillUsageBars || !skillHistoryTotal || !skillHistorySuccess) return;
    skillUsageBars.innerHTML = "";
    if (!Array.isArray(stats) || stats.length === 0) {
      skillHistoryTotal.textContent = "0 runs";
      skillHistorySuccess.textContent = "0% success";
      const empty = document.createElement("div");
      empty.className = "skill-bar empty";
      empty.textContent = "No data yet";
      skillUsageBars.append(empty);
      return;
    }
    const totals = stats.reduce(
      (acc, entry) => {
        acc.total += Number(entry.total || 0);
        acc.success += Number(entry.success_count || 0);
        return acc;
      },
      { total: 0, success: 0 },
    );
    const overallRate = totals.total ? Math.round((totals.success / totals.total) * 100) : 0;
    skillHistoryTotal.textContent = `${totals.total} runs`;
    skillHistorySuccess.textContent = `${overallRate}% success`;

    const maxTotal = Math.max(...stats.map((entry) => Number(entry.total || 0)), 1);
    stats.slice(0, 6).forEach((entry) => {
      const wrapper = document.createElement("div");
      wrapper.className = "skill-bar";
      const label = document.createElement("div");
      label.className = "skill-bar__label";
      label.textContent = entry.skill_name;
      const track = document.createElement("div");
      track.className = "skill-bar__track";
      const fill = document.createElement("div");
      fill.className = "skill-bar__fill";
      const rate = Number(entry.success_rate || 0);
      if (rate < 50) {
        fill.classList.add("danger");
      } else if (rate < 80) {
        fill.classList.add("warn");
      }
      fill.style.width = `${Math.round((Number(entry.total || 0) / maxTotal) * 100)}%`;
      track.append(fill);
      const meta = document.createElement("div");
      meta.className = "skill-bar__meta";
      meta.textContent = `${entry.total} uses · ${rate}% success`;
      wrapper.append(label, track, meta);
      skillUsageBars.append(wrapper);
    });
  };

  const updateCommentary = (payload) => {
    if (!payload) return;
    if (commentaryText && payload.text !== undefined) {
      commentaryText.textContent = payload.text || "Waiting for commentary...";
    }
    if (commentaryPersonality && payload.personality) {
      commentaryPersonality.value = payload.personality;
    }
    if (commentaryTts && payload.tts_enabled !== undefined) {
      commentaryTts.checked = Boolean(payload.tts_enabled);
    }
    if (commentaryVolume && payload.volume !== undefined) {
      commentaryVolume.value = payload.volume;
    }
  };

  const updateCommentaryVoices = (voices) => {
    if (!commentaryPersonality) return;
    commentaryPersonality.innerHTML = "";
    const list = Array.isArray(voices) && voices.length ? voices : defaultPersonalities;
    list.forEach((voice) => {
      const option = document.createElement("option");
      option.value = voice;
      option.textContent = voice;
      commentaryPersonality.append(option);
    });
  };

  const updateSpatialMap = (tiles, center) => {
    if (!spatialMapGrid || !spatialMapNote || !center) return;
    spatialMapGrid.innerHTML = "";
    if (!Array.isArray(tiles)) {
      spatialMapNote.textContent = "Waiting for map data...";
      return;
    }
    if (!tiles.length) {
      spatialMapNote.textContent = "No map data yet.";
    } else {
      spatialMapNote.textContent = `Tiles tracked: ${tiles.length}`;
    }

    const radius = 10;
    const size = radius * 2 + 1;
    const lookup = new Map();
    tiles.forEach((tile) => {
      if (tile && Number.isFinite(tile.x) && Number.isFinite(tile.y)) {
        lookup.set(`${tile.x},${tile.y}`, tile);
      }
    });

    for (let row = 0; row < size; row += 1) {
      for (let col = 0; col < size; col += 1) {
        const x = center.x + (col - radius);
        const y = center.y + (row - radius);
        const cell = document.createElement("div");
        cell.className = "spatial-cell";
        const tile = lookup.get(`${x},${y}`);
        if (tile) {
          const state = tile.state || "";
          const isWatered = Boolean(tile.watered);
          if (state === "obstacle") cell.classList.add("obstacle");
          else if (state === "ready") cell.classList.add("ready");
          else if (isWatered) cell.classList.add("watered");
          else if (state === "planted" || tile.crop) cell.classList.add("planted");
          else if (state === "tilled") cell.classList.add("tilled");
          cell.title = `${x},${y} ${state || "unknown"} ${tile.crop ? `(${tile.crop})` : ""}`.trim();
        } else {
          cell.title = `${x},${y}`;
        }
        if (x === center.x && y === center.y) {
          cell.classList.add("center");
        }
        spatialMapGrid.append(cell);
      }
    }
  };

  const updateFarmPlan = (plan) => {
    if (!farmPlanMeta || !farmPlanGrid || !farmPlanRows) return;
    farmPlanGrid.innerHTML = "";
    farmPlanRows.innerHTML = "";
    if (!plan || !plan.active || !Array.isArray(plan.plots) || !plan.plots.length) {
      farmPlanMeta.textContent = "No active farm plan.";
      if (farmPlanPercent) farmPlanPercent.textContent = "0% complete";
      if (farmPlanBarFill) farmPlanBarFill.style.width = "0%";
      if (farmPlanWorkflow) {
        farmPlanWorkflow.querySelectorAll("span").forEach((span) => {
          span.classList.remove("done", "active");
        });
      }
      return;
    }

    const activeId = plan.active_plot_id;
    const plot = plan.plots.find((entry) => entry.id === activeId) || plan.plots[0];
    const width = Number(plot.width || 0);
    const height = Number(plot.height || 0);
    const originX = Number(plot.origin_x || 0);
    const originY = Number(plot.origin_y || 0);
    const phase = String(plot.phase || "unknown").toUpperCase();
    if (!width || !height) {
      farmPlanMeta.textContent = "Invalid plot definition.";
      return;
    }

    const current = plan.current_tile || null;
    const next = plan.next_tile || null;
    const currentLabel =
      current && Number.isFinite(current.x) && Number.isFinite(current.y)
        ? `Current ${current.x},${current.y}`
        : "Current -";
    const nextLabel =
      next && Number.isFinite(next.x) && Number.isFinite(next.y) ? `Next ${next.x},${next.y}` : "Next -";
    farmPlanMeta.textContent = `${plot.id || "Plot"} (${width}x${height}) @ ${originX},${originY} · ${currentLabel} · ${nextLabel} · Phase ${phase}`;

    const stepOrder = ["clear", "till", "plant", "water"];
    const phaseKey = String(plot.phase || "").toLowerCase();
    const activeIdx = stepOrder.findIndex((step) => phaseKey.includes(step));
    if (farmPlanWorkflow) {
      farmPlanWorkflow.querySelectorAll("span").forEach((span, idx) => {
        span.classList.toggle("done", activeIdx > -1 && idx < activeIdx);
        span.classList.toggle("active", idx === activeIdx);
      });
    }

    farmPlanGrid.style.gridTemplateColumns = `repeat(${width}, 14px)`;
    farmPlanGrid.style.gridAutoRows = "14px";
    const tiles = plot.tiles || {};
    const doneStates = new Set(["cleared", "tilled", "planted", "watered", "done", "ready"]);
    const blockedStates = new Set(["debris", "blocked", "obstacle"]);
    let doneCount = 0;
    const total = width * height;

    for (let row = 0; row < height; row += 1) {
      let rowDone = 0;
      for (let col = 0; col < width; col += 1) {
        const x = originX + col;
        const y = originY + row;
        const key = `${x},${y}`;
        const state = tiles[key];
        const cell = document.createElement("div");
        cell.className = "farm-plan-cell";
        if (doneStates.has(state)) {
          cell.classList.add("done");
          doneCount += 1;
          rowDone += 1;
        } else if (blockedStates.has(state)) {
          cell.classList.add("blocked");
        }
        if (current && current.x === x && current.y === y) {
          cell.classList.add("current");
          cell.textContent = "●";
        } else if (next && next.x === x && next.y === y) {
          cell.classList.add("next");
        }
        cell.title = `${key} ${state || "pending"}`;
        farmPlanGrid.append(cell);
      }
      const rowEntry = document.createElement("li");
      rowEntry.textContent = `Row ${row}: ${rowDone}/${width}`;
      farmPlanRows.append(rowEntry);
    }

    const percent = total ? Math.round((doneCount / total) * 100) : 0;
    if (farmPlanPercent) farmPlanPercent.textContent = `${doneCount}/${total} tiles (${percent}%)`;
    if (farmPlanBarFill) farmPlanBarFill.style.width = `${percent}%`;
  };

  const updateLessons = (payload) => {
    if (!lessonsList || !lessonsCount) return;
    const lessons = Array.isArray(payload?.lessons) ? payload.lessons : [];
    const count = Number(payload?.count ?? lessons.length);
    lessonsCount.textContent = `${count} lesson${count === 1 ? "" : "s"}`;
    lessonsList.innerHTML = "";
    if (!lessons.length) {
      const item = document.createElement("li");
      item.textContent = "None";
      lessonsList.append(item);
      return;
    }
    lessons.slice(-10).forEach((entry) => {
      const item = document.createElement("li");
      if (entry && typeof entry === "object") {
        const text = entry.text || entry.lesson || JSON.stringify(entry);
        item.textContent = text;
        if (entry.applied) item.classList.add("lesson-applied");
      } else {
        item.textContent = String(entry);
      }
      lessonsList.append(item);
    });
  };

  const updateCropStatus = (crops) => {
    if (!cropStatus || !cropStatusNote) return;
    cropStatus.classList.remove("ok", "warn");
    if (!Array.isArray(crops) || !crops.length) {
      cropStatus.textContent = "No crops detected";
      cropStatusNote.textContent = "-";
      return;
    }
    const total = crops.length;
    const watered = crops.filter((crop) => crop.isWatered).length;
    const unwatered = total - watered;
    cropStatus.textContent = `WATERED: ${watered}/${total}`;
    if (unwatered === 0) {
      cropStatus.classList.add("ok");
      cropStatusNote.textContent = "All crops watered";
    } else {
      cropStatus.classList.add("warn");
      cropStatusNote.textContent = `${unwatered} crop${unwatered === 1 ? "" : "s"} need water`;
    }
  };

  const updateHarvestStatus = (crops) => {
    if (!harvestStatus || !harvestNote) return;
    harvestStatus.classList.remove("ready", "waiting");
    if (!Array.isArray(crops) || !crops.length) {
      harvestStatus.textContent = "No crops detected";
      harvestNote.textContent = "-";
      return;
    }
    const ready = crops.filter((crop) => crop.isReadyForHarvest).length;
    if (ready > 0) {
      harvestStatus.classList.add("ready");
      harvestStatus.textContent = `HARVEST READY: ${ready}`;
      harvestNote.textContent = "Crops ready to pick";
      return;
    }
    const days = crops
      .map((crop) => Number(crop.daysUntilHarvest ?? 0))
      .filter((value) => value > 0);
    const soonest = days.length ? Math.min(...days) : null;
    harvestStatus.classList.add("waiting");
    harvestStatus.textContent = `HARVEST: 0`;
    harvestNote.textContent = soonest ? `Soonest in ${soonest} day${soonest === 1 ? "" : "s"}` : "No harvest data";
  };

  const updateInventoryGrid = (inventory, selectedIndex) => {
    if (!inventoryGrid) return;
    const slots = new Map();
    if (Array.isArray(inventory)) {
      inventory.forEach((item) => {
        if (item && typeof item.slot === "number") {
          slots.set(item.slot, item);
        }
      });
    }
    inventoryGrid.querySelectorAll(".inventory-slot").forEach((slotEl, idx) => {
      const item = slots.get(idx);
      slotEl.classList.toggle("active", idx === selectedIndex);
      const nameEl = slotEl.querySelector(".inventory-slot__name");
      const stackEl = slotEl.querySelector(".inventory-slot__stack");
      if (!item) {
        nameEl.textContent = "Empty";
        stackEl.textContent = "-";
        return;
      }
      nameEl.textContent = item.name || "Unknown";
      stackEl.textContent = item.stack ? `x${item.stack}` : "-";
    });
  };

  const updateActionLog = (events) => {
    if (!actionLog) return;
    actionLog.innerHTML = "";
    if (!Array.isArray(events) || !events.length) {
      const li = document.createElement("li");
      li.textContent = "None";
      actionLog.append(li);
      return;
    }
    events.slice(-10).reverse().forEach((event) => {
      const data = event.data || {};
      const li = document.createElement("li");
      const success = data.success !== false;
      li.className = `action-log__item ${success ? "success" : "fail"}`;
      const name = data.action_type || "unknown";
      const status = success ? "ok" : "fail";
      li.textContent = `${name} (${status})`;
      actionLog.append(li);
    });
  };

  const updateActionRepeat = (events) => {
    if (!actionRepeat) return;
    actionRepeat.classList.remove("repeat");
    if (!Array.isArray(events) || events.length < 3) {
      actionRepeat.textContent = "No repeats detected";
      return;
    }
    const recent = events.slice(-5).map((event) => event.data?.action_type || "unknown");
    const last = recent[recent.length - 1];
    const repeatCount = recent.filter((name) => name === last).length;
    if (repeatCount >= 3) {
      actionRepeat.classList.add("repeat");
      actionRepeat.textContent = `REPEATING: ${last} (${repeatCount}x)`;
    } else {
      actionRepeat.textContent = "No repeats detected";
    }
  };

  const updateStamina = (player) => {
    if (!staminaStatus || !staminaFill) return;
    if (!player) {
      staminaStatus.textContent = "Waiting for state...";
      staminaFill.style.width = "0%";
      staminaFill.classList.remove("medium", "low");
      return;
    }
    const stamina = Number(player.stamina ?? player.energy ?? 0);
    const max = Number(player.maxStamina ?? player.maxEnergy ?? player.max_energy ?? 0);
    if (!max) {
      staminaStatus.textContent = "Energy: unknown";
      staminaFill.style.width = "0%";
      staminaFill.classList.remove("medium", "low");
      return;
    }
    const pct = Math.max(0, Math.min(100, Math.round((stamina / max) * 100)));
    staminaStatus.textContent = `Energy: ${stamina}/${max}`;
    staminaFill.style.width = `${pct}%`;
    staminaFill.classList.remove("medium", "low");
    if (pct <= 25) staminaFill.classList.add("low");
    else if (pct <= 60) staminaFill.classList.add("medium");
  };

  const updateActionHistory = (events) => {
    if (!actionHistory) return;
    actionHistory.innerHTML = "";
    if (!Array.isArray(events) || !events.length) {
      const li = document.createElement("li");
      li.textContent = "None";
      actionHistory.append(li);
      return;
    }
    const recent = events.slice(-10).reverse();
    recent.forEach((event, idx) => {
      const data = event.data || {};
      const action = data.action_type || "unknown";
      const success = data.success !== false;
      const prev = idx > 0 ? recent[idx - 1]?.data?.action_type : null;
      const repeated = prev && prev === action;
      const li = document.createElement("li");
      li.className = `action-log__item ${success ? "success" : "fail"}`;
      const status = success ? "ok" : "fail";
      li.textContent = `${success ? "" : "BLOCKED "} ${action} (${status})${repeated ? " repeat" : ""}`;
      actionHistory.append(li);
    });
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

  const updateMemoryList = (items) => {
    if (!memoryList) return;
    memoryList.innerHTML = "";
    if (!items.length) {
      const li = document.createElement("li");
      li.textContent = "None";
      memoryList.append(li);
      return;
    }
    items.forEach((item) => {
      const li = document.createElement("li");
      const meta = item.metadata || {};
      const location = meta.location ? ` @ ${meta.location}` : "";
      li.textContent = `${item.text}${location}`;
      memoryList.append(li);
    });
  };

  const updateKnowledgeList = (events) => {
    if (!knowledgeList) return;
    knowledgeList.innerHTML = "";
    if (!events.length) {
      const li = document.createElement("li");
      li.textContent = "None";
      knowledgeList.append(li);
      return;
    }
    events.slice(-10).reverse().forEach((event) => {
      const li = document.createElement("li");
      const data = event.data || {};
      li.textContent = `${data.type || "lookup"}: ${data.name || "unknown"}`;
      knowledgeList.append(li);
    });
  };

  const fetchMemories = (query) => {
    const params = new URLSearchParams({ limit: "10" });
    if (query) params.set("query", query);
    fetch(`/api/episodic-memories?${params.toString()}`)
      .then((res) => res.json())
      .then((items) => {
        if (!Array.isArray(items)) return;
        updateMemoryList(items);
      })
      .catch(() => {});
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

  if (commentaryPersonality) {
    commentaryPersonality.addEventListener("change", () => {
      postJSON("/api/commentary/personality", { personality: commentaryPersonality.value });
    });
  }

  if (commentaryTts) {
    commentaryTts.addEventListener("change", () => {
      postJSON("/api/commentary", { tts_enabled: commentaryTts.checked });
    });
  }

  if (commentaryVolume) {
    commentaryVolume.addEventListener("input", () => {
      postJSON("/api/commentary", { volume: Number(commentaryVolume.value) });
    });
  }

  if (lessonsReset) {
    lessonsReset.addEventListener("click", () => {
      postJSON("/api/lessons/clear", {});
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
    } else if (data.type === "commentary_updated") {
      updateCommentary(data.payload);
    } else if (data.type === "farm_plan_updated") {
      updateFarmPlan(data.payload);
    } else if (data.type === "lessons_updated") {
      updateLessons(data.payload);
    }
  };

  const pollIntervalMs = 5000;
  setInterval(() => {
    let smapiChecks = 0;
    let smapiOk = false;
    const finalizeSmapi = () => {
      smapiChecks += 1;
      if (smapiChecks < 2) return;
      updateSmapiStatus(smapiOk);
      if (!smapiOk) applySmapiEmptyState();
    };
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

    Promise.all([
      fetch("/api/session-memory?event_type=position&limit=10").then((res) => res.json()),
      fetch("/api/session-memory?event_type=action&limit=10").then((res) => res.json()),
    ])
      .then(([positions, actions]) => {
        if (!Array.isArray(positions)) return;
        updateMovementHistory(positions, actions);
      })
      .catch(() => {});

    fetch("/api/session-memory?limit=20")
      .then((res) => res.json())
      .then((events) => {
        if (!Array.isArray(events)) return;
        updateSessionTimeline(events);
      })
      .catch(() => {});

    fetch("/api/session-memory?event_type=action&limit=10")
      .then((res) => res.json())
      .then((events) => {
        if (!Array.isArray(events)) return;
        updateActionLog(events);
        updateActionRepeat(events);
        updateActionHistory(events);
      })
      .catch(() => {});

    fetch("/api/session-memory?event_type=knowledge_lookup&limit=10")
      .then((res) => res.json())
      .then((events) => {
        if (!Array.isArray(events)) return;
        updateKnowledgeList(events);
      })
      .catch(() => {});

    fetch("/api/tasks")
      .then((res) => res.json())
      .then((tasks) => {
        if (!Array.isArray(tasks)) return;
        updateGoalProgress(tasks);
      })
      .catch(() => {});

    fetch("/api/skill-history?limit=20")
      .then((res) => res.json())
      .then((history) => {
        if (!Array.isArray(history)) return;
        updateSkillHistory(history);
      })
      .catch(() => {});

    fetch("/api/skill-stats?limit=10")
      .then((res) => res.json())
      .then((stats) => {
        if (!Array.isArray(stats)) return;
        updateSkillStats(stats);
      })
      .catch(() => {});

    fetch("/api/lessons")
      .then((res) => res.json())
      .then((payload) => {
        updateLessons(payload);
      })
      .catch(() => {
        updateLessons({ lessons: [], count: 0 });
      });

    fetch("/api/farm-plan")
      .then((res) => res.json())
      .then((plan) => {
        updateFarmPlan(plan);
      })
      .catch(() => {
        updateFarmPlan(null);
      });

    const smapiBase = `${window.location.protocol}//${window.location.hostname}:8790`;
    fetch(`${smapiBase}/surroundings`)
      .then((res) => res.json())
      .then((payload) => {
        if (!payload || !payload.success) {
          if (compassNote) compassNote.textContent = "SMAPI unavailable";
          updateTileState(null);
          finalizeSmapi();
          return;
        }
        smapiOk = true;
        updateCompass(payload.data);
        updateTileState(payload.data.currentTile);
        updateWaterSource(payload.data.nearestWater, latestPlayer);
        finalizeSmapi();
      })
      .catch(() => {
        if (compassNote) compassNote.textContent = "SMAPI unavailable";
        updateTileState(null);
        updateWaterSource(null, null);
        finalizeSmapi();
      });

    fetch(`${smapiBase}/state`)
      .then((res) => res.json())
      .then((payload) => {
        if (!payload || !payload.success) {
          updateWateringCan(null);
          updateShippingBin(null);
          updateCropProgress(null);
          updateCropCountdown(null);
          finalizeSmapi();
          return;
        }
        smapiOk = true;
        latestState = payload.data || null;
        latestPlayer = payload.data?.player || null;
        updateWateringCan(latestPlayer);
        updateShippingBin(latestState);
        updateCropProgress(latestState?.location?.crops);
        updateCropCountdown(latestState?.location?.crops);
        updateCropStatus(latestState?.location?.crops);
        updateHarvestStatus(latestState?.location?.crops);
        updateInventoryGrid(latestState?.inventory, latestState?.player?.currentToolIndex);
        updateStamina(latestPlayer);
        updateBedtime(latestState?.time, latestPlayer);
        updateDaySeason(latestState?.time);
        const gameDay = latestState?.time?.day ?? latestState?.time?.Day ?? null;
        if (shippingList && shippingTotal) {
          const params = new URLSearchParams();
          if (gameDay) params.set("game_day", gameDay);
          fetch(`/api/shipping${params.toString() ? `?${params.toString()}` : ""}`)
            .then((res) => res.json())
            .then((items) => {
              if (!Array.isArray(items)) return;
              updateShippingHistory(items, gameDay);
            })
            .catch(() => {
              updateShippingHistory(null, gameDay);
            });
        }
        if (locationDisplay) {
          locationDisplay.textContent = latestState?.location?.name || "Unknown";
        }
        if (positionDisplay) {
          const x = latestPlayer?.tileX ?? "?";
          const y = latestPlayer?.tileY ?? "?";
          positionDisplay.textContent = `(${x}, ${y})`;
        }

        const locationName = latestState?.location?.name || "Farm";
        if (spatialMapGrid && spatialMapNote && latestPlayer?.tileX !== undefined && latestPlayer?.tileY !== undefined) {
          const params = new URLSearchParams({ location: locationName });
          fetch(`/api/spatial-map?${params.toString()}`)
            .then((res) => res.json())
            .then((payload) => {
              const tiles = payload?.tiles || [];
              updateSpatialMap(tiles, { x: latestPlayer.tileX, y: latestPlayer.tileY });
            })
            .catch(() => {
              updateSpatialMap(null, { x: latestPlayer.tileX, y: latestPlayer.tileY });
            });
        }
        finalizeSmapi();
      })
      .catch(() => {
        updateWateringCan(null);
        updateShippingBin(null);
        updateCropProgress(null);
        updateCropCountdown(null);
        updateBedtime(null, null);
        updateDaySeason(null);
        updateShippingHistory(null, null);
        if (spatialMapGrid) spatialMapGrid.innerHTML = "";
        if (spatialMapNote) spatialMapNote.textContent = "Spatial map unavailable";
        finalizeSmapi();
      });
  }, pollIntervalMs);

  if (memorySearchBtn) {
    memorySearchBtn.addEventListener("click", () => {
      const query = memorySearch ? memorySearch.value.trim() : "";
      fetchMemories(query);
    });
  }

  if (memorySearch) {
    memorySearch.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        fetchMemories(memorySearch.value.trim());
      }
    });
  }

  if (commentaryPersonality) {
    fetch("/api/commentary/voices")
      .then((res) => res.json())
      .then((payload) => {
        updateCommentaryVoices(payload.personalities || []);
      })
      .catch(() => {
        updateCommentaryVoices(defaultPersonalities);
      });
  }

  if (commentaryText) {
    fetch("/api/commentary")
      .then((res) => res.json())
      .then((payload) => {
        updateCommentary(payload);
      })
      .catch(() => {});
  }

  fetchMemories("");
}

window.addEventListener("DOMContentLoaded", init);
