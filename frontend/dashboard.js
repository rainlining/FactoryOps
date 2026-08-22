const $ = id => document.getElementById(id);
const clean = value => String(value ?? "暂无").replaceAll("**", "").replaceAll("`", "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
let batch = null;
let currentRun = null;
let polling = null;
let startedAt = null;
let historyRecords = [];
let queueRecords = [];
let queuePolling = null;

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

function groupBatchFiles(files) {
  const groups = new Map(); let rootName = "factoryops"; let ignored = 0;
  for (const file of files) {
    const parts = String(file.webkitRelativePath || file.name).split("/").filter(Boolean);
    if (parts.length !== 3 || !file.type.startsWith("image/")) { ignored += 1; continue; }
    rootName = parts[0];
    if (!groups.has(parts[1])) groups.set(parts[1], []);
    groups.get(parts[1]).push(file);
  }
  return {rootName, ignored, batches: [...groups].map(([displayName, batchFiles]) => ({displayName, files: batchFiles}))};
}

async function sha256(value) {
  const bytes = typeof value === "string" ? new TextEncoder().encode(value) : value;
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map(part => part.toString(16).padStart(2, "0")).join("");
}

async function buildBatchManifest(candidate) {
  const entries = [];
  for (const file of candidate.files) entries.push({file, relative_path:file.webkitRelativePath, size:file.size, sha256:await sha256(await file.arrayBuffer())});
  entries.sort((a,b)=>a.relative_path.localeCompare(b.relative_path));
  const images = await Promise.all(entries.map(async entry=>({...await fileData(entry.file),relative_path:entry.relative_path,size:entry.size,sha256:entry.sha256})));
  return {batch_id:candidate.displayName.replace(/[^a-zA-Z0-9._-]/g,"-")||"batch",display_name:candidate.displayName,manifest_digest:await sha256(entries.map(entry=>`${entry.relative_path}:${entry.size}:${entry.sha256}`).join("\n")),images};
}

const queueStatusNames={QUEUED:"待检测",STARTING:"正在启动",RUNNING:"检测中",QA_ACCEPTED:"质检通过",RECHECK_REQUIRED:"待复检",WAITING_FOR_APPROVAL:"待审批",FAILED:"失败",CANCELLED:"已取消"};
function renderQueue(queue){
  queueRecords=queue.items||[];const summary=queue.summary||{};
  $("queueSummary").textContent=`${queue.root_name||"未选择目录"} · ${summary.total||0} 个批次 · 通过 ${summary.QA_ACCEPTED||0} · 待审批 ${summary.WAITING_FOR_APPROVAL||0} · 失败 ${summary.FAILED||0}`;
  $("startQueue").disabled=!queueRecords.some(item=>item.status==="QUEUED");$("pauseQueue").disabled=queue.status!=="RUNNING";
  $("queueList").replaceChildren(...(queueRecords.length?queueRecords.map(item=>{const row=document.createElement("article");row.className="queue-row";row.innerHTML='<div><strong></strong><small></small></div><span></span><span></span><span class="queue-state"></span><div class="top-actions"></div>';row.querySelector("strong").textContent=item.display_name;row.querySelector("small").textContent=`revision ${item.revision}${item.run_id?` · ${item.run_id}`:""}`;const spans=row.querySelectorAll(":scope > span");spans[0].textContent=`${item.image_count} 张`;spans[1].textContent=item.outcome||"—";spans[2].textContent=queueStatusNames[item.status]||item.status;spans[2].classList.add(item.status.toLowerCase());const actions=row.querySelector(".top-actions");if(item.run_id){const view=document.createElement("button");view.className="secondary-button";view.textContent="查看";view.onclick=()=>showQueueRun(item.run_id);actions.append(view)}if(["FAILED","CANCELLED"].includes(item.status)){const retry=document.createElement("button");retry.className="secondary-button";retry.textContent="重试";retry.onclick=()=>queueAction(item.item_id,"retry");actions.append(retry)}if(["QUEUED","RUNNING","STARTING"].includes(item.status)){const cancel=document.createElement("button");cancel.className="secondary-button";cancel.textContent="取消";cancel.onclick=()=>queueAction(item.item_id,"cancel");actions.append(cancel)}return row}):[Object.assign(document.createElement("p"),{className:"empty",textContent:"队列为空。"})]));
}
async function refreshQueue(){const response=await fetch("/api/batch-queues/current",{cache:"no-store"});if(!response.ok)throw new Error("无法读取批次队列");const queue=await response.json();renderQueue(queue);const active=queueRecords.find(item=>["STARTING","RUNNING"].includes(item.status)&&item.run_id);if(active)await showQueueRun(active.run_id,false);return queue}
async function showQueueRun(runId,switchToWorkflow=true){const response=await fetch(`/api/runs/${runId}`,{cache:"no-store"});if(!response.ok)return;const run=await response.json();currentRun=run;renderProgress(run);if(run.result)showResult(run.result,run.progress_events||[]);if(switchToWorkflow)switchView("workflow")}
async function queueAction(itemId,action){const response=await fetch(`/api/batch-queue-items/${itemId}/${action}`,{method:"POST"});if(!response.ok)notice("当前批次无法执行该操作");await refreshQueue()}

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
    const duration = roleEvents.length > 1 ? Math.max(0, (new Date(latest.occurred_at) - new Date(roleEvents[0].occurred_at)) / 1000).toFixed(1) : null;
    node.className = `agent-node ${latest?.status?.toLowerCase() || "pending"}`;
    node.querySelector("small").textContent = latest ? `${latest.summary}${duration ? ` · ${duration}s` : ""}` : node.querySelector("small").dataset.initial || "等待上游证据";
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
    $("startPipeline").textContent = "重新检测当前批次";
    $("cancelPipeline").hidden = true;
    await refreshHistory();
  } else if (run.status === "FAILED") {
    clearInterval(polling); polling = null;
    $("runState").textContent = `运行失败：${run.progress_events.at(-1)?.summary || "未知错误"}`;
    $("startPipeline").disabled = false;
    $("startPipeline").textContent = "重试整个批次";
    $("cancelPipeline").hidden = true;
  } else if (run.status === "CANCELLED") {
    clearInterval(polling); polling = null;
    $("runState").textContent = "批次检测已取消；已完成事件仍保留在历史中";
    $("startPipeline").disabled = false;
    $("cancelPipeline").hidden = true;
    await refreshHistory();
  }
}

async function runBatch() {
  if (!batch?.files.length || polling) { if (!batch) notice("请先从产品库导入一个批次"); return; }
  $("startPipeline").disabled = true;
  $("cancelPipeline").hidden = false;
  $("agentOutput").innerHTML = '<p class="empty">批次正在运行，最终结论将在所有 Agent 完成协作后显示。</p>';
  $("tracePanel").innerHTML = "<p>正在等待第一条真实运行事件……</p>";
  const images = await Promise.all(batch.files.map(fileData));
  const retryOf = currentRun?.status === "FAILED" ? currentRun.run_id : null;
  const response = await fetch("/api/runs", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({batch_id: batch.name, images, retry_of: retryOf})});
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
  const grouped=groupBatchFiles([...event.target.files]);
  $("selectionCount").textContent=`${grouped.batches.length} 个批次`;
  $("imageGrid").replaceChildren(...grouped.batches.flatMap(candidate=>candidate.files.map((file,index)=>{
    const card = document.createElement("article"); card.className = "image-card";
    card.innerHTML = `<img><strong>${clean(file.name)}</strong><small>产品 ${index + 1} · ${clean(candidate.displayName)}</small>`;
    card.querySelector("img").src = URL.createObjectURL(file); card.querySelector("img").alt = file.name; return card;
  })));
  Promise.all(grouped.batches.map(buildBatchManifest)).then(async batches=>{const response=await fetch("/api/batch-queues/scan",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({root_name:grouped.rootName,batches})});const data=await response.json();if(!response.ok)throw new Error(data.error);renderQueue(data);notice(`已导入 ${batches.length} 个批次，忽略 ${grouped.ignored} 个文件；尚未调用模型`);switchView("workflow")}).catch(error=>notice(error.message));
});

$("startQueue").addEventListener("click",async()=>{const response=await fetch("/api/batch-queues/current/start",{method:"POST"});if(!response.ok){notice("没有可启动的批次");return}if(!queuePolling)queuePolling=setInterval(()=>refreshQueue().catch(error=>notice(error.message)),900);await refreshQueue()});
$("pauseQueue").addEventListener("click",async()=>{await fetch("/api/batch-queues/current/pause",{method:"POST"});await refreshQueue();notice("已暂停派发；正在运行的批次会继续完成")});

$("startPipeline").addEventListener("click", () => runBatch().catch(error => notice(error.message)));
$("cancelPipeline").addEventListener("click", async () => {
  if (!currentRun?.run_id) return;
  const response = await fetch(`/api/runs/${currentRun.run_id}/cancel`, {method: "POST"});
  notice(response.ok ? "取消请求已发送；当前 Agent 调用结束后停止" : "当前运行已无法取消");
});
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
refreshQueue().catch(error => notice(error.message));
