"use strict";

const STORAGE_KEYS = {
  theme: "todayWhere.theme",
  history: "todayWhere.history.v1",
  metrics: "todayWhere.metrics.v1",
};

const CATEGORY_META = {
  restaurant: { label: "음식점", tag: "FOOD" },
  cafe: { label: "카페", tag: "CAFE" },
  parking: { label: "주차장", tag: "PARK" },
};

const state = {
  selectedRegion: null,
  result: null,
  placeIndexes: { restaurant: 0, cafe: 0, parking: 0 },
  accuracy: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeUrl(value) {
  try {
    const url = new URL(String(value));
    return ["https:", "http:"].includes(url.protocol) ? url.href : "#";
  } catch {
    return "#";
  }
}

function readJsonStorage(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

function setLoading(isLoading, text = "정보를 확인하고 있어요…") {
  $("#loadingText").textContent = text;
  $("#loadingOverlay").hidden = !isLoading;
  document.body.style.overflow = isLoading ? "hidden" : "";
}

function showStatus(message, type = "info") {
  const box = $("#globalStatus");
  box.textContent = message;
  box.classList.toggle("error", type === "error");
  box.hidden = false;
  if (type === "error") box.scrollIntoView({ behavior: "smooth", block: "center" });
}

function hideStatus() {
  $("#globalStatus").hidden = true;
}

async function apiFetch(path, payload, timeoutMs = 26000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error("서버 응답을 읽지 못했습니다. 배포 로그를 확인해 주세요.");
    }
    if (!response.ok || !data.ok) {
      const error = new Error(data?.error?.message || `요청이 실패했습니다(${response.status}).`);
      error.code = data?.error?.code || `HTTP_${response.status}`;
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("응답 시간이 26초를 넘었습니다. 잠시 후 다시 시도해 주세요.");
    }
    if (error instanceof TypeError) {
      throw new Error("서버에 연결하지 못했습니다. 인터넷 연결과 배포 주소를 확인해 주세요.");
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

function selectedInterests() {
  return $$('input[name="interest"]:checked').map((item) => item.value);
}

function tripConditions() {
  return {
    date: $("#tripDate").value,
    departure: $("#departure").value.trim(),
    companion: $("#companion").value,
    transport: $("#transport").value,
    budget: $("#budget").value,
    radius: Number($("#radius").value),
    start_time: $("#startTime").value,
    end_time: $("#endTime").value,
    interests: selectedInterests(),
  };
}

function validateBasicConditions() {
  const values = tripConditions();
  if (!values.date) throw new Error("여행 날짜를 먼저 선택해 주세요.");
  if (values.start_time >= values.end_time) throw new Error("마침 시간은 시작 시간보다 뒤여야 합니다.");
  if (!values.interests.length) throw new Error("관심사를 한 개 이상 선택해 주세요.");
  return values;
}

function setSelectedRegion(region, accuracy = null) {
  state.selectedRegion = region;
  state.accuracy = accuracy;
  const accuracyText = Number.isFinite(accuracy) ? ` · 위치 정확도 약 ±${Math.round(accuracy)}m` : "";
  const box = $("#selectedRegion");
  box.classList.add("confirmed");
  box.innerHTML = `
    <span class="status-dot"></span>
    <div>
      <strong>${escapeHtml(region.display_name)}</strong>
      <small>법정동 ${escapeHtml(region.legal_dong || "미제공")} · 행정동 ${escapeHtml(region.administrative_dong || "미제공")}${escapeHtml(accuracyText)}</small>
    </div>`;
  $("#generateButton").disabled = false;
  $("#suggestionGrid").innerHTML = "";
  showStatus("지역을 실제 행정구역 데이터로 확인했습니다. 이제 ‘AI 하루 여행 만들기’를 눌러 주세요.");
}

function switchLocationMode(mode) {
  $("#manualMode").hidden = mode !== "manual";
  $("#currentMode").hidden = mode !== "current";
  $("#aiMode").hidden = mode !== "ai";
  hideStatus();
}

async function verifyManualRegion() {
  const query = $("#regionQuery").value.trim();
  if (!query) {
    showStatus("빈칸입니다. 예: ‘서울특별시 종로구 청운효자동’처럼 입력해 주세요.", "error");
    $("#regionQuery").focus();
    return;
  }
  setLoading(true, "법정동과 행정동을 확인하고 있어요…");
  try {
    const data = await apiFetch("/api/verify_region", { query }, 15000);
    setSelectedRegion(data.region);
  } catch (error) {
    showStatus(error.message, "error");
  } finally {
    setLoading(false);
  }
}

function getCurrentPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("이 브라우저는 현재 위치 기능을 지원하지 않습니다. 지역을 직접 입력해 주세요."));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, (error) => {
      const messages = {
        1: "위치 권한이 거부되었습니다. 브라우저 설정에서 허용하거나 지역을 직접 입력해 주세요.",
        2: "현재 위치를 확인할 수 없습니다. 잠시 후 다시 시도하거나 직접 입력해 주세요.",
        3: "위치 확인 시간이 초과되었습니다. 직접 입력 방식으로 바꿔 주세요.",
      };
      reject(new Error(messages[error.code] || "현재 위치를 확인하지 못했습니다."));
    }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
  });
}

async function useCurrentLocation() {
  setLoading(true, "브라우저에서 현재 위치를 확인하고 있어요…");
  try {
    const position = await getCurrentPosition();
    const { latitude, longitude, accuracy } = position.coords;
    const data = await apiFetch("/api/current_region", { latitude, longitude }, 15000);
    setSelectedRegion(data.region, accuracy);
    if (accuracy > 1000) showStatus("위치 오차가 큽니다. 표시된 동네가 맞는지 확인하거나 지역을 직접 입력해 주세요.", "error");
  } catch (error) {
    showStatus(error.message, "error");
  } finally {
    setLoading(false);
  }
}

async function requestRegionSuggestions() {
  let conditions;
  try {
    conditions = validateBasicConditions();
  } catch (error) {
    showStatus(error.message, "error");
    return;
  }
  setLoading(true, "AI가 실제로 확인 가능한 동네를 찾고 있어요…");
  try {
    const data = await apiFetch("/api/recommend_regions", conditions);
    $("#suggestionGrid").innerHTML = data.regions.map((region, index) => `
      <button class="suggestion-button" type="button" data-region-index="${index}">
        <strong>${escapeHtml(region.display_name)}</strong>
        <small>법정동 ${escapeHtml(region.legal_dong || "-")} · 행정동 ${escapeHtml(region.administrative_dong || "-")}</small>
        <small>${escapeHtml(region.reason)}</small>
      </button>`).join("");
    $$("[data-region-index]").forEach((button) => button.addEventListener("click", () => {
      setSelectedRegion(data.regions[Number(button.dataset.regionIndex)]);
    }));
    showStatus("AI 후보를 주소 데이터로 검증했습니다. 마음에 드는 지역을 하나 선택해 주세요.");
  } catch (error) {
    showStatus(error.message, "error");
  } finally {
    setLoading(false);
  }
}

function renderPlan(result) {
  $("#planEmpty").hidden = true;
  $("#planResult").hidden = false;
  $("#resultTitle").textContent = result.title;
  $("#resultSummary").textContent = result.summary;
  $("#timeline").innerHTML = result.schedule.map((item) => `
    <li>
      <time>${escapeHtml(item.time)}</time>
      <div><h4>${escapeHtml(item.place_name)}</h4><p>${escapeHtml(item.activity)} · ${escapeHtml(item.reason)}</p><p>${escapeHtml(item.address)}</p></div>
      <a href="${safeUrl(item.url)}" target="_blank" rel="noopener noreferrer">지도 확인 ↗</a>
    </li>`).join("");
}

function currentPlaceIndex(kind, selected) {
  const pool = state.result?.candidate_pools?.[kind] || [];
  const found = pool.findIndex((item) => item.id === selected?.id);
  return found >= 0 ? found : 0;
}

function renderPlaces() {
  const places = state.result?.places || {};
  $("#placeGrid").innerHTML = Object.keys(CATEGORY_META).map((kind) => {
    const meta = CATEGORY_META[kind];
    const place = places[kind];
    if (!place) {
      return `<article class="place-card"><span>${meta.tag}</span><h3>${meta.label} 검색 결과 없음</h3><p>현재 반경에서 검증된 장소를 찾지 못했습니다. 반경을 넓혀 다시 만들어 주세요.</p></article>`;
    }
    const distance = place.distance_m ? `${(place.distance_m / 1000).toFixed(1)} km` : "거리 미제공";
    return `<article class="place-card">
      <span>${meta.tag}</span><h3>${escapeHtml(place.name)}</h3>
      <p>${escapeHtml(place.address)}</p><p>${escapeHtml(place.phone)} · ${escapeHtml(distance)}</p>
      <p class="reason"><strong>추천 이유</strong><br />${escapeHtml(place.reason)}</p>
      <div class="card-actions">
        <a href="${safeUrl(place.url)}" target="_blank" rel="noopener noreferrer">카카오맵</a>
        <button type="button" data-regenerate="${kind}">다른 ${meta.label}</button>
      </div></article>`;
  }).join("");
  $$('[data-regenerate]').forEach((button) => button.addEventListener("click", () => rotatePlace(button.dataset.regenerate)));
}

function rotatePlace(kind) {
  const pool = state.result?.candidate_pools?.[kind] || [];
  if (pool.length < 2) {
    showStatus(`${CATEGORY_META[kind].label} 후보가 더 없습니다. 검색 반경을 넓혀 전체를 다시 추천해 주세요.`, "error");
    return;
  }
  const nextIndex = (state.placeIndexes[kind] + 1) % pool.length;
  state.placeIndexes[kind] = nextIndex;
  state.result.places[kind] = { ...pool[nextIndex], reason: "사용자의 재추천 요청에 따라 다음 검증 후보를 보여 드립니다." };
  updateMetrics({ regenerations: 1 });
  renderPlaces();
  renderSummary(state.result);
  autoSaveHistory();
  showStatus(`다른 ${CATEGORY_META[kind].label}으로 바꿨습니다. 외부 API를 다시 부르지 않아 비용을 아꼈습니다.`);
}

function renderWeather(weather, tip) {
  if (!weather?.available) {
    $("#weatherResult").innerHTML = `<p class="muted">${escapeHtml(weather?.message || "날씨 정보가 없습니다.")}</p>`;
    return;
  }
  $("#weatherResult").innerHTML = `
    <h3>${escapeHtml(weather.condition)}</h3><p>${escapeHtml(weather.date)} · ${escapeHtml(tip || "")}</p>
    <div class="weather-numbers">
      <div><small>최고</small><strong>${escapeHtml(weather.temperature_max)}℃</strong></div>
      <div><small>최저</small><strong>${escapeHtml(weather.temperature_min)}℃</strong></div>
      <div><small>강수</small><strong>${escapeHtml(weather.precipitation_probability)}%</strong></div>
    </div><p class="field-help">출처: ${escapeHtml(weather.source)}</p>`;
}

function renderEvents(events) {
  if (!events?.available) {
    $("#eventResult").innerHTML = `<p class="muted">${escapeHtml(events?.message || "행사 정보가 없습니다.")}</p>`;
    return;
  }
  if (!events.events?.length) {
    $("#eventResult").innerHTML = `<p class="muted">${escapeHtml(events.message || "선택 날짜에 확인된 행사가 없습니다.")}</p>`;
    return;
  }
  $("#eventResult").innerHTML = events.events.map((event) => `
    <div class="event-item"><strong>${escapeHtml(event.title)}</strong><small>${escapeHtml(event.address)}</small></div>`).join("")
    + `<p class="field-help">출처: ${escapeHtml(events.source)}</p>`;
}

function markdownSummary(result = state.result) {
  if (!result) return "";
  const lines = [
    `# ${result.title}`,
    "",
    `- 날짜: ${result.date}`,
    `- 지역: ${result.region.display_name}`,
    `- 법정동: ${result.region.legal_dong || "미제공"}`,
    `- 행정동: ${result.region.administrative_dong || "미제공"}`,
    "",
    result.summary,
    "",
    "## 일정",
    ...result.schedule.map((item) => `- ${item.time} ${item.place_name}: ${item.activity}`),
    "",
    "## 생활 장소",
    ...Object.entries(CATEGORY_META).map(([kind, meta]) => {
      const place = result.places[kind];
      return place ? `- ${meta.label}: ${place.name} (${place.address})` : `- ${meta.label}: 확인된 결과 없음`;
    }),
    "",
    "## 준비물",
    ...result.checklist.map((item) => `- ${item}`),
    "",
    "> 영업시간·가격·주차 가능 여부는 방문 전에 지도와 업체에 다시 확인하세요.",
  ];
  return lines.join("\n");
}

function renderSummary(result) {
  $("#summaryCard").innerHTML = `
    <p class="eyebrow">SAVED PLAN</p><h3>${escapeHtml(result.title)}</h3>
    <p><strong>${escapeHtml(result.date)}</strong> · ${escapeHtml(result.region.display_name)}</p>
    <p>${escapeHtml(result.summary)}</p>
    <h4>준비물</h4><ul>${result.checklist.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
  ["#copyButton", "#downloadButton", "#printButton", "#regenerateAllButton"].forEach((selector) => { $(selector).disabled = false; });
}

function safeHistoryResult(result) {
  return {
    title: result.title,
    summary: result.summary,
    schedule: result.schedule,
    places: result.places,
    weather: result.weather,
    events: result.events,
    weather_tip: result.weather_tip,
    checklist: result.checklist,
    region: result.region,
    date: result.date,
    generated_at: result.generated_at,
  };
}

function autoSaveHistory() {
  if (!state.result) return;
  const history = readJsonStorage(STORAGE_KEYS.history, []);
  const item = safeHistoryResult(state.result);
  const unique = history.filter((old) => !(old.date === item.date && old.region?.display_name === item.region.display_name));
  localStorage.setItem(STORAGE_KEYS.history, JSON.stringify([item, ...unique].slice(0, 5)));
  renderHistory();
}

function renderHistory() {
  const history = readJsonStorage(STORAGE_KEYS.history, []);
  if (!history.length) {
    $("#historyList").innerHTML = '<p class="muted">저장된 여행이 없습니다.</p>';
    return;
  }
  $("#historyList").innerHTML = history.map((item, index) => `
    <button class="history-item" type="button" data-history-index="${index}">
      <strong>${escapeHtml(item.region?.display_name || "지역 미상")}</strong>
      <small>${escapeHtml(item.date)} · ${escapeHtml(item.title)}</small>
    </button>`).join("");
  $$('[data-history-index]').forEach((button) => button.addEventListener("click", () => {
    const picked = history[Number(button.dataset.historyIndex)];
    state.result = picked;
    renderPlan(picked); renderPlaces(); renderWeather(picked.weather, picked.weather_tip); renderEvents(picked.events); renderSummary(picked);
    $("#plan").scrollIntoView({ behavior: "smooth" });
  }));
}

function updateMetrics(delta = {}) {
  const metrics = readJsonStorage(STORAGE_KEYS.metrics, { visits: 0, plans: 0, regenerations: 0, lastLatencyMs: 0 });
  Object.entries(delta).forEach(([key, value]) => { metrics[key] = (metrics[key] || 0) + value; });
  localStorage.setItem(STORAGE_KEYS.metrics, JSON.stringify(metrics));
  renderMetrics();
}

function renderMetrics() {
  const metrics = readJsonStorage(STORAGE_KEYS.metrics, { visits: 0, plans: 0, regenerations: 0, lastLatencyMs: 0 });
  $("#localMetrics").innerHTML = `<strong>이 브라우저의 사용 기록</strong><br />방문 ${metrics.visits}회 · 계획 ${metrics.plans}회 · 재추천 ${metrics.regenerations}회 · 최근 응답 ${metrics.lastLatencyMs || "-"}ms`;
}

async function generateTrip({ regenerateAll = false } = {}) {
  if (!state.selectedRegion) {
    showStatus("먼저 지역을 확인해 주세요.", "error");
    return;
  }
  let conditions;
  try {
    conditions = validateBasicConditions();
  } catch (error) {
    showStatus(error.message, "error");
    return;
  }
  const excluded = regenerateAll && state.result
    ? Object.values(state.result.places).filter(Boolean).map((place) => place.id)
    : [];
  const started = performance.now();
  setLoading(true, regenerateAll ? "다른 후보를 AI가 다시 고르고 있어요…" : "검증된 장소로 하루를 설계하고 있어요…");
  try {
    const data = await apiFetch("/api/generate", {
      ...conditions,
      region: state.selectedRegion,
      excluded_place_ids: excluded,
    });
    state.result = data.result;
    Object.keys(CATEGORY_META).forEach((kind) => {
      state.placeIndexes[kind] = currentPlaceIndex(kind, data.result.places[kind]);
    });
    renderPlan(data.result);
    renderPlaces();
    renderWeather(data.result.weather, data.result.weather_tip);
    renderEvents(data.result.events);
    renderSummary(data.result);
    const elapsed = Math.round(performance.now() - started);
    const metrics = readJsonStorage(STORAGE_KEYS.metrics, { visits: 1, plans: 0, regenerations: 0, lastLatencyMs: 0 });
    metrics.plans = (metrics.plans || 0) + 1;
    metrics.regenerations = (metrics.regenerations || 0) + (regenerateAll ? 1 : 0);
    metrics.lastLatencyMs = elapsed;
    localStorage.setItem(STORAGE_KEYS.metrics, JSON.stringify(metrics));
    renderMetrics();
    autoSaveHistory();
    showStatus(`여행 계획을 ${elapsed / 1000}초 만에 만들고 이 브라우저에 자동 저장했습니다.`);
    $("#plan").scrollIntoView({ behavior: "smooth" });
  } catch (error) {
    showStatus(error.message, "error");
  } finally {
    setLoading(false);
  }
}

async function copySummary() {
  try {
    await navigator.clipboard.writeText(markdownSummary());
    showStatus("여행 요약을 클립보드에 복사했습니다.");
  } catch {
    showStatus("복사 권한을 사용할 수 없습니다. Markdown 저장 버튼을 이용해 주세요.", "error");
  }
}

function downloadSummary() {
  const blob = new Blob([markdownSummary()], { type: "text/markdown;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `오늘어디로-${state.result.date}.md`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function resetApp() {
  state.selectedRegion = null;
  state.result = null;
  state.accuracy = null;
  $("#selectedRegion").className = "selected-region";
  $("#selectedRegion").innerHTML = '<span class="status-dot"></span><div><strong>아직 확인된 지역이 없습니다.</strong><small>위 방법 중 하나를 선택해 주세요.</small></div>';
  $("#suggestionGrid").innerHTML = "";
  $("#planEmpty").hidden = false;
  $("#planResult").hidden = true;
  $("#placeGrid").innerHTML = Object.values(CATEGORY_META).map((meta) => `<article class="place-card placeholder"><span>${meta.tag}</span><h3>${meta.label}</h3><p>여행을 만들면 실제 검색 결과가 표시됩니다.</p></article>`).join("");
  $("#weatherResult").innerHTML = '<p class="muted">아직 날씨를 확인하지 않았습니다.</p>';
  $("#eventResult").innerHTML = '<p class="muted">아직 행사를 확인하지 않았습니다.</p>';
  $("#summaryCard").innerHTML = '<p class="muted">AI 여행을 만들면 복사·저장·인쇄할 수 있습니다.</p>';
  ["#generateButton", "#copyButton", "#downloadButton", "#printButton", "#regenerateAllButton"].forEach((selector) => { $(selector).disabled = true; });
  hideStatus();
  $("#setup").scrollIntoView({ behavior: "smooth" });
}

function initializeTheme() {
  const saved = localStorage.getItem(STORAGE_KEYS.theme);
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.body.classList.toggle("dark", saved ? saved === "dark" : prefersDark);
  updateThemeLabel();
}

function updateThemeLabel() {
  const dark = document.body.classList.contains("dark");
  $("#themeToggle").setAttribute("aria-label", dark ? "라이트 모드 켜기" : "다크 모드 켜기");
}

function initialize() {
  const today = new Date();
  const localDate = new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  $("#tripDate").min = localDate;
  $("#tripDate").value = localDate;
  initializeTheme();
  updateMetrics({ visits: 1 });
  renderHistory();

  $$('input[name="locationMode"]').forEach((radio) => radio.addEventListener("change", () => switchLocationMode(radio.value)));
  $("#verifyRegionButton").addEventListener("click", verifyManualRegion);
  $("#regionQuery").addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); verifyManualRegion(); } });
  $("#currentLocationButton").addEventListener("click", useCurrentLocation);
  $("#recommendRegionsButton").addEventListener("click", requestRegionSuggestions);
  $("#tripForm").addEventListener("submit", (event) => { event.preventDefault(); generateTrip(); });
  $("#regenerateAllButton").addEventListener("click", () => generateTrip({ regenerateAll: true }));
  $("#copyButton").addEventListener("click", copySummary);
  $("#downloadButton").addEventListener("click", downloadSummary);
  $("#printButton").addEventListener("click", () => window.print());
  $("#resetButton").addEventListener("click", resetApp);
  $("#clearHistoryButton").addEventListener("click", () => { localStorage.removeItem(STORAGE_KEYS.history); renderHistory(); });
  $("#themeToggle").addEventListener("click", () => {
    document.body.classList.toggle("dark");
    localStorage.setItem(STORAGE_KEYS.theme, document.body.classList.contains("dark") ? "dark" : "light");
    updateThemeLabel();
  });
}

document.addEventListener("DOMContentLoaded", initialize);

