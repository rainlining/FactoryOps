const $ = id => document.getElementById(id);
const clean = value => String(value ?? "暂无").replaceAll("**", "").replaceAll("### ", "").replaceAll("## ", "").replaceAll("# ", "").replaceAll("`", "");
const demoSnapshot = {
  run: {run_id: "RUN-2026-0817-0007", status: "SUCCEEDED", incident_id: "QI-2026-0817-0042", revision: 5, completed_task_count: 3, task_count: 3},
  coordinator: {status: "SUCCEEDED", revision: 2, execution_id: "EXE-COORD-0007"},
  tasks: [
    {task_id: "TASK-Q-0007", target_agent_role: "quality", status: "SUCCEEDED", attempt_count: 1},
    {task_id: "TASK-P-0007", target_agent_role: "production", status: "SUCCEEDED", attempt_count: 1},
    {task_id: "TASK-S-0007", target_agent_role: "sla", status: "SUCCEEDED", attempt_count: 1},
  ],
  fusion: {proposed_action: "HOLD_BATCH", fusion_round: 1},
  risk: {decision: "REQUIRE_APPROVAL", proposed_action: "HOLD_BATCH"},
  approval: {status: "APPROVED", revision: 2, approval_key: "APR-2026-0817-0007"},
};

let batch = null;
let activeRequest = null;
let historyRecords = [];

function notice(message) {
  $("notice").textContent = message;
  $("notice").hidden = false;
  setTimeout(() => $("notice").hidden = true, 4500);
}

function details(id, rows) {
  $(id).replaceChildren(...rows.map(([key, value]) => {
    const row = document.createElement("div");
    row.className = "detail-row";
    row.innerHTML = '<span class="detail-key"></span><span class="detail-value"></span>';
    row.children[0].textContent = key;
    row.children[1].textContent = clean(value);
    return row;
  }));
}

function renderSnapshot(snapshot) {
  if (!snapshot?.run || !Array.isArray(snapshot.tasks)) throw new Error("快照必须包含 run 和 tasks");
  const {run, tasks} = snapshot;
  $("runId").textContent = clean(run.run_id);
  $("incidentLine").textContent = `质量事件 · ${clean(run.incident_id)}`;
  $("runStatus").textContent = clean(run.status);
  $("runStatus").className = `run-status ${clean(run.status).toLowerCase()}`;
  $("runRevision").textContent = clean(run.revision);
  $("taskProgress").textContent = `${run.completed_task_count ?? 0}/${run.task_count ?? tasks.length}`;
  $("taskProgressNote").textContent = `${tasks.length} 个专家任务`;
  $("coordinatorStatus").textContent = clean(snapshot.coordinator?.status);
  $("approvalStatus").textContent = clean(snapshot.approval?.status);
  $("approvalNote").textContent = snapshot.approval?.revision ? `版本 ${snapshot.approval.revision}` : "审批关卡";
  $("taskCount").textContent = `${tasks.length} 个任务`;
  $("taskRows").replaceChildren(...tasks.map(task => {
    const row = document.createElement("tr");
    row.innerHTML = '<td class="task-id"></td><td class="role"></td><td><span class="status-pill"></span></td><td></td>';
    row.children[0].textContent = clean(task.task_id);
    row.children[1].textContent = clean(task.target_agent_role);
    row.children[2].firstChild.textContent = clean(task.status);
    row.children[2].firstChild.className = `status-pill ${clean(task.status).toLowerCase()}`;
    row.children[3].textContent = clean(task.attempt_count);
    return row;
  }));
  const chain = [["协调器", snapshot.coordinator?.status], ["融合决策", snapshot.fusion?.proposed_action], ["风险检查", snapshot.risk?.decision], ["人工审批", snapshot.approval?.status]];
  $("decisionChain").replaceChildren(...chain.map(([label, value], index) => {
    const item = document.createElement("div");
    item.className = "chain-item";
    item.innerHTML = `<span class="chain-mark">${index + 1}</span><div><div class="chain-label"></div><div class="chain-value">生命周期状态</div></div><span class="status-pill"></span>`;
    item.querySelector(".chain-label").textContent = label;
    item.querySelector(".status-pill").textContent = clean(value);
    return item;
  }));
  details("approvalDetails", [["审批编号", snapshot.approval?.approval_key], ["状态", snapshot.approval?.status], ["版本", snapshot.approval?.revision], ["动作", snapshot.risk?.proposed_action]]);
  details("coordinatorDetails", [["执行编号", snapshot.coordinator?.execution_id], ["状态", snapshot.coordinator?.status], ["版本", snapshot.coordinator?.revision], ["融合轮次", snapshot.fusion?.fusion_round]]);
}

async function loadInitialSnapshot() {
  try {
    const response = await fetch("/api/snapshot", {cache: "no-store"});
    if (!response.ok) throw new Error();
    renderSnapshot(await response.json());
    $("updatedAt").textContent = "实时快照 · API";
  } catch {
    renderSnapshot(demoSnapshot);
    $("updatedAt").textContent = "演示快照 · API 不可用";
  }
}

function switchView(view) {
  const sections = [...document.querySelector(".main-content").children].filter(element => !element.classList.contains("topbar") && !element.classList.contains("notice"));
  sections.forEach(element => { element.hidden = view === "library" ? element.id !== "imageLibrary" : element.id === "imageLibrary"; });
  $("workflowNav").classList.toggle("active", view === "workflow");
  $("productLibraryNav").classList.toggle("active", view === "library");
  document.querySelector(".topbar h1").textContent = view === "library" ? "产品库" : "运行总览";
}

function fileData(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({name: file.name, data: String(reader.result).split(",")[1]});
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function resultCards(record) {
  if (record.items?.length > 1) {
    return `<article class="agent-card batch-summary"><h4>批次诊断结果</h4><p>本次共完成 ${record.item_count} 个产品。以下均为该次运行保存的结果。</p></article>` + record.items.map((item, index) =>
      `<article class="agent-card"><h4>${index + 1}. ${clean(item.image)}</h4><p><b>视觉检测</b>\n${clean(item.vision)}\n\n<b>协调结论</b>\n${clean(item.coordinator)}\n\n<b>风险判断</b>\n${clean(item.risk)}</p></article>`).join("");
  }
  return `<article class="agent-card"><h4>Vision Service</h4><p>${clean(record.vision)}</p></article>` +
    Object.entries(record.specialists || {}).map(([role, value]) => `<article class="agent-card"><h4>${clean(role)} Agent</h4><p>${clean(value)}</p></article>`).join("") +
    `<article class="agent-card"><h4>Incident Coordinator</h4><p>${clean(record.coordinator)}</p></article>` +
    `<article class="agent-card"><h4>Risk / Policy Agent</h4><p>${clean(record.risk)}</p></article>`;
}

function showStoredRun(record) {
  $("runState").textContent = `历史记录：${record.run_id}（仅查看，不调用模型）`;
  $("agentOutput").innerHTML = resultCards(record);
  $("tracePanel").innerHTML = `<strong>历史 Trace</strong><p>${(record.trace || []).map(clean).join(" → ")}</p>`;
}

function renderHistory() {
  $("historyCount").textContent = `${historyRecords.length} 次运行`;
  $("deleteHistory").disabled = !historyRecords.length;
  if (!historyRecords.length) {
    $("historyList").innerHTML = "<p>暂无运行记录。</p>";
    return;
  }
  $("historyList").replaceChildren(...historyRecords.map(record => {
    const row = document.createElement("div");
    const text = document.createElement("div");
    const checkbox = document.createElement("input");
    const title = document.createElement("strong");
    const meta = document.createElement("small");
    const button = document.createElement("button");
    row.className = "history-row";
    checkbox.type = "checkbox";
    checkbox.className = "history-select";
    checkbox.value = record.run_id;
    title.textContent = record.run_id;
    meta.textContent = `${new Date(record.created_at).toLocaleString()} · ${record.product_id} · ${record.batch_id} · ${record.item_count || 1} 个产品`;
    button.className = "load-button";
    button.type = "button";
    button.textContent = "查看记录";
    button.addEventListener("click", () => showStoredRun(record));
    text.append(title, meta);
    row.prepend(checkbox);
    row.append(text, button);
    return row;
  }));
}

function setHistory(records) {
  historyRecords = [...records].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  renderHistory();
}

function addHistory(record) {
  setHistory([record, ...historyRecords.filter(item => item.run_id !== record.run_id)]);
}

async function refreshHistory() {
  const response = await fetch("/api/history", {cache: "no-store"});
  if (!response.ok) throw new Error(`历史接口返回 ${response.status}`);
  const data = await response.json();
  setHistory(Array.isArray(data.runs) ? data.runs : []);
}

async function runBatch() {
  if (!batch?.files.length || activeRequest) {
    if (!batch?.files.length) $("runState").textContent = "请先在产品库选择一个批次文件夹";
    return;
  }
  const controller = new AbortController();
  activeRequest = controller;
  $("startPipeline").disabled = true;
  $("cancelPipeline").hidden = false;
  $("retryPipeline").hidden = true;
  $("runState").textContent = `正在处理批次 ${batch.name}，共 ${batch.files.length} 张`;
  $("agentOutput").innerHTML = `<article class="agent-card"><h4>批次处理中</h4><p>正在逐张分析 ${batch.files.length} 个产品。完成前不会显示旧的 Agent 输出。</p></article>`;
  $("tracePanel").replaceChildren();
  try {
    const images = await Promise.all(batch.files.map(fileData));
    const response = await fetch("/api/run", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({images}), signal: controller.signal});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Agent 调用失败");
    $("runState").textContent = `批次完成：${result.item_count || 1} 个产品 · ${result.run_id}`;
    $("agentOutput").innerHTML = resultCards(result);
    $("tracePanel").innerHTML = `<strong>Trace</strong><p>${(result.trace || []).map(clean).join(" → ")}</p>`;
    addHistory(result);
    try { await refreshHistory(); } catch (error) { notice(`结果已显示，但历史同步失败：${error.message}`); }
  } catch (error) {
    if (error.name === "AbortError") {
      $("runState").textContent = "检测已取消";
      $("agentOutput").innerHTML = '<article class="agent-card"><h4>检测已取消</h4><p>本次未完成，不会写入历史记录。</p></article>';
    } else {
      $("runState").textContent = "批次检测失败，可点击重试";
      $("agentOutput").innerHTML = `<article class="agent-card"><h4>真实运行失败</h4><p>${clean(error.message)}</p></article>`;
      $("retryPipeline").hidden = false;
    }
  } finally {
    if (activeRequest === controller) activeRequest = null;
    $("startPipeline").disabled = false;
    $("cancelPipeline").hidden = true;
  }
}

$("batchFolder").addEventListener("change", event => {
  const files = [...event.target.files].filter(file => file.type.startsWith("image/"));
  const name = files[0]?.webkitRelativePath?.split("/")[0] || "未命名批次";
  batch = files.length ? {name, files} : null;
  $("selectionCount").textContent = files.length ? `已导入 ${files.length} 张` : "未导入批次";
  $("imageGrid").replaceChildren(...(files.length ? files.map((file, index) => {
    const card = document.createElement("label");
    card.className = "image-card";
    card.innerHTML = `<input type="checkbox" checked disabled><img><strong>${clean(file.name)}</strong><small>产品 ${index + 1} · 批次 ${clean(name)}</small>`;
    card.querySelector("img").src = URL.createObjectURL(file);
    card.querySelector("img").alt = file.name;
    return card;
  }) : [Object.assign(document.createElement("p"), {textContent: "未找到图片。"})]));
  $("runState").textContent = files.length ? `已导入批次 ${name}，共 ${files.length} 张产品图片` : "请选择包含产品图片的批次文件夹";
});

$("startPipeline").addEventListener("click", runBatch);
$("retryPipeline").addEventListener("click", runBatch);
$("replayRun").addEventListener("click", runBatch);
$("cancelPipeline").addEventListener("click", () => activeRequest?.abort());
$("deleteHistory").addEventListener("click", async () => {
  const runIds = [...document.querySelectorAll(".history-select:checked")].map(input => input.value);
  if (!runIds.length) return;
  const response = await fetch("/api/history/delete", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({run_ids: runIds})});
  if (!response.ok) { notice("删除历史记录失败"); return; }
  await refreshHistory();
  notice(`已删除 ${runIds.length} 条历史记录`);
});
$("approveAction").addEventListener("click", () => notice("审批动作已记录。此工作台不会直接修改生产系统。"));
$("workflowNav").addEventListener("click", () => switchView("workflow"));
$("productLibraryNav").addEventListener("click", () => switchView("library"));
$("loadButton").addEventListener("click", () => $("snapshotInput").click());
$("loadNav").addEventListener("click", () => $("snapshotInput").click());
$("snapshotInput").addEventListener("change", event => {
  const reader = new FileReader();
  reader.onload = () => { try { renderSnapshot(JSON.parse(reader.result)); } catch (error) { notice(error.message); } };
  if (event.target.files[0]) reader.readAsText(event.target.files[0]);
});
$("menuButton").addEventListener("click", () => $("sidebar").classList.toggle("open"));

switchView("workflow");
loadInitialSnapshot();
refreshHistory().catch(error => notice(`无法读取历史记录：${error.message}`));
