// Point this at your running backend. If you deploy the backend elsewhere,
// this is the only line you need to change.
const API_BASE = "http://127.0.0.1:8000";

let currentPatientId = localStorage.getItem("endotrack_patient_id")
  ? Number(localStorage.getItem("endotrack_patient_id"))
  : null;

let timelineChart = null;

// ---------- Helpers ----------

function $(id) {
  return document.getElementById(id);
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

function showSection(id) {
  $(id).classList.remove("hidden");
}

// ---------- Patient setup ----------

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
    const patient = await apiPost("/patients", payload);
    currentPatientId = patient.id;
    localStorage.setItem("endotrack_patient_id", currentPatientId);
    $("patient-status").textContent = `Profile created (id ${patient.id}). You can start logging symptoms below.`;
    showSection("log-section");
    showSection("results-section");
    $("entry_date").valueAsDate = new Date();
    await refreshTimelineAndRisk();
  } catch (err) {
    $("patient-status").textContent = `Error: ${err.message}`;
  }
});

// ---------- Symptom logging ----------

// Live-update range slider labels
["pain_level", "bleeding_level", "fatigue_level"].forEach((id) => {
  $(id).addEventListener("input", (e) => {
    $(`${id}_val`).textContent = e.target.value;
  });
});

$("symptom-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!currentPatientId) {
    alert("Create a patient profile first.");
    return;
  }

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
    await apiPost(`/patients/${currentPatientId}/symptoms`, payload);
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
  if (!currentPatientId) return;

  const [timeline, risk] = await Promise.all([
    apiGet(`/patients/${currentPatientId}/timeline`),
    apiGet(`/patients/${currentPatientId}/risk-score`),
  ]);

  renderTimelineChart(timeline);
  renderRisk(risk);
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
          borderColor: "#8b3a62",
          backgroundColor: "rgba(139,58,98,0.1)",
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

function renderRisk(risk) {
  $("risk-score-number").textContent = `${risk.score} / ${risk.max_score}`;

  const tierLabel = $("risk-tier-label");
  tierLabel.textContent = risk.tier;
  tierLabel.className = risk.tier; // 'high' | 'moderate' | 'low' -> matches CSS

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

// ---------- Resume existing patient on page load ----------

window.addEventListener("DOMContentLoaded", async () => {
  $("entry_date").valueAsDate = new Date();
  if (currentPatientId) {
    try {
      const patient = await apiGet(`/patients/${currentPatientId}`);
      $("patient-status").textContent = `Welcome back (profile id ${patient.id}).`;
      showSection("log-section");
      showSection("results-section");
      await refreshTimelineAndRisk();
    } catch {
      // Stored id no longer valid (e.g. DB was reset) -- start fresh.
      localStorage.removeItem("endotrack_patient_id");
      currentPatientId = null;
    }
  }
});
