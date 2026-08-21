from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import base64
import json
import os
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent


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
        os.environ.setdefault(key.strip(), cleaned)


load_local_config()


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
        try:
            result = run_pipeline()
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
    key = os.getenv(f"FACTORYOPS_{role.upper()}_API_KEY") or os.getenv("FACTORYOPS_API_KEY")
    endpoint = os.getenv(f"FACTORYOPS_{role.upper()}_API_URL", "https://api.openai.com/v1/chat/completions")
    model = os.getenv(f"FACTORYOPS_{role.upper()}_MODEL", os.getenv("FACTORYOPS_MODEL", "gpt-4o-mini"))
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
        raise RuntimeError(f"{role} Agent 认证或请求失败（HTTP {status}）。请检查 API Key、接口地址和认证头配置。原始错误：{error}") from error
    return payload["choices"][0]["message"]["content"]


def run_pipeline():
    image = ROOT.parent.parent.parent / "dataset" / "sheet_metal" / "sheet_metal" / "test_private" / "000_regular.png"
    if not image.exists():
        raise RuntimeError("检测图片不存在。")
    encoded = base64.b64encode(image.read_bytes()).decode()
    vision = call_agent("vision", "分析这张工业产品图片，指出缺陷、严重程度和置信度。", {"batch": "BATCH-2026-0817-A"}, encoded)
    context = {"vision_result": vision, "batch": "BATCH-2026-0817-A"}
    specialists = {role: call_agent(role, "根据视觉异常判断对本角色负责领域的影响，并给出建议。", context) for role in ("quality", "production", "sla")}
    fusion = call_agent("coordinator", "汇总三个专家结果，形成一个明确的业务建议。", {**context, "specialists": specialists})
    risk = call_agent("risk", "检查该建议是否需要人工审批，并说明风险规则依据。", {**context, "specialists": specialists, "fusion": fusion})
    return {"mode": "live", "vision": vision, "specialists": specialists, "coordinator": fusion, "risk": risk, "trace": ["vision", "quality", "production", "sla", "coordinator", "risk"]}

    def do_DELETE(self):  # noqa: N802
        self.send_error(405, "Read-only demo server")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 4173), DemoHandler)
    print("FactoryOps demo server: http://127.0.0.1:4173/dashboard.html")
    server.serve_forever()
