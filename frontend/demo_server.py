from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import base64
import json
import os
import sqlite3
from datetime import datetime, timezone
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "demo_runs.sqlite3"
LOCAL_CONFIG = {}


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
        db.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)")


init_db()


class DemoHandler(SimpleHTTPRequestHandler):
    def _json(self, status, value):
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        if self.path == "/api/history":
            with sqlite3.connect(DB_PATH) as db:
                rows = db.execute("SELECT payload FROM runs ORDER BY created_at DESC LIMIT 50").fetchall()
            self._json(200, {"runs": [json.loads(row[0]) for row in rows]})
            return
        if self.path == "/api/images":
            folder = ROOT.parent.parent.parent / "dataset" / "sheet_metal" / "sheet_metal" / "test_private"
            images = [{"image_id": p.name, "filename": p.name, "product_id": f"P-{p.stem.upper()}", "batch_id": "BATCH-2026-0817-A", "url": f"/api/product-image/{p.name}"} for p in sorted(folder.glob("*.png"))]
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
            image = ROOT.parent.parent.parent / "dataset" / "sheet_metal" / "sheet_metal" / "test_private" / "000_regular.png"
            payload = image.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def do_POST(self):  # noqa: N802
        if self.path != "/api/run":
            self.send_error(405, "Only /api/run accepts POST")
            return
        if self.path.startswith("/api/product-image/"):
            name = Path(self.path.rsplit("/", 1)[-1]).name
            image = ROOT.parent.parent.parent / "dataset" / "sheet_metal" / "sheet_metal" / "test_private" / name
            if not image.exists() or image.suffix.lower() != ".png":
                self.send_error(404, "Image not found")
                return
            payload = image.read_bytes()
            self.send_response(200); self.send_header("Content-Type", "image/png"); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload); return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length) or b"{}")
            result = run_pipeline(request.get("images"))
            result["run_id"] = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            result["created_at"] = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(DB_PATH) as db:
                db.execute("INSERT INTO runs(run_id, created_at, payload) VALUES (?, ?, ?)", (result["run_id"], result["created_at"], json.dumps(result, ensure_ascii=False)))
        except RuntimeError as error:
            self._json(400, {"error": str(error)})
            return
        except Exception as error:  # pragma: no cover - network/provider boundary
            self._json(502, {"error": f"Agent provider failed: {error}"})
            return
        self._json(200, result)

    def do_PUT(self):  # noqa: N802
        self.send_error(405, "Read-only demo server")


def call_agent(role, instruction, context, image_data=None):
    setting = lambda name, fallback=None: LOCAL_CONFIG.get(name, os.getenv(name, fallback))
    key = setting(f"FACTORYOPS_{role.upper()}_API_KEY") or setting("FACTORYOPS_API_KEY")
    endpoint = setting(f"FACTORYOPS_{role.upper()}_API_URL") or setting("FACTORYOPS_API_URL", "https://api.openai.com/v1/chat/completions")
    endpoint = endpoint.strip().strip('"').strip("'").rstrip("#").rstrip("/")
    if endpoint.endswith("/v1") or endpoint.endswith("/compatible-mode"):
        endpoint = f"{endpoint}/chat/completions"
    model = setting(f"FACTORYOPS_{role.upper()}_MODEL") or setting("FACTORYOPS_MODEL", "gpt-4o-mini")
    if not key:
        raise RuntimeError(f"未配置 {role} Agent API Key。请设置 FACTORYOPS_{role.upper()}_API_KEY。")
    user_content = [{"type": "text", "text": f"{instruction}\n\n上下文：{json.dumps(context, ensure_ascii=False)}"}]
    if image_data:
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}})
    body = {"model": model, "temperature": 0, "messages": [{"role": "system", "content": f"你是 FactoryOps 的 {role} Agent。只返回中文、结构化、可审计的判断。"}, {"role": "user", "content": user_content if image_data else user_content[0]["text"]}]}
    auth_header = os.getenv(f"FACTORYOPS_{role.upper()}_AUTH_HEADER", os.getenv("FACTORYOPS_AUTH_HEADER", "Authorization"))
    auth_prefix = os.getenv(f"FACTORYOPS_{role.upper()}_AUTH_PREFIX", os.getenv("FACTORYOPS_AUTH_PREFIX", "Bearer"))
    headers = {"Content-Type": "application/json", auth_header: f"{auth_prefix} {key}".strip()}
    request = Request(endpoint, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=45) as response:
            payload = json.loads(response.read())
    except Exception as error:
        status = getattr(error, "code", "unknown")
        reason = getattr(error, "reason", str(error))
        raise RuntimeError(f"{role} Agent 认证或请求失败（HTTP {status}，模型={model}，接口={endpoint}）。请检查 API Key、模型权限、接口地址和认证头配置。原因：{reason}") from error
    return payload["choices"][0]["message"]["content"]


def run_pipeline(selected_images=None):
    results = []
    for selected in (selected_images or ["000_regular.png"]):
        name = Path(selected).name
        image = ROOT.parent.parent.parent / "dataset" / "sheet_metal" / "sheet_metal" / "test_private" / name
        if not image.exists():
            raise RuntimeError(f"检测图片不存在：{name}")
        encoded = base64.b64encode(image.read_bytes()).decode()
        vision = call_agent("vision", "分析这张工业产品图片，指出缺陷、严重程度和置信度。", {"batch": "BATCH-2026-0817-A", "image": name}, encoded)
        context = {"vision_result": vision, "batch": "BATCH-2026-0817-A", "image": name}
        specialists = {role: call_agent(role, "根据视觉异常判断对本角色负责领域的影响，并给出建议。", context) for role in ("quality", "production", "sla")}
        fusion = call_agent("coordinator", "汇总三个专家结果，形成一个明确的业务建议。", {**context, "specialists": specialists})
        risk = call_agent("risk", "检查该建议是否需要人工审批，并说明风险规则依据。", {**context, "specialists": specialists, "fusion": fusion})
        results.append({"image": name, "product_id": f"P-{Path(name).stem.upper()}", "batch_id": "BATCH-2026-0817-A", "vision": vision, "specialists": specialists, "coordinator": fusion, "risk": risk, "trace": ["vision", "quality", "production", "sla", "coordinator", "risk"]})
    first = results[0]
    return {"mode": "live", "image": first["image"], "product_id": first["product_id"], "batch_id": first["batch_id"], "vision": first["vision"], "specialists": first["specialists"], "coordinator": first["coordinator"], "risk": first["risk"], "trace": first["trace"], "items": results, "item_count": len(results)}

    def do_DELETE(self):  # noqa: N802
        self.send_error(405, "Read-only demo server")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 4173), DemoHandler)
    print("FactoryOps demo server: http://127.0.0.1:4173/dashboard.html")
    server.serve_forever()
