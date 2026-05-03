from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from app.models import IndependentTaskPackage, SandboxInfo


class SandboxAccessError(RuntimeError):
    pass


class SandboxManager:
    def __init__(self, base_dir: Path | None = None, cleanup_on_exit: bool = True) -> None:
        self.base_dir = base_dir or Path(tempfile.gettempdir()) / "thirty_agent_sandboxes"
        self.cleanup_on_exit = cleanup_on_exit
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create(self, agent_id: str, run_id: str | None = None) -> SandboxInfo:
        safe_agent_id = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in agent_id)
        run_id = run_id or str(uuid4())
        root = Path(tempfile.mkdtemp(prefix=f"{run_id}_{safe_agent_id}_", dir=self.base_dir))
        return SandboxInfo(run_id=run_id, agent_id=agent_id, root_path=root, cleanup_on_exit=self.cleanup_on_exit)

    def assert_inside(self, sandbox: SandboxInfo, path: Path) -> Path:
        root = sandbox.root_path.resolve()
        candidate = path.resolve()
        if candidate != root and root not in candidate.parents:
            raise SandboxAccessError(f"Path {candidate} is outside sandbox {root}")
        return candidate

    def write_package(self, sandbox: SandboxInfo, package: IndependentTaskPackage) -> SandboxInfo:
        package_path = self.assert_inside(sandbox, sandbox.root_path / "task_package.json")
        package_path.write_text(package.model_dump_json(indent=2), encoding="utf-8")
        sandbox.package_path = package_path
        return sandbox

    def write_json(self, sandbox: SandboxInfo, relative_path: str, payload: dict) -> Path:
        target = self.assert_inside(sandbox, sandbox.root_path / relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return target

    def cleanup(self, sandbox: SandboxInfo) -> None:
        if sandbox.cleanup_on_exit and sandbox.root_path.exists():
            shutil.rmtree(sandbox.root_path, ignore_errors=True)
