from __future__ import annotations

import base64
import json
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "demo_runs.sqlite3"
LOCAL_CONFIG = {}
EVENT_LOCK = threading.Lock()
QUEUE_LOCK = threading.Lock()
QUEUE_WORKER = None


def load_local_config():
    config = ROOT / ".env.local"
    if not config.exists():
        return
    for line in config.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        cleaned = value.strip().strip('"').strip("'").strip()
        if key.strip().endswith("_API_URL"):
            cleaned = cleaned.rstrip("#").rstrip()
        # Project-local configuration must win over stale variables inherited by the server process.
        LOCAL_CONFIG[key.strip()] = cleaned
        os.environ[key.strip()] = cleaned


load_local_config()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS run_jobs (run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, batch_id TEXT NOT NULL, product_count INTEGER NOT NULL, status TEXT NOT NULL, result TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0)"
        )
        if "cancel_requested" not in {
            row[1] for row in db.execute("PRAGMA table_info(run_jobs)")
        }:
            db.execute(
                "ALTER TABLE run_jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0"
            )
        db.execute(
            "CREATE TABLE IF NOT EXISTS progress_events (run_id TEXT NOT NULL, sequence INTEGER NOT NULL, occurred_at TEXT NOT NULL, stage TEXT NOT NULL, agent_role TEXT NOT NULL, status TEXT NOT NULL, completed_units INTEGER NOT NULL, total_units INTEGER NOT NULL, product_ref TEXT, summary TEXT NOT NULL, PRIMARY KEY (run_id, sequence))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS batch_queue_control (id INTEGER PRIMARY KEY CHECK (id = 1), root_name TEXT NOT NULL, status TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS batch_queue_items (item_id INTEGER PRIMARY KEY AUTOINCREMENT, root_name TEXT NOT NULL, batch_id TEXT NOT NULL, display_name TEXT NOT NULL, revision INTEGER NOT NULL, manifest_digest TEXT NOT NULL, images TEXT NOT NULL, status TEXT NOT NULL, run_id TEXT, retry_of TEXT, outcome TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(root_name, batch_id, manifest_digest))"
        )


init_db()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def create_run(batch_id, product_count):
    run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    created_at = utc_now()
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "INSERT INTO run_jobs(run_id, created_at, updated_at, batch_id, product_count, status) VALUES (?, ?, ?, ?, ?, 'PENDING')",
            (run_id, created_at, created_at, batch_id, product_count),
        )
    return get_run(run_id)


def append_progress_event(
    run_id,
    stage,
    agent_role,
    status,
    completed_units,
    total_units,
    summary,
    product_ref=None,
):
    occurred_at = utc_now()
    with EVENT_LOCK, sqlite3.connect(DB_PATH) as db:
        sequence = db.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM progress_events WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO progress_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                sequence,
                occurred_at,
                stage,
                agent_role,
                status,
                completed_units,
                total_units,
                product_ref,
                summary,
            ),
        )
        db.execute(
            "UPDATE run_jobs SET status = ?, updated_at = ? WHERE run_id = ?",
            (
                "RUNNING"
                if status not in {"FAILED", "CANCELLED", "SUCCEEDED"}
                or stage != "COMPLETED"
                else status,
                occurred_at,
                run_id,
            ),
        )
    return {
        "sequence": sequence,
        "occurred_at": occurred_at,
        "stage": stage,
        "agent_role": agent_role,
        "status": status,
        "completed_units": completed_units,
        "total_units": total_units,
        "product_ref": product_ref,
        "summary": summary,
    }


def complete_run(run_id, result):
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "UPDATE run_jobs SET status = 'SUCCEEDED', updated_at = ?, result = ? WHERE run_id = ?",
            (utc_now(), json.dumps(result, ensure_ascii=False), run_id),
        )


def save_run_result(run_id, result, status="RUNNING"):
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "UPDATE run_jobs SET status = ?, updated_at = ?, result = ? WHERE run_id = ?",
            (status, utc_now(), json.dumps(result, ensure_ascii=False), run_id),
        )


def get_run(run_id):
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            "SELECT run_id, created_at, updated_at, batch_id, product_count, status, result FROM run_jobs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            return None
        events = db.execute(
            "SELECT sequence, occurred_at, stage, agent_role, status, completed_units, total_units, product_ref, summary FROM progress_events WHERE run_id = ? ORDER BY sequence",
            (run_id,),
        ).fetchall()
    return {
        "run_id": row[0],
        "created_at": row[1],
        "updated_at": row[2],
        "batch_id": row[3],
        "product_count": row[4],
        "status": row[5],
        "result": json.loads(row[6]) if row[6] else None,
        "transport": {"mode": "http-local", "kafka_used": False},
        "progress_events": [
            {
                "sequence": event[0],
                "occurred_at": event[1],
                "stage": event[2],
                "agent_role": event[3],
                "status": event[4],
                "completed_units": event[5],
                "total_units": event[6],
                "product_ref": event[7],
                "summary": event[8],
            }
            for event in events
        ],
    }


class RunCancelled(Exception):
    pass


def request_cancel(run_id):
    with sqlite3.connect(DB_PATH) as db:
        return (
            db.execute(
                "UPDATE run_jobs SET cancel_requested = 1, updated_at = ? WHERE run_id = ? AND status IN ('PENDING', 'RUNNING')",
                (utc_now(), run_id),
            ).rowcount
            == 1
        )


def ensure_not_cancelled(run_id):
    with sqlite3.connect(DB_PATH) as db:
        requested = db.execute(
            "SELECT cancel_requested FROM run_jobs WHERE run_id = ?", (run_id,)
        ).fetchone()
    if requested and requested[0]:
        raise RunCancelled()


def delete_runs(run_ids):
    deleted = 0
    with sqlite3.connect(DB_PATH) as db:
        for run_id in set(run_ids):
            if db.execute(
                "SELECT 1 FROM batch_queue_items WHERE run_id=?", (run_id,)
            ).fetchone():
                continue
            db.execute("DELETE FROM progress_events WHERE run_id = ?", (run_id,))
            deleted += db.execute(
                "DELETE FROM run_jobs WHERE run_id = ?", (run_id,)
            ).rowcount
            deleted += db.execute(
                "DELETE FROM runs WHERE run_id = ?", (run_id,)
            ).rowcount
    return deleted


def _queue_item(row):
    return {
        "item_id": row[0],
        "root_name": row[1],
        "batch_id": row[2],
        "display_name": row[3],
        "revision": row[4],
        "manifest_digest": row[5],
        "image_count": len(json.loads(row[6])),
        "status": row[7],
        "run_id": row[8],
        "retry_of": row[9],
        "outcome": row[10],
        "error": row[11],
        "created_at": row[12],
        "updated_at": row[13],
    }


def _select_queue_items(db, where="", params=()):
    return [
        _queue_item(row)
        for row in db.execute(
            "SELECT item_id, root_name, batch_id, display_name, revision, manifest_digest, images, status, run_id, retry_of, outcome, error, created_at, updated_at FROM batch_queue_items "
            + where
            + " ORDER BY item_id",
            params,
        ).fetchall()
    ]


def scan_batch_queue(root_name, batches):
    if not root_name or not isinstance(batches, list) or not batches:
        raise ValueError("根目录至少包含一个有效批次")
    affected = []
    now = utc_now()
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "INSERT INTO batch_queue_control(id, root_name, status, updated_at) VALUES (1, ?, 'PAUSED', ?) ON CONFLICT(id) DO UPDATE SET root_name=excluded.root_name, updated_at=excluded.updated_at",
            (root_name, now),
        )
        for batch in batches:
            images = batch.get("images") or []
            if (
                not batch.get("batch_id")
                or not batch.get("manifest_digest")
                or not images
            ):
                raise ValueError("批次必须包含身份、清单摘要和图片")
            existing = db.execute(
                "SELECT item_id FROM batch_queue_items WHERE root_name=? AND batch_id=? AND manifest_digest=?",
                (root_name, batch["batch_id"], batch["manifest_digest"]),
            ).fetchone()
            if existing:
                item_id = existing[0]
            else:
                revision = db.execute(
                    "SELECT COALESCE(MAX(revision), 0) + 1 FROM batch_queue_items WHERE root_name=? AND batch_id=?",
                    (root_name, batch["batch_id"]),
                ).fetchone()[0]
                item_id = db.execute(
                    "INSERT INTO batch_queue_items(root_name,batch_id,display_name,revision,manifest_digest,images,status,created_at,updated_at) VALUES (?,?,?,?,?,?,'QUEUED',?,?)",
                    (
                        root_name,
                        batch["batch_id"],
                        batch.get("display_name") or batch["batch_id"],
                        revision,
                        batch["manifest_digest"],
                        json.dumps(images, ensure_ascii=False),
                        now,
                        now,
                    ),
                ).lastrowid
            affected.extend(_select_queue_items(db, "WHERE item_id=?", (item_id,)))
    current = get_batch_queue()
    return {**current, "items": affected}


def get_batch_queue():
    with sqlite3.connect(DB_PATH) as db:
        control = db.execute(
            "SELECT root_name, status, updated_at FROM batch_queue_control WHERE id=1"
        ).fetchone()
        items = (
            _select_queue_items(db, "WHERE root_name=?", (control[0],))
            if control
            else []
        )
    counts = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {
        "root_name": control[0] if control else None,
        "status": control[1] if control else "EMPTY",
        "updated_at": control[2] if control else None,
        "summary": {"total": len(items), **counts},
        "items": items,
    }


def route_batch_outcome(result):
    decision = str(result.get("decision") or "").upper()
    approval = result.get("requires_human_approval")
    if not decision or not isinstance(approval, bool):
        return "FAILED"
    if approval is True or decision in {
        "HOLD_BATCH",
        "STOP_LINE",
    }:
        return "WAITING_FOR_APPROVAL"
    if decision == "RECHECK":
        return "RECHECK_REQUIRED"
    if decision in {"PASS", "NO_ACTION", "QA_ACCEPTED"} and approval is False:
        return "QA_ACCEPTED"
    return "FAILED"


def parse_risk_decision(value):
    if not isinstance(value, str):
        return None
    text = (
        value.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    required = {"decision", "requires_human_approval", "risk_level", "policy_refs"}
    if not isinstance(parsed, dict) or not required.issubset(parsed):
        return None
    if not isinstance(parsed["requires_human_approval"], bool) or not isinstance(
        parsed["policy_refs"], list
    ):
        return None
    return parsed


def cancel_queue_item(item_id):
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            "SELECT status, run_id FROM batch_queue_items WHERE item_id=?", (item_id,)
        ).fetchone()
        if not row:
            return False
        if row[0] in {"QUEUED", "STARTING"} and not row[1]:
            return (
                db.execute(
                    "UPDATE batch_queue_items SET status='CANCELLED', updated_at=? WHERE item_id=? AND status=? AND run_id IS NULL",
                    (utc_now(), item_id, row[0]),
                ).rowcount
                == 1
            )
        return bool(row[1] and request_cancel(row[1]))


def pause_queue():
    with sqlite3.connect(DB_PATH) as db:
        return (
            db.execute(
                "UPDATE batch_queue_control SET status='PAUSED', updated_at=? WHERE id=1",
                (utc_now(),),
            ).rowcount
            == 1
        )


def _run_queue(agent_caller):
    global QUEUE_WORKER
    try:
        while True:
            with sqlite3.connect(DB_PATH) as db:
                db.execute("BEGIN IMMEDIATE")
                control = db.execute(
                    "SELECT status,root_name FROM batch_queue_control WHERE id=1"
                ).fetchone()
                row = db.execute(
                    "SELECT item_id,batch_id,images,retry_of FROM batch_queue_items WHERE status='QUEUED' AND root_name=? ORDER BY item_id LIMIT 1",
                    (control[1],),
                ).fetchone()
                if not control or control[0] != "RUNNING" or not row:
                    return
                claimed = db.execute(
                    "UPDATE batch_queue_items SET status='STARTING', updated_at=? WHERE item_id=? AND status='QUEUED'",
                    (utc_now(), row[0]),
                ).rowcount
                if not claimed:
                    continue
            item_id, batch_id, images_json, retry_of = row
            images = json.loads(images_json)
            try:
                run = create_run(batch_id, len(images))
                with sqlite3.connect(DB_PATH) as db:
                    bound = db.execute(
                        "UPDATE batch_queue_items SET status='RUNNING', run_id=?, updated_at=? WHERE item_id=? AND status='STARTING'",
                        (run["run_id"], utc_now(), item_id),
                    ).rowcount
                if not bound:
                    delete_runs([run["run_id"]])
                    continue
                if retry_of:
                    append_progress_event(
                        run["run_id"],
                        "INGEST",
                        "system",
                        "RETRYING",
                        0,
                        len(images),
                        f"从 {retry_of} 重试",
                    )
                process_batch_run(run["run_id"], batch_id, images, agent_caller)
                finished = get_run(run["run_id"])
                outcome = (
                    route_batch_outcome(finished.get("result") or {})
                    if finished["status"] == "SUCCEEDED"
                    else finished["status"]
                )
                status = (
                    outcome
                    if outcome
                    in {"QA_ACCEPTED", "RECHECK_REQUIRED", "WAITING_FOR_APPROVAL"}
                    else "FAILED"
                    if outcome == "FAILED"
                    else outcome
                )
                with sqlite3.connect(DB_PATH) as db:
                    db.execute(
                        "UPDATE batch_queue_items SET status=?, outcome=?, error=?, updated_at=? WHERE item_id=?",
                        (
                            status,
                            outcome,
                            None if status != "FAILED" else "批次结论无法安全路由",
                            utc_now(),
                            item_id,
                        ),
                    )
            except (
                OSError,
                RuntimeError,
                TypeError,
                ValueError,
                sqlite3.Error,
            ) as error:
                with sqlite3.connect(DB_PATH) as db:
                    db.execute(
                        "UPDATE batch_queue_items SET status='FAILED', error=?, updated_at=? WHERE item_id=?",
                        (str(error), utc_now(), item_id),
                    )
    finally:
        with QUEUE_LOCK:
            QUEUE_WORKER = None


def start_queue(agent_caller=None):
    global QUEUE_WORKER
    with sqlite3.connect(DB_PATH) as db:
        control = db.execute(
            "SELECT root_name FROM batch_queue_control WHERE id=1"
        ).fetchone()
        if (
            not control
            or not db.execute(
                "SELECT 1 FROM batch_queue_items WHERE status='QUEUED' AND root_name=?",
                (control[0],),
            ).fetchone()
        ):
            return False
        db.execute(
            "UPDATE batch_queue_control SET status='RUNNING', updated_at=? WHERE id=1",
            (utc_now(),),
        )
    with QUEUE_LOCK:
        if QUEUE_WORKER and QUEUE_WORKER.is_alive():
            return True
        QUEUE_WORKER = threading.Thread(
            target=_run_queue, args=(agent_caller or call_agent,), daemon=True
        )
        QUEUE_WORKER.start()
    return True


def retry_queue_item(item_id):
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            "SELECT root_name,batch_id,display_name,revision,manifest_digest,images,run_id,status FROM batch_queue_items WHERE item_id=?",
            (item_id,),
        ).fetchone()
        if not row or row[7] not in {"FAILED", "CANCELLED"}:
            return None
        now = utc_now()
        new_id = db.execute(
            "INSERT INTO batch_queue_items(root_name,batch_id,display_name,revision,manifest_digest,images,status,retry_of,created_at,updated_at) VALUES (?,?,?,?,?,?,'QUEUED',?,?,?)",
            (
                row[0],
                row[1],
                row[2],
                row[3] + 1,
                f"{row[4]}-retry-{item_id}",
                row[5],
                row[6],
                now,
                now,
            ),
        ).lastrowid
        return _select_queue_items(db, "WHERE item_id=?", (new_id,))[0]


def recover_batch_queue():
    recovered = 0
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            "SELECT item_id,status,run_id FROM batch_queue_items WHERE status IN ('STARTING','RUNNING')"
        ).fetchall()
    for item_id, status, run_id in rows:
        run = get_run(run_id) if run_id else None
        if run and run["status"] == "SUCCEEDED":
            outcome = route_batch_outcome(run.get("result") or {})
            final = outcome
            error = None if final != "FAILED" else "重启恢复时批次结论无法安全路由"
        elif run and run["status"] in {"FAILED", "CANCELLED"}:
            final, outcome, error = run["status"], run["status"], None
        else:
            final, outcome, error = (
                "FAILED",
                "FAILED",
                f"服务重启中断了 {status} 批次；请显式重试",
            )
            if run and run["status"] in {"PENDING", "RUNNING"}:
                append_progress_event(
                    run_id,
                    "COMPLETED",
                    "system",
                    "FAILED",
                    0,
                    run["product_count"],
                    "服务重启中断了活动调用",
                )
                save_run_result(
                    run_id,
                    {
                        "mode": "live",
                        "run_id": run_id,
                        "batch_id": run["batch_id"],
                        "item_count": run["product_count"],
                        "items": [],
                        "coordinator": "服务重启，未形成结论",
                        "risk": "未执行",
                        "error": "restart-interrupted",
                        "trace": ["服务重启中断"],
                        "transport": {"mode": "http-local", "kafka_used": False},
                    },
                    "FAILED",
                )
        with sqlite3.connect(DB_PATH) as db:
            db.execute(
                "UPDATE batch_queue_items SET status=?,outcome=?,error=?,updated_at=? WHERE item_id=?",
                (final, outcome, error, utc_now(), item_id),
            )
        recovered += 1
    return recovered


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _json(self, status, value):
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/batch-queues/current":
            self._json(200, get_batch_queue())
            return
        if parsed.path.startswith("/api/runs/"):
            parts = parsed.path.strip("/").split("/")
            run_id = parts[2] if len(parts) >= 3 else ""
            run = get_run(run_id)
            if not run:
                self._json(404, {"error": "运行不存在"})
                return
            if len(parts) == 4 and parts[3] == "events":
                after = int(parse_qs(parsed.query).get("after", ["0"])[0])
                self._json(
                    200,
                    {
                        "events": [
                            event
                            for event in run["progress_events"]
                            if event["sequence"] > after
                        ],
                        "status": run["status"],
                    },
                )
            else:
                self._json(200, run)
            return
        if parsed.path == "/api/history":
            with sqlite3.connect(DB_PATH) as db:
                rows = db.execute(
                    "SELECT payload FROM runs ORDER BY created_at DESC LIMIT 50"
                ).fetchall()
                jobs = db.execute(
                    "SELECT run_id FROM run_jobs WHERE status IN ('SUCCEEDED', 'FAILED', 'CANCELLED') ORDER BY created_at DESC LIMIT 50"
                ).fetchall()
            job_runs = []
            for (run_id,) in jobs:
                run = get_run(run_id)
                payload = run["result"] or {
                    "batch_id": run["batch_id"],
                    "item_count": run["product_count"],
                    "coordinator": "未形成批次结论",
                    "risk": run["status"],
                    "items": [],
                }
                job_runs.append(
                    {
                        **payload,
                        "run_id": run["run_id"],
                        "created_at": run["created_at"],
                        "progress_events": run["progress_events"],
                        "transport": run["transport"],
                        "status": run["status"],
                    }
                )
            old_runs = [json.loads(row[0]) for row in rows]
            known = {run["run_id"] for run in job_runs}
            self._json(
                200,
                {
                    "runs": job_runs
                    + [run for run in old_runs if run.get("run_id") not in known]
                },
            )
            return
        if self.path == "/api/images":
            folder = (
                ROOT.parent.parent.parent
                / "dataset"
                / "sheet_metal"
                / "sheet_metal"
                / "test_private"
            )
            images = [
                {
                    "image_id": p.name,
                    "filename": p.name,
                    "product_id": f"P-{p.stem.upper()}",
                    "batch_id": "BATCH-2026-0817-A",
                    "url": f"/api/product-image/{p.name}",
                }
                for p in sorted(folder.glob("*.png"))
            ]
            self._json(200, {"images": images})
            return
        if self.path == "/api/snapshot":
            payload = (ROOT / "demo_snapshot.json").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/api/scenario":
            payload = (ROOT / "demo_scenario.json").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/api/inspection-image":
            image = (
                ROOT.parent.parent.parent
                / "dataset"
                / "sheet_metal"
                / "sheet_metal"
                / "test_private"
                / "000_regular.png"
            )
            payload = image.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/batch-queues/scan":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                request = json.loads(self.rfile.read(length) or b"{}")
                self._json(
                    200,
                    scan_batch_queue(request.get("root_name"), request.get("batches")),
                )
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                self._json(400, {"error": str(error)})
            return
        if self.path == "/api/batch-queues/current/start":
            accepted = start_queue()
            self._json(202 if accepted else 409, {"accepted": accepted})
            return
        if self.path == "/api/batch-queues/current/pause":
            self._json(200, {"paused": pause_queue()})
            return
        if self.path.startswith("/api/batch-queue-items/"):
            parts = self.path.strip("/").split("/")
            if len(parts) == 4 and parts[2].isdigit():
                item_id = int(parts[2])
                if parts[3] == "cancel":
                    accepted = cancel_queue_item(item_id)
                    self._json(202 if accepted else 409, {"accepted": accepted})
                    return
                if parts[3] == "retry":
                    item = retry_queue_item(item_id)
                    self._json(
                        201 if item else 409, item or {"error": "当前批次不可重试"}
                    )
                    return
        if self.path.startswith("/api/runs/") and self.path.endswith("/cancel"):
            run_id = self.path.strip("/").split("/")[2]
            accepted = request_cancel(run_id)
            self._json(
                202 if accepted else 409, {"accepted": accepted, "run_id": run_id}
            )
            return
        if self.path == "/api/runs":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                request = json.loads(self.rfile.read(length) or b"{}")
                images = request.get("images", [])
                batch_id = str(request.get("batch_id") or "未命名批次")
                if not images:
                    raise ValueError("批次至少需要一张图片")
                run = create_run(batch_id, len(images))
                retry_of = request.get("retry_of")
                if retry_of:
                    append_progress_event(
                        run["run_id"],
                        "INGEST",
                        "system",
                        "RETRYING",
                        0,
                        len(images),
                        f"从失败运行 {retry_of} 创建重试",
                    )
                threading.Thread(
                    target=process_batch_run,
                    args=(run["run_id"], batch_id, images),
                    daemon=True,
                ).start()
                self._json(202, run)
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                self._json(400, {"error": str(error)})
            return
        if self.path == "/api/history/delete":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                request = json.loads(self.rfile.read(length) or b"{}")
                run_ids = request.get("run_ids", [])
                if not isinstance(run_ids, list) or not all(
                    isinstance(run_id, str) for run_id in run_ids
                ):
                    raise ValueError("run_ids 必须是字符串数组")
                deleted = delete_runs(run_ids)
                self._json(200, {"deleted": deleted})
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                self._json(400, {"error": f"删除请求无效：{error}"})
            return
        if self.path != "/api/run":
            self.send_error(405, "Only /api/run accepts POST")
            return
        if self.path.startswith("/api/product-image/"):
            name = Path(self.path.rsplit("/", 1)[-1]).name
            image = (
                ROOT.parent.parent.parent
                / "dataset"
                / "sheet_metal"
                / "sheet_metal"
                / "test_private"
                / name
            )
            if not image.exists() or image.suffix.lower() != ".png":
                self.send_error(404, "Image not found")
                return
            payload = image.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length) or b"{}")
            result = run_pipeline(request.get("images"))
            result["run_id"] = (
                f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            )
            result["created_at"] = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(DB_PATH) as db:
                db.execute(
                    "INSERT INTO runs(run_id, created_at, payload) VALUES (?, ?, ?)",
                    (
                        result["run_id"],
                        result["created_at"],
                        json.dumps(result, ensure_ascii=False),
                    ),
                )
        except RuntimeError as error:
            self._json(400, {"error": str(error)})
            return
        except Exception as error:  # noqa: BLE001  # provider boundary
            self._json(502, {"error": f"Agent provider failed: {error}"})
            return
        self._json(200, result)

    def do_PUT(self):
        self.send_error(405, "Read-only demo server")

    def do_DELETE(self):
        if self.path != "/api/history":
            self.send_error(405, "Only /api/history accepts DELETE")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length) or b"{}")
            run_ids = request.get("run_ids", [])
            if not isinstance(run_ids, list) or not all(
                isinstance(run_id, str) for run_id in run_ids
            ):
                raise ValueError("run_ids 必须是字符串数组")
            deleted = delete_runs(run_ids)
            self._json(200, {"deleted": deleted})
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            self._json(400, {"error": f"删除请求无效：{error}"})


def call_agent(role, instruction, context, image_data=None):
    setting = lambda name, fallback=None: LOCAL_CONFIG.get(
        name, os.getenv(name, fallback)
    )
    key = setting(f"FACTORYOPS_{role.upper()}_API_KEY") or setting("FACTORYOPS_API_KEY")
    endpoint = setting(f"FACTORYOPS_{role.upper()}_API_URL") or setting(
        "FACTORYOPS_API_URL", "https://api.openai.com/v1/chat/completions"
    )
    endpoint = endpoint.strip().strip('"').strip("'").rstrip("#").rstrip("/")
    if endpoint.endswith(("/v1", "/compatible-mode")):
        endpoint = f"{endpoint}/chat/completions"
    model = setting(f"FACTORYOPS_{role.upper()}_MODEL") or setting(
        "FACTORYOPS_MODEL", "gpt-4o-mini"
    )
    if not key:
        raise RuntimeError(
            f"未配置 {role} Agent API Key。请设置 FACTORYOPS_{role.upper()}_API_KEY。"
        )
    user_content = [
        {
            "type": "text",
            "text": f"{instruction}\n\n上下文：{json.dumps(context, ensure_ascii=False)}",
        }
    ]
    if image_data:
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_data}"},
            }
        )
    body = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": f"你是 FactoryOps 的 {role} Agent。只返回中文、结构化、可审计的判断。",
            },
            {
                "role": "user",
                "content": user_content if image_data else user_content[0]["text"],
            },
        ],
    }
    auth_header = os.getenv(
        f"FACTORYOPS_{role.upper()}_AUTH_HEADER",
        os.getenv("FACTORYOPS_AUTH_HEADER", "Authorization"),
    )
    auth_prefix = os.getenv(
        f"FACTORYOPS_{role.upper()}_AUTH_PREFIX",
        os.getenv("FACTORYOPS_AUTH_PREFIX", "Bearer"),
    )
    headers = {
        "Content-Type": "application/json",
        auth_header: f"{auth_prefix} {key}".strip(),
    }
    request = Request(
        endpoint, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    try:
        with urlopen(request, timeout=45) as response:
            payload = json.loads(response.read())
    except Exception as error:  # provider boundary
        status = getattr(error, "code", "unknown")
        reason = getattr(error, "reason", str(error))
        raise RuntimeError(
            f"{role} Agent 认证或请求失败（HTTP {status}，模型={model}，接口={endpoint}）。请检查 API Key、模型权限、接口地址和认证头配置。原因：{reason}"
        ) from error
    return payload["choices"][0]["message"]["content"]


def process_batch_run(run_id, batch_id, selected_images, agent_caller=call_agent):
    total = len(selected_images)
    results = []
    try:
        append_progress_event(
            run_id,
            "INGEST",
            "system",
            "SUCCEEDED",
            total,
            total,
            f"已读取 {total} 个产品",
        )
        for index, selected in enumerate(selected_images, 1):
            uploaded = isinstance(selected, dict)
            name = Path(
                selected.get("name", "uploaded.png") if uploaded else selected
            ).name
            image = (
                ROOT.parent.parent.parent
                / "dataset"
                / "sheet_metal"
                / "sheet_metal"
                / "test_private"
                / name
            )
            if not uploaded and not image.exists():
                raise RuntimeError(f"检测图片不存在：{name}")
            encoded = (
                selected["data"]
                if uploaded
                else base64.b64encode(image.read_bytes()).decode()
            )
            append_progress_event(
                run_id,
                "VISION",
                "vision",
                "RUNNING",
                index - 1,
                total,
                f"正在检测第 {index} 个产品",
                name,
            )
            vision = agent_caller(
                "vision",
                "分析这张工业产品图片，指出缺陷、严重程度和置信度。",
                {"batch": batch_id, "image": name},
                encoded,
            )
            ensure_not_cancelled(run_id)
            append_progress_event(
                run_id,
                "VISION",
                "vision",
                "SUCCEEDED",
                index,
                total,
                f"第 {index} 个产品视觉检测完成",
                name,
            )
            context = {"vision_result": vision, "batch": batch_id, "image": name}

            def run_specialist(
                role,
                current_index=index,
                current_name=name,
                current_context=context,
            ):
                append_progress_event(
                    run_id,
                    "SPECIALISTS",
                    role,
                    "RUNNING",
                    current_index - 1,
                    total,
                    f"{role} 正在分析第 {current_index} 个产品",
                    current_name,
                )
                output = agent_caller(
                    role,
                    "根据视觉异常判断对本角色负责领域的影响，并给出建议。",
                    current_context,
                )
                ensure_not_cancelled(run_id)
                append_progress_event(
                    run_id,
                    "SPECIALISTS",
                    role,
                    "SUCCEEDED",
                    current_index,
                    total,
                    f"{role} 完成：{output[:100]}",
                    current_name,
                )
                return role, output

            with ThreadPoolExecutor(max_workers=3) as executor:
                specialists = dict(
                    executor.map(run_specialist, ("quality", "production", "sla"))
                )
            results.append(
                {
                    "image": name,
                    "product_id": f"P-{Path(name).stem.upper()}",
                    "batch_id": batch_id,
                    "vision": vision,
                    "specialists": specialists,
                }
            )
            save_run_result(
                run_id,
                {
                    "mode": "live",
                    "run_id": run_id,
                    "batch_id": batch_id,
                    "product_id": f"BATCH-{batch_id}",
                    "item_count": total,
                    "completed_item_count": len(results),
                    "items": results,
                    "coordinator": "批次尚未完成，未形成最终结论",
                    "risk": "尚未执行批次风险审查",
                    "trace": ["批次读取", "产品证据处理中"],
                    "transport": {"mode": "http-local", "kafka_used": False},
                },
            )
        batch_context = {"batch": batch_id, "product_count": total, "products": results}
        append_progress_event(
            run_id, "COORDINATOR", "coordinator", "RUNNING", 0, 1, "正在汇总整个批次"
        )
        fusion = agent_caller(
            "coordinator",
            "汇总整个生产批次的所有产品证据，给出唯一批次结论、主要异常、影响范围和建议动作。",
            batch_context,
        )
        ensure_not_cancelled(run_id)
        append_progress_event(
            run_id,
            "COORDINATOR",
            "coordinator",
            "SUCCEEDED",
            1,
            1,
            f"批次结论：{fusion[:100]}",
        )
        append_progress_event(
            run_id, "RISK", "risk", "RUNNING", 0, 1, "正在审查批次风险"
        )
        risk = agent_caller(
            "risk",
            "针对整个生产批次结论进行风险与审批判断。只返回 JSON 对象，必须包含 decision（PASS/RECHECK/HOLD_BATCH/STOP_LINE）、requires_human_approval（布尔值）、risk_level 和 policy_refs（数组），不得添加 Markdown。",
            {**batch_context, "batch_coordinator": fusion},
        )
        risk_fields = parse_risk_decision(risk)
        ensure_not_cancelled(run_id)
        append_progress_event(
            run_id, "RISK", "risk", "SUCCEEDED", 1, 1, f"风险结论：{risk[:100]}"
        )
        approval_required = bool(risk_fields and risk_fields["requires_human_approval"])
        append_progress_event(
            run_id,
            "APPROVAL",
            "approval",
            "PENDING" if approval_required else "SUCCEEDED",
            0 if approval_required else 1,
            1,
            "等待人工确认批次动作" if approval_required else "策略判定无需人工审批",
        )
        result = {
            "mode": "live",
            "run_id": run_id,
            "batch_id": batch_id,
            "product_id": f"BATCH-{batch_id}",
            "item_count": total,
            "items": results,
            "coordinator": fusion,
            "risk": risk,
            **(risk_fields or {}),
            "trace": [
                "批次读取",
                "Vision 逐张检测",
                "Specialist 协作",
                "Coordinator 批次汇总",
                "Risk 批次审查",
            ],
            "transport": {"mode": "http-local", "kafka_used": False},
        }
        append_progress_event(
            run_id, "COMPLETED", "system", "SUCCEEDED", total, total, "批次审查完成"
        )
        complete_run(run_id, result)
    except RunCancelled:
        append_progress_event(
            run_id, "COMPLETED", "system", "CANCELLED", 0, total, "批次检测已取消"
        )
        save_run_result(
            run_id,
            {
                "mode": "live",
                "run_id": run_id,
                "batch_id": batch_id,
                "item_count": total,
                "completed_item_count": len(results),
                "items": results,
                "coordinator": "运行已取消，未形成最终批次结论",
                "risk": "未执行",
                "trace": ["批次运行取消"],
                "transport": {"mode": "http-local", "kafka_used": False},
            },
            "CANCELLED",
        )
    except Exception as error:  # noqa: BLE001  # persist arbitrary provider failures
        append_progress_event(
            run_id, "COMPLETED", "system", "FAILED", 0, total, str(error)
        )
        save_run_result(
            run_id,
            {
                "mode": "live",
                "run_id": run_id,
                "batch_id": batch_id,
                "item_count": total,
                "completed_item_count": len(results),
                "items": results,
                "coordinator": "运行失败，未形成最终批次结论",
                "risk": "未执行",
                "error": str(error),
                "trace": ["批次运行失败"],
                "transport": {"mode": "http-local", "kafka_used": False},
            },
            "FAILED",
        )


def run_pipeline(selected_images=None):
    results = []
    for selected in selected_images or ["000_regular.png"]:
        uploaded = isinstance(selected, dict)
        name = Path(selected.get("name", "uploaded.png") if uploaded else selected).name
        image = (
            ROOT.parent.parent.parent
            / "dataset"
            / "sheet_metal"
            / "sheet_metal"
            / "test_private"
            / name
        )
        if not uploaded and not image.exists():
            raise RuntimeError(f"检测图片不存在：{name}")
        encoded = (
            selected["data"]
            if uploaded
            else base64.b64encode(image.read_bytes()).decode()
        )
        vision = call_agent(
            "vision",
            "分析这张工业产品图片，指出缺陷、严重程度和置信度。",
            {"batch": "BATCH-2026-0817-A", "image": name},
            encoded,
        )
        context = {"vision_result": vision, "batch": "BATCH-2026-0817-A", "image": name}
        specialists = {
            role: call_agent(
                role, "根据视觉异常判断对本角色负责领域的影响，并给出建议。", context
            )
            for role in ("quality", "production", "sla")
        }
        fusion = call_agent(
            "coordinator",
            "汇总三个专家结果，形成一个明确的业务建议。",
            {**context, "specialists": specialists},
        )
        risk = call_agent(
            "risk",
            "检查该建议是否需要人工审批，并说明风险规则依据。",
            {**context, "specialists": specialists, "fusion": fusion},
        )
        results.append(
            {
                "image": name,
                "product_id": f"P-{Path(name).stem.upper()}",
                "batch_id": "BATCH-2026-0817-A",
                "vision": vision,
                "specialists": specialists,
                "coordinator": fusion,
                "risk": risk,
                "trace": [
                    "vision",
                    "quality",
                    "production",
                    "sla",
                    "coordinator",
                    "risk",
                ],
            }
        )
    first = results[0]
    batch_context = {
        "batch": first["batch_id"],
        "product_count": len(results),
        "products": [
            {
                "image": item["image"],
                "vision": item["vision"],
                "specialists": item["specialists"],
                "product_coordinator": item["coordinator"],
                "product_risk": item["risk"],
            }
            for item in results
        ],
    }
    batch_coordinator = call_agent(
        "coordinator",
        "汇总整个生产批次的所有产品检测证据，只给出一个批次级结论、主要异常、影响范围和建议动作。",
        batch_context,
    )
    batch_risk = call_agent(
        "risk",
        "针对整个生产批次的汇总结论进行风险与审批判断，只给出一个批次级风险结论和是否需要人工审批。",
        {**batch_context, "batch_coordinator": batch_coordinator},
    )
    return {
        "mode": "live",
        "image": first["image"],
        "product_id": first["product_id"],
        "batch_id": first["batch_id"],
        "vision": first["vision"],
        "specialists": first["specialists"],
        "coordinator": batch_coordinator,
        "risk": batch_risk,
        "trace": ["批次逐张检测", "批次 Coordinator 汇总", "批次 Risk 审查"],
        "items": results,
        "item_count": len(results),
    }


if __name__ == "__main__":
    # Serve dashboard.html and its assets from the frontend directory regardless
    # of the directory from which the script was launched.
    os.chdir(ROOT)
    resume_dispatch = get_batch_queue()["status"] == "RUNNING"
    recover_batch_queue()
    if resume_dispatch:
        start_queue()
    server = ThreadingHTTPServer(("127.0.0.1", 4173), DemoHandler)
    print("FactoryOps demo server: http://127.0.0.1:4173/dashboard.html")
    server.serve_forever()
