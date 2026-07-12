// Point this at your running backend. If you deploy the backend elsewhere,
// this is the only line you need to change.
const API_BASE = "http://127.0.0.1:8000";

let authToken = localStorage.getItem("endotrack_token") || null;
let timelineChart = null;
let cycleChart = null;

// ---------- Helpers ----------

function $(id) {
  return document.getElementById(id);
}

function authHeaders() {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

function showSection(id) {
  $(id).classList.remove("hidden");
}

function hideSection(id) {
  $(id).classList.add("hidden");
}

// ---------- Sliding page mechanism ----------
// #page-login and #page-app sit side by side; toggling "show-app" on the
// wrapper slides one out and the other in (see the CSS transition rules).
// Because both pages are position:absolute, the wrapper needs its height
// set explicitly in JS -- otherwise it collapses to 0, since absolutely
// positioned children don't contribute to a parent's height.

function measurePageHeight(pageEl) {
  $("page-wrapper").style.height = `${pageEl.scrollHeight}px`;
}

function goToAppPage() {
  $("page-wrapper").classList.add("show-app");
  // Wait a tick so newly-revealed sections are laid out before measuring.
  requestAnimationFrame(() => measurePageHeight($("page-app")));
}

function goToLoginPage() {
  $("page-wrapper").classList.remove("show-app");
  requestAnimationFrame(() => measurePageHeight($("page-login")));
}

// ---------- Auth ----------

$("login-btn").addEventListener("click", async () => {
  const email = $("auth_email").value;
  const password = $("auth_password").value;
  if (!email || !password) {
    $("auth-status").textContent = "Enter both email and password.";
    return;
  }

  try {
    // Login uses OAuth2's standard form-encoded body, not JSON, because the
    // backend uses FastAPI's built-in OAuth2PasswordRequestForm.
    const form = new URLSearchParams();
    form.append("username", email); // the backend treats "username" as the email
    form.append("password", password);

    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    authToken = data.access_token;
    localStorage.setItem("endotrack_token", authToken);
    $("auth-status").textContent = "Logged in.";
    await afterLogin();
  } catch (err) {
    $("auth-status").textContent = `Error: ${err.message}`;
  }
});

$("register-btn").addEventListener("click", async () => {
  const email = $("auth_email").value;
  const password = $("auth_password").value;
  if (!email || !password) {
    $("auth-status").textContent = "Enter both email and password.";
    return;
  }
  if (password.length < 8) {
    $("auth-status").textContent = "Password must be at least 8 characters.";
    return;
  }

  try {
    await apiPost("/auth/register", { email, password });
    $("auth-status").textContent = "Account created. Logging you in...";
    $("login-btn").click();
  } catch (err) {
    $("auth-status").textContent = `Error: ${err.message}`;
  }
});

$("logout-btn").addEventListener("click", () => {
  authToken = null;
  localStorage.removeItem("endotrack_token");
  $("auth_email").value = "";
  $("auth_password").value = "";
  $("auth-status").textContent = "Logged out.";
  hideSection("setup-section");
  hideSection("log-section");
  hideSection("cycle-section");
  hideSection("results-section");
  goToLoginPage();
});

async function afterLogin() {
  goToAppPage();

  // Does this account already have a patient profile?
  try {
    await apiGet("/patients/me");
    // Profile exists -- skip straight to logging symptoms.
    showSection("log-section");
    showSection("cycle-section");
    showSection("results-section");
    $("entry_date").valueAsDate = new Date();
    await refreshTimelineAndRisk();
  } catch {
    // No profile yet (404) -- show the create-profile form.
    showSection("setup-section");
  }
  requestAnimationFrame(() => measurePageHeight($("page-app")));
}

// ---------- Patient profile setup ----------

$("trying_to_conceive").addEventListener("change", (e) => {
  $("months-trying-wrap").style.display = e.target.checked ? "block" : "none";
});

$("create-patient-btn").addEventListener("click", async () => {
  const payload = {
    display_name: $("display_name").value || null,
    age: $("age").value ? Number($("age").value) : null,
    trying_to_conceive: $("trying_to_conceive").checked,
    months_trying_to_conceive: $("months_trying_to_conceive").value
      ? Number($("months_trying_to_conceive").value)
      : null,
    family_history_endometriosis: $("family_history_endometriosis").checked,
  };

  try {
    await apiPost("/patients", payload);
    $("patient-status").textContent = "Profile created. You can start logging symptoms below.";
    hideSection("setup-section");
    showSection("log-section");
    showSection("cycle-section");
    showSection("results-section");
    $("entry_date").valueAsDate = new Date();
    await refreshTimelineAndRisk();
    requestAnimationFrame(() => measurePageHeight($("page-app")));
  } catch (err) {
    $("patient-status").textContent = `Error: ${err.message}`;
  }
});

// ---------- Cycle logging ----------

$("cycle-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    start_date: $("cycle_start_date").value,
    end_date: $("cycle_end_date").value || null,
    flow_level: Number($("flow_level").value),
  };

  try {
    await apiPost("/patients/me/cycles", payload);
    $("cycle-status").textContent = "Period logged.";
    e.target.reset();
    $("flow_level_val").textContent = "0";
    await refreshTimelineAndRisk();
  } catch (err) {
    $("cycle-status").textContent = `Error: ${err.message}`;
  }
});

async function renderCycleHistory() {
  const cycles = await apiGet("/patients/me/cycles");
  const container = $("cycle-history");

  if (cycles.length === 0) {
    container.innerHTML = `<p style="font-size:0.85rem; color:var(--muted);">No periods logged yet.</p>`;
    return;
  }

  // Most recent first
  const sorted = [...cycles].reverse();
  const rows = sorted
    .map((c) => {
      const start = new Date(c.start_date + "T00:00:00").toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      });
      const end = c.end_date
        ? new Date(c.end_date + "T00:00:00").toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          })
        : "ongoing";
      const flow = c.flow_level != null ? `${c.flow_level}/10 flow` : "";
      return `<li>${start} &ndash; ${end} ${flow ? `&middot; ${flow}` : ""}</li>`;
    })
    .join("");

  container.innerHTML = `<ul style="padding-left:1.1rem; font-size:0.85rem; color:var(--muted);">${rows}</ul>`;
}

// ---------- Symptom logging ----------

["pain_level", "bleeding_level", "fatigue_level", "flow_level"].forEach((id) => {
  $(id).addEventListener("input", (e) => {
    $(`${id}_val`).textContent = e.target.value;
  });
});

$("symptom-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    entry_date: $("entry_date").value,
    pain_level: Number($("pain_level").value),
    on_period: $("on_period").checked,
    pain_during_intercourse: $("pain_during_intercourse").checked,
    bleeding_level: Number($("bleeding_level").value),
    fatigue_level: Number($("fatigue_level").value),
    bowel_symptoms: $("bowel_symptoms").checked,
    bladder_symptoms: $("bladder_symptoms").checked,
    took_pain_medication: $("took_pain_medication").checked,
    missed_work_or_school: $("missed_work_or_school").checked,
    notes: $("notes").value || null,
  };

  try {
    await apiPost("/patients/me/symptoms", payload);
    e.target.reset();
    $("entry_date").valueAsDate = new Date();
    ["pain_level", "bleeding_level", "fatigue_level"].forEach((id) => {
      $(`${id}_val`).textContent = "0";
    });
    await refreshTimelineAndRisk();
  } catch (err) {
    alert(`Could not save entry: ${err.message}`);
  }
});

// ---------- Timeline + risk score ----------

$("refresh-btn").addEventListener("click", refreshTimelineAndRisk);

async function refreshTimelineAndRisk() {
  if (!authToken) return;

  const [timeline, risk, cycleAnalysis] = await Promise.all([
    apiGet("/patients/me/timeline"),
    apiGet("/patients/me/risk-score"),
    apiGet("/patients/me/cycle-analysis"),
  ]);

  renderTimelineChart(timeline);
  renderGallery(timeline);
  renderRisk(risk);
  renderCycleCorrelationChart(cycleAnalysis);
  await renderCycleHistory();

  if ($("page-wrapper").classList.contains("show-app")) {
    requestAnimationFrame(() => measurePageHeight($("page-app")));
  }
}

function painTier(painLevel) {
  if (painLevel >= 7) return "pain-high";
  if (painLevel >= 4) return "pain-moderate";
  return "pain-low";
}

function renderGallery(timeline) {
  const gallery = $("symptom-gallery");
  const emptyState = $("gallery-empty-state");

  if (timeline.length === 0) {
    gallery.innerHTML = "";
    emptyState.classList.remove("hidden");
    return;
  }
  emptyState.classList.add("hidden");

  // Show most recent entries first, newest on top-left of the grid.
  const sorted = [...timeline].reverse();

  gallery.innerHTML = sorted
    .map((entry) => {
      const dateLabel = new Date(entry.date + "T00:00:00").toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      });
      const icons = [
        entry.on_period ? "🩸" : "",
        entry.bowel_symptoms ? "🌀" : "",
        entry.bladder_symptoms ? "💧" : "",
      ]
        .filter(Boolean)
        .join(" ");

      return `
        <div class="gallery-card ${painTier(entry.pain_level)}" title="${dateLabel}">
          <div class="gc-date">${dateLabel}</div>
          <div class="gc-pain">${entry.pain_level}</div>
          <div class="gc-pain-label">pain / 10</div>
          ${icons ? `<div class="gc-icons">${icons}</div>` : ""}
        </div>
      `;
    })
    .join("");
}

function renderTimelineChart(timeline) {
  const labels = timeline.map((t) => t.date);
  const painData = timeline.map((t) => t.pain_level);

  const ctx = $("timeline-chart").getContext("2d");
  if (timelineChart) {
    timelineChart.data.labels = labels;
    timelineChart.data.datasets[0].data = painData;
    timelineChart.update();
    return;
  }

  timelineChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Pain level (0-10)",
          data: painData,
          borderColor: "#0d9488",
          backgroundColor: "rgba(13,148,136,0.1)",
          tension: 0.25,
          fill: true,
          pointRadius: 3,
        },
      ],
    },
    options: {
      scales: {
        y: { min: 0, max: 10, ticks: { stepSize: 2 } },
      },
      plugins: { legend: { display: false } },
    },
  });
}

function renderCycleCorrelationChart(cycleAnalysis) {
  const statusEl = $("cycle-analysis-status");
  const canvas = $("cycle-correlation-chart");

  if (cycleAnalysis.cycles_logged === 0) {
    statusEl.textContent = "Log at least one period start date to see this chart.";
    canvas.classList.add("hidden");
    return;
  }
  if (cycleAnalysis.points.length === 0) {
    statusEl.textContent = `${cycleAnalysis.cycles_logged} period(s) logged, but no symptom entries fall within a logged cycle yet.`;
    canvas.classList.add("hidden");
    return;
  }

  canvas.classList.remove("hidden");
  statusEl.textContent = `Based on ${cycleAnalysis.cycles_logged} logged period(s) and ${cycleAnalysis.entries_matched} matched symptom entries. Day 1 = period start.`;

  const labels = cycleAnalysis.points.map((p) => `Day ${p.cycle_day}`);
  const avgPain = cycleAnalysis.points.map((p) => p.avg_pain);

  const ctx = canvas.getContext("2d");
  if (cycleChart) {
    cycleChart.data.labels = labels;
    cycleChart.data.datasets[0].data = avgPain;
    cycleChart.update();
    return;
  }

  cycleChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Average pain by cycle day",
          data: avgPain,
          backgroundColor: "rgba(3, 105, 161, 0.55)",
          borderRadius: 4,
        },
      ],
    },
    options: {
      scales: {
        y: { min: 0, max: 10, ticks: { stepSize: 2 } },
      },
      plugins: { legend: { display: false } },
    },
  });
}

function renderRisk(risk) {
  $("risk-score-number").textContent = `${risk.score} / ${risk.max_score}`;

  const tierLabel = $("risk-tier-label");
  tierLabel.textContent = risk.tier;
  tierLabel.className = risk.tier;

  $("risk-recommendation").textContent = risk.recommendation;
  $("risk-disclaimer").textContent = risk.disclaimer;

  const list = $("risk-factors");
  list.innerHTML = "";
  if (risk.factors.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No risk factors detected yet from your logged entries.";
    list.appendChild(li);
  } else {
    risk.factors.forEach((f) => {
      const li = document.createElement("li");
      li.textContent = `${f.label} (+${f.points}): ${f.detail}`;
      list.appendChild(li);
    });
  }
}

// ---------- Resume session on page load ----------

window.addEventListener("resize", () => {
  const activePage = $("page-wrapper").classList.contains("show-app")
    ? $("page-app")
    : $("page-login");
  measurePageHeight(activePage);
});

window.addEventListener("DOMContentLoaded", async () => {
  $("entry_date").valueAsDate = new Date();
  measurePageHeight($("page-login")); // default state: showing the login page

  if (authToken) {
    try {
      await apiGet("/auth/me");
      await afterLogin();
    } catch {
      // Token expired or invalid -- clear it and show the login form again.
      authToken = null;
      localStorage.removeItem("endotrack_token");
    }
  }
});
