const $ = id => document.getElementById(id);
const clean = value => String(value ?? "暂无").replaceAll("**", "").replaceAll("`", "");
let batch = null;
let currentRun = null;
let polling = null;
let startedAt = null;
let historyRecords = [];

function notice(message) {
  $("notice").textContent = message;
  $("notice").hidden = false;
  setTimeout(() => $("notice").hidden = true, 4500);
}

function switchView(view) {
  const library = view === "library";
  $("imageLibrary").hidden = !library;
  $("workflowView").hidden = library;
  $("workflowNav").classList.toggle("active", !library);
  $("productLibraryNav").classList.toggle("active", library);
  $("pageTitle").textContent = library ? "产品库" : "批次质量作战室";
}

function fileData(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({name: file.name, data: String(reader.result).split(",")[1]});
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function stageProgress(events, productCount) {
  const succeeded = (stage, role) => events.filter(event => event.stage === stage && event.status === "SUCCEEDED" && (!role || event.agent_role === role));
  if (events.some(event => event.stage === "COMPLETED" && event.status === "SUCCEEDED")) return 100;
  let value = succeeded("INGEST").length ? 5 : 0;
  value += 40 * ((succeeded("VISION").at(-1)?.completed_units || 0) / Math.max(productCount, 1));
  const specialistUnits = ["quality", "production", "sla"].reduce((sum, role) => sum + (succeeded("SPECIALISTS", role).at(-1)?.completed_units || 0), 0);
  value += 35 * (specialistUnits / Math.max(productCount * 3, 1));
  value += succeeded("COORDINATOR").length ? 10 : 0;
  value += succeeded("RISK").length ? 10 : 0;
  return Math.min(100, Math.round(value));
}

const stageNames = {INGEST: "读取批次", VISION: "Vision 逐张检测", SPECIALISTS: "专家并行分析", COORDINATOR: "Coordinator 批次汇总", RISK: "Risk 风险审查", COMPLETED: "批次完成"};

function renderProgress(run) {
  const events = run.progress_events || [];
  const latest = events.at(-1);
  const percent = stageProgress(events, run.product_count);
  $("batchProgress").style.width = `${percent}%`;
  $("batchProgress").parentElement.setAttribute("aria-valuenow", percent);
  $("progressPercent").textContent = `${percent}%`;
  $("progressLabel").textContent = latest ? `${stageNames[latest.stage] || latest.stage} · ${latest.summary}` : "等待运行事件";
  $("progressUnits").textContent = latest ? `${latest.completed_units} / ${latest.total_units}` : `0 / ${run.product_count}`;
  $("lastActivity").textContent = latest ? `最近活动 ${new Date(latest.occurred_at).toLocaleTimeString()}` : "尚无运行事件";
  $("runState").textContent = `${run.run_id} · ${run.status}`;
  $("batchName").textContent = `${run.batch_id} · ${run.product_count} 个产品`;
  renderTopology(events);
}

function renderTopology(events) {
  for (const node of document.querySelectorAll(".agent-node")) {
    const role = node.dataset.role;
    const roleEvents = events.filter(event => event.agent_role === role);
    const latest = roleEvents.at(-1);
    node.className = `agent-node ${latest?.status?.toLowerCase() || "pending"}`;
    node.querySelector("small").textContent = latest?.summary || node.querySelector("small").dataset.initial || "等待上游证据";
    if (!node.querySelector("small").dataset.initial) node.querySelector("small").dataset.initial = node.querySelector("small").textContent;
  }
}

function resultHtml(record) {
  const items = record.items || [];
  return `<div class="batch-verdict"><div><span>检测产品</span><strong>${record.item_count || items.length}</strong></div><div><span>传输方式</span><strong>${record.transport?.kafka_used ? "Kafka" : "本地 HTTP"}</strong></div></div>` +
    `<article class="verdict-card"><span>COORDINATOR · 批次结论</span><p>${clean(record.coordinator)}</p></article>` +
    `<article class="verdict-card risk"><span>RISK / POLICY · 批次风险</span><p>${clean(record.risk)}</p></article>`;
}

function evidenceHtml(record, events) {
  const items = record.items || [];
  return `<p><b>运行来源：</b>${record.transport?.kafka_used ? "真实 Kafka 事件" : "本次本地运行未经过 Kafka"}</p>` +
    `<p><b>Trace：</b>${(record.trace || []).map(clean).join(" → ")}</p>` +
    `<h4>产品证据</h4>${items.map((item, index) => `<details class="evidence-item"><summary>${index + 1}. ${clean(item.image)}</summary><p><b>Vision</b>\n${clean(item.vision)}</p>${Object.entries(item.specialists || {}).map(([role, value]) => `<p><b>${role}</b>\n${clean(value)}</p>`).join("")}</details>`).join("")}` +
    `<h4>运行事件</h4><ol class="event-list">${events.map(event => `<li><time>${new Date(event.occurred_at).toLocaleTimeString()}</time><b>${clean(event.agent_role)}</b>${clean(event.summary)}</li>`).join("")}</ol>`;
}

function showResult(result, events) {
  $("batchConclusion").querySelector("h3").textContent = `${result.batch_id} 批次审查完成`;
  $("batchConclusion").querySelector(".status-pill").textContent = "已形成批次结论";
  $("agentOutput").innerHTML = resultHtml(result);
  $("tracePanel").innerHTML = evidenceHtml(result, events);
  $("transportBadge").textContent = result.transport?.kafka_used ? "Kafka 事件运行" : "本次本地运行未经过 Kafka";
}

async function pollRun(runId) {
  const after = currentRun?.progress_events?.at(-1)?.sequence || 0;
  const response = await fetch(`/api/runs/${runId}/events?after=${after}`, {cache: "no-store"});
  if (!response.ok) throw new Error("无法读取运行状态");
  const update = await response.json();
  let run = {...currentRun, status: update.status, progress_events: [...(currentRun?.progress_events || []), ...(update.events || [])]};
  if (["SUCCEEDED", "FAILED", "CANCELLED"].includes(update.status)) {
    const detailResponse = await fetch(`/api/runs/${runId}`, {cache: "no-store"});
    run = await detailResponse.json();
  }
  currentRun = run;
  renderProgress(run);
  if (run.status === "SUCCEEDED") {
    clearInterval(polling); polling = null;
    showResult(run.result, run.progress_events);
    $("startPipeline").disabled = false;
    $("cancelPipeline").hidden = true;
    await refreshHistory();
  } else if (run.status === "FAILED") {
    clearInterval(polling); polling = null;
    $("runState").textContent = `运行失败：${run.progress_events.at(-1)?.summary || "未知错误"}`;
    $("startPipeline").disabled = false;
    $("cancelPipeline").hidden = true;
  }
}

async function runBatch() {
  if (!batch?.files.length || polling) { if (!batch) notice("请先从产品库导入一个批次"); return; }
  $("startPipeline").disabled = true;
  $("cancelPipeline").hidden = false;
  $("agentOutput").innerHTML = '<p class="empty">批次正在运行，最终结论将在所有 Agent 完成协作后显示。</p>';
  $("tracePanel").innerHTML = "<p>正在等待第一条真实运行事件……</p>";
  const images = await Promise.all(batch.files.map(fileData));
  const response = await fetch("/api/runs", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({batch_id: batch.name, images})});
  const run = await response.json();
  if (!response.ok) { $("startPipeline").disabled = false; throw new Error(run.error); }
  startedAt = Date.now();
  currentRun = run;
  renderProgress(run);
  polling = setInterval(() => pollRun(run.run_id).catch(error => notice(error.message)), 700);
  await pollRun(run.run_id);
}

function showStoredRun(record) {
  const events = record.progress_events || [];
  $("batchName").textContent = `${record.batch_id} · ${record.item_count || 1} 个产品`;
  $("runState").textContent = `历史记录 ${record.run_id} · 仅查看，不调用模型`;
  $("transportBadge").textContent = record.transport?.kafka_used ? "Kafka 事件运行" : "本次本地运行未经过 Kafka";
  showResult(record, events);
  if (events.length) renderProgress({batch_id: record.batch_id, product_count: record.item_count || 1, run_id: record.run_id, status: record.status || "SUCCEEDED", progress_events: events});
}

function renderHistory() {
  $("historyCount").textContent = `${historyRecords.length} 次运行`;
  $("deleteHistory").disabled = !historyRecords.length;
  $("historyList").replaceChildren(...(historyRecords.length ? historyRecords.map(record => {
    const row = document.createElement("div");
    row.className = "history-row";
    row.innerHTML = `<input class="history-select" type="checkbox"><div><strong></strong><small></small></div><button class="secondary-button" type="button">查看记录</button>`;
    row.querySelector("input").value = record.run_id;
    row.querySelector("strong").textContent = record.run_id;
    row.querySelector("small").textContent = `${new Date(record.created_at).toLocaleString()} · ${record.batch_id} · ${record.item_count || 1} 个产品`;
    row.querySelector("button").addEventListener("click", () => showStoredRun(record));
    return row;
  }) : [Object.assign(document.createElement("p"), {className: "empty", textContent: "暂无历史记录。"})]));
}

async function refreshHistory() {
  const response = await fetch("/api/history", {cache: "no-store"});
  const data = await response.json();
  historyRecords = data.runs || [];
  renderHistory();
}

$("batchFolder").addEventListener("change", event => {
  const files = [...event.target.files].filter(file => file.type.startsWith("image/"));
  const name = files[0]?.webkitRelativePath?.split("/")[0] || "未命名批次";
  batch = files.length ? {name, files} : null;
  $("selectionCount").textContent = `${files.length} 张`;
  $("imageGrid").replaceChildren(...files.map((file, index) => {
    const card = document.createElement("article"); card.className = "image-card";
    card.innerHTML = `<img><strong>${clean(file.name)}</strong><small>产品 ${index + 1} · ${clean(name)}</small>`;
    card.querySelector("img").src = URL.createObjectURL(file); card.querySelector("img").alt = file.name; return card;
  }));
  $("batchName").textContent = `${name} · ${files.length} 个产品`;
  $("runState").textContent = "批次已就绪，等待开始检测";
  switchView("workflow");
});

$("startPipeline").addEventListener("click", () => runBatch().catch(error => notice(error.message)));
$("cancelPipeline").addEventListener("click", () => notice("取消请求尚未得到服务端确认；当前 Run 将继续保留真实状态。"));
$("deleteHistory").addEventListener("click", async () => {
  const runIds = [...document.querySelectorAll(".history-select:checked")].map(input => input.value);
  if (!runIds.length) return;
  const response = await fetch("/api/history/delete", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({run_ids: runIds})});
  if (response.ok) await refreshHistory(); else notice("删除历史记录失败");
});
$("workflowNav").addEventListener("click", () => switchView("workflow"));
$("productLibraryNav").addEventListener("click", () => switchView("library"));
$("menuButton").addEventListener("click", () => $("sidebar").classList.toggle("open"));
setInterval(() => { if (startedAt && polling) $("elapsedTime").textContent = `已耗时 ${new Date(Date.now() - startedAt).toISOString().slice(14, 19)}`; }, 1000);
refreshHistory().catch(error => notice(error.message));
