"""Evaluation report store + background runner (powers the in-product 评测页).

The offline evaluation scripts already produce honest metrics (recall / confirm
rate / false-positive rate), but those numbers lived only in a terminal. This
service stores reports as JSON and can launch a fresh run in the background so
the product — and the thesis — have a reproducible entry point.

The heavy work (loading the pose + expression models) runs in a **subprocess** so
a long evaluation can never block the API event loop or the inference lock.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.config import ROOT_DIR

REPORT_DIR = ROOT_DIR / 'data' / 'eval'
SCRIPT = ROOT_DIR / 'scripts' / 'eval' / 'evaluate_pipeline_urfd.py'
RUN_TIMEOUT_SECONDS = 3600

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _safe_name(name: str) -> str:
    return ''.join(ch for ch in str(name or '') if ch.isalnum() or ch in '-_') or 'report'


def report_path(name: str) -> Path:
    return REPORT_DIR / f'{_safe_name(name)}.json'


def list_reports() -> list[dict[str, Any]]:
    """列出可用的评测报告。

    此前是 glob 目录下**所有** *.json，于是调试过程中产生的中间产物
    （m2_replay_v2/v3/v4、urfd_side_after_pain、pose_comparison 等）全部
    混进列表 —— 实测列出了 23 份无差别报告，用户在一个下拉框里根本分不清
    哪份代表当前系统、哪份是废弃的试验。这就是"评测页不知道要干嘛"的根源。

    现在只收录**结构完整**的评测报告（必须含 summary 与 fall/adl 明细），
    并按生成时间倒序 —— 最新的排在最前。非评测 JSON 一律不出现。
    """
    if not REPORT_DIR.exists():
        return []
    reports = []
    for path in REPORT_DIR.glob('*.json'):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        summary = data.get('summary')
        # 结构校验：没有 summary 或缺少 fall/adl 明细的，不是评测报告
        if not isinstance(summary, dict) or not summary:
            continue
        if not isinstance(data.get('fall'), dict) or not isinstance(data.get('adl'), dict):
            continue
        reports.append({
            'name': path.stem,
            'generatedAt': data.get('generatedAt'),
            'dataset': data.get('dataset'),
            'config': data.get('config'),
            'summary': summary,
            'fallTotal': data['fall'].get('total'),
            'adlTotal': data['adl'].get('total'),
        })
    # 最新在前；缺 generatedAt 的排最后
    reports.sort(key=lambda r: r.get('generatedAt') or '', reverse=True)
    return reports


def get_report(name: str) -> dict[str, Any] | None:
    path = report_path(name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def _worker(job_id: str, *, every: int, videos: int, name: str) -> None:
    job = _jobs[job_id]
    out = report_path(name)
    cmd = [sys.executable, str(SCRIPT), '--every', str(every),
           '--videos', str(videos), '--out', str(out)]
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True,
                              text=True, timeout=RUN_TIMEOUT_SECONDS)
        job['log'] = (proc.stdout or '').splitlines()[-30:]
        if proc.returncode == 0 and out.exists():
            job['status'] = 'done'
            job['report'] = out.stem
            job['summary'] = (get_report(out.stem) or {}).get('summary')
        else:
            job['status'] = 'failed'
            job['error'] = (proc.stderr or '脚本执行失败')[-500:]
    except subprocess.TimeoutExpired:
        job['status'] = 'failed'
        job['error'] = f'评测超时（>{RUN_TIMEOUT_SECONDS}s）'
    except Exception as exc:  # noqa: BLE001
        job['status'] = 'failed'
        job['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        job['finishedAt'] = time.time()


def start_run(*, every: int = 5, videos: int = 0, name: str = 'urfd_pipeline') -> dict[str, Any]:
    safe = _safe_name(name)
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        running = [j for j in _jobs.values() if j.get('status') == 'running']
        if running:
            return {'id': running[0]['id'], 'status': 'running', 'reused': True}
        _jobs[job_id] = {
            'id': job_id, 'status': 'running', 'name': safe,
            'startedAt': time.time(),
            'every': every, 'videos': videos, 'log': [],
        }
    threading.Thread(target=_worker, args=(job_id,),
                     kwargs={'every': every, 'videos': videos, 'name': safe},
                     daemon=True).start()
    return _jobs[job_id]


def job_status(job_id: str) -> dict[str, Any] | None:
    job = _jobs.get(job_id)
    if not job:
        return None
    result = dict(job)
    if job.get('status') == 'running':
        result['elapsedSeconds'] = int(time.time() - job.get('startedAt', time.time()))
    return result
