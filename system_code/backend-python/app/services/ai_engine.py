import sys
import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import HTTPException

from app.core.config import ROOT_DIR, Settings, get_settings

logger = logging.getLogger(__name__)


class LocalAIEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._system = None
        self._error: str | None = None
        self._lock = Lock()
        # Serialises inference. SmartElderlyCareSystem.process_frame mutates
        # shared per-session state (face tracker, fall track dicts, temporal
        # histories, last-expression fields); concurrent calls from the
        # frame-stream WebSocket and the detect API race on that state and
        # corrupt the face box / fall state. A single lock around inference
        # makes the engine correct under concurrency.
        self._predict_lock = Lock()

    def available(self) -> bool:
        return self.status()['status'] == 'healthy'

    def status(self) -> dict[str, Any]:
        """引擎状态。

        **阈值一律报「正在生效的值」，即 self._system 上的实例属性**，
        而不是 self.settings（环境变量/配置文件的初始值）。

        这里原来全部读 self.settings，于是管理员在「AI 判定参数」页改完并
        保存成功（后端确实调了 apply_runtime_config）之后，本接口仍然报
        环境变量的初始值 —— 表现为"改了不生效"、"面板在说谎"。
        实测：apply_ai_config 返回 ['fall_threshold','expr_conf','alert_bounds']
        说明已经生效，而 status() 依旧显示 0.3 / 0.25（默认值）。

        模型未加载时没有实例可读，才回退到 settings。
        """
        try:
            self._ensure_loaded()
        except Exception as exc:
            self._error = str(exc)

        sys_ = self._system

        def live(attr: str, fallback: Any) -> Any:
            if sys_ is None:
                return fallback
            v = getattr(sys_, attr, None)
            return fallback if v is None else v

        return {
            'status': 'healthy' if sys_ is not None else 'unavailable',
            'requestedDevice': self.settings.ai_device,
            'device': live('device', self.settings.ai_device),
            'poseModel': self.settings.ai_pose_model_path,
            'exprModel': self.settings.ai_expr_model_path,
            'fallThreshold': live('fall_threshold', self.settings.ai_fall_threshold),
            'poseConf': live('pose_conf', self.settings.ai_pose_conf),
            'poseIou': live('pose_iou', self.settings.ai_pose_iou),
            'poseImgsz': live('pose_imgsz', self.settings.ai_pose_imgsz),
            'poseMaxDet': live('pose_max_det', self.settings.ai_pose_max_det),
            'exprConf': live('expr_conf', self.settings.ai_expr_conf),
            # 告警分级边界也一并暴露：它是「AI 判定参数」页可改的东西，
            # 不给出来就没法从外部核对改到底生效没有。
            'alertBounds': dict(getattr(sys_, 'alert_bounds', {}) or {}),
            'faceSuodingLoaded': bool(getattr(sys_, '_suoding', None)),
            # 时序跌倒模型的状态。这里必须双向报出来：只看"配了路径"会掩盖
            # "配了但加载失败、实际还在用几何规则"这种情况。
            'fallModelPath': self.settings.ai_fall_model_path,
            'fallModelActive': getattr(sys_, 'fall_temporal', None) is not None,
            'fallModelError': getattr(sys_, 'fall_temporal_error', None),
            'error': self._error,
        }

    def predict(self, frame: Any, camera_id: int | None = None,
                reset_state: bool = False) -> dict[str, Any]:
        self._ensure_loaded()
        if self._system is None:
            raise HTTPException(status_code=503, detail=self._error or 'AI 引擎不可用')
        with self._predict_lock:
            # Single-image requests must not inherit temporal state (face box,
            # expression cache, fall history) from a previous request.
            if reset_state:
                self._system.reset_state()
            result = self._system.process_frame(frame)
        data = self._to_response(result)
        if camera_id is not None:
            data['cameraId'] = camera_id
        return data

    def _fall_model_path(self) -> str | None:
        """时序跌倒模型权重；空串或文件不存在时返回 None（回退几何规则）。

        回退而不是报错：模型文件缺失不应该让整个 AI 引擎起不来，
        几何规则本身是可用的降级路径。
        """
        raw = (self.settings.ai_fall_model_path or '').strip()
        if not raw:
            return None
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = ROOT_DIR / path
        return str(path) if path.exists() else None

    def _ensure_loaded(self) -> None:
        if self._system is not None:
            return
        with self._lock:
            if self._system is not None:
                return
            self._load()

    def _resolve_device(self) -> str:
        requested = (self.settings.ai_device or 'auto').strip().lower()
        if requested != 'auto':
            return requested
        try:
            import torch
            if getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available():
                return 'mps'
            if torch.cuda.is_available():
                return 'cuda'
        except Exception:
            pass
        return 'cpu'

    def _load(self) -> None:
        pose_path = Path(self.settings.ai_pose_model_path).expanduser().resolve()
        expr_path = Path(self.settings.ai_expr_model_path).expanduser().resolve()
        if not pose_path.exists():
            raise RuntimeError(f'姿态估计模型不存在: {pose_path}')
        if not expr_path.exists():
            raise RuntimeError(f'表情识别模型不存在: {expr_path}')

        ultralytics_path = ROOT_DIR / 'third_party' / 'ultralytics'
        for path in (ROOT_DIR, ultralytics_path):
            value = str(path)
            if value not in sys.path:
                sys.path.insert(0, value)

        try:
            from expression_recognition.system import SmartElderlyCareSystem
        except Exception as exc:
            raise RuntimeError(f'AI Pipeline 导入失败: {exc}') from exc

        device = self._resolve_device()
        try:
            system = SmartElderlyCareSystem(
                pose_model_path=str(pose_path),
                expr_model_path=str(expr_path),
                device=device,
                expr_conf=self.settings.ai_expr_conf,
                fall_threshold=self.settings.ai_fall_threshold,
                pose_conf=self.settings.ai_pose_conf,
                pose_iou=self.settings.ai_pose_iou,
                pose_imgsz=self.settings.ai_pose_imgsz,
                pose_max_det=self.settings.ai_pose_max_det,
                fall_model_path=self._fall_model_path(),
                fall_model_smooth=self.settings.ai_fall_model_smooth,
            )
        except Exception as exc:
            raise RuntimeError(f'AI Pipeline 初始化失败: {exc}') from exc

        self._system = system
        self._error = None
        # apply any AI parameters persisted by the admin UI
        self.load_ai_config_from_db()

    # ── Admin-UI -> engine configuration bridge ────────────────────────────
    # The frontend AI settings panel persists into the `settings` table, but
    # the engine historically read only environment variables, so every slider
    # in that panel was inert. These methods close that gap.
    _AI_CONFIG_KEYS = (
        'aiConfig', 'ai_config', 'aiSettings', 'ai_settings',
    )

    def apply_ai_config(self, payload: dict[str, Any] | None) -> list[str]:
        """Push admin-UI AI parameters into the running pipeline.

        Mapping (all optional):
          minConfidence      percent -> expr_conf（表情模型的置信度阈值）
          fallThreshold      -> fall_threshold（姿态判据的触发线）
          exprSampleInterval -> expr_sample_interval
          lowMin / mediumMin / highMin / urgentMin (percent) -> alert_bounds
          alignFaces / exprInputSize -> alignment switches

        Returns the list of parameters actually applied.
        """
        if not payload or self._system is None:
            return []
        cfg: dict[str, Any] = {}

        def as_float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        v = as_float(payload.get('minConfidence'))
        if v is not None:
            cfg['expr_conf'] = v / 100.0
        v = as_float(payload.get('fallThreshold'))
        if v is not None:
            cfg['fall_threshold'] = v / 100.0 if v > 1.0 else v
        v = as_float(payload.get('exprSampleInterval'))
        if v is not None:
            cfg['expr_sample_interval'] = v
        if payload.get('alignFaces') is not None:
            cfg['expr_align'] = payload.get('alignFaces')
        v = as_float(payload.get('exprInputSize'))
        if v is not None:
            cfg['expr_input_size'] = int(v)

        # 告警分级边界：low/medium/high/urgent 四条。
        # urgent 此前**没有映射** —— 界面上也没有对应控件，所以引擎里那条
        # 0.8 的紧急阈值是写死的、管理员根本改不了。
        bounds = {}
        for src, dst in (('lowMin', 'low'), ('mediumMin', 'medium'),
                         ('highMin', 'high'), ('urgentMin', 'urgent')):
            v = as_float(payload.get(src))
            if v is not None:
                bounds[dst] = v / 100.0
        if bounds:
            cfg['alert_bounds'] = bounds

        try:
            return list(self._system.apply_runtime_config(**cfg))
        except Exception as exc:  # noqa: BLE001
            # 不能静默吞掉：这个返回值会被接口原样回给前端当"已生效的参数"，
            # 一旦这里出错而返回 []，界面就只会说"已保存"，而实际的失败原因
            # 完全不可见 —— 「保存成功但不生效」正是这样产生的。
            logger.warning('apply_runtime_config failed: %s', exc)
            return []

    def load_ai_config_from_db(self) -> list[str]:
        """Read the persisted AI config and apply it (called after model load).

        **已知边界（进程级共享）**：推理引擎是进程单例，所有机构共用同一份
        参数，因此只能有一个机构的 `aiConfig` 真正驱动它。这里显式按
        `tenant_id` 升序取**第一个**，让"哪家说了算"变成**确定**的行为，
        并留下一条 warning。

        改之前是无 `ORDER BY` 的 `SELECT ... FROM settings` 取首个匹配：
        顺序由存储引擎决定，同一套数据在不同时刻可能命中不同机构 ——
        "租户 2 保存的参数永不生效、租户 1 的参数在所有机构生效"就是它造成的，
        而且没有任何日志提示。

        真正的修法是给引擎做租户维度（每家一份实例）或把它明确成平台级配置
        并由平台管理员维护，两者都属于产品决策；在那之前，
        **确定 + 有日志**比"看起来支持多租户、实际随机"要诚实得多。
        详见 docs/planning/11_多租户隔离设计.md 的「已知边界」。
        """
        try:
            from app.core.database import db
            rows = db.query(
                'SELECT tenant_id, setting_key, setting_value FROM settings '
                'WHERE setting_key IN (%s,%s,%s,%s) '
                'ORDER BY tenant_id ASC, id ASC LIMIT 1',
                ['aiConfig', 'ai_config', 'aiSettings', 'ai_settings'])
            if rows:
                logger.info('AI config loaded from tenant_id=%s '
                            '(engine is process-wide; other tenants share it)',
                            rows[0].get('tenant_id'))
        except Exception:
            return []
        # SQL 已经限定只取一条（见上面的 ORDER BY ... LIMIT 1），这里只需解析。
        for row in rows or []:
            raw = row.get('setting_value') or row.get('value')
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except Exception:
                    continue
            return self.apply_ai_config(raw)
        return []

    @staticmethod
    def _to_response(result: Any) -> dict[str, Any]:
        fall_info = result.fall_info or {}
        return {
            'keypoints': LocalAIEngine._native(result.keypoints.tolist() if result.keypoints is not None else []),
            'fallScore': float(result.fall_score),
            'painScore': float(result.pain_score),
            'alertLevel': result.alert_level.value,
            'expressions': [LocalAIEngine._convert_expression(item) for item in result.expressions],
            'faceAvailable': bool(result.face_available),
            'faceMethod': result.face_method,
            'faceBox': LocalAIEngine._native(result.face_box),
            'expressionState': LocalAIEngine._native(result.expression_state),
            'imageWidth': int(result.image_width),
            'imageHeight': int(result.image_height),
            'fallInfo': {LocalAIEngine._camel_case(k): LocalAIEngine._native(v) for k, v in fall_info.items()},
            'persons': [LocalAIEngine._native(item) for item in (result.persons or [])],
            'faces': [LocalAIEngine._native({LocalAIEngine._camel_case(k): v for k, v in item.items()}) for item in (result.faces or [])],
            'latencyMs': float(result.latency_ms),
        }

    @staticmethod
    def _convert_expression(item: dict[str, Any]) -> dict[str, Any]:
        converted = {LocalAIEngine._camel_case(k): LocalAIEngine._native(v) for k, v in item.items()}
        if 'className' not in converted and 'class_name' in item:
            converted['className'] = item['class_name']
        return converted

    @staticmethod
    def _native(value: Any) -> Any:
        if hasattr(value, 'item'):
            return value.item()
        if isinstance(value, list):
            return [LocalAIEngine._native(item) for item in value]
        if isinstance(value, tuple):
            return [LocalAIEngine._native(item) for item in value]
        if isinstance(value, dict):
            return {k: LocalAIEngine._native(v) for k, v in value.items()}
        return value

    @staticmethod
    def _camel_case(value: str) -> str:
        parts = value.split('_')
        return parts[0] + ''.join(part[:1].upper() + part[1:] for part in parts[1:])


_ai_engine: LocalAIEngine | None = None
_ai_engine_lock = Lock()


def get_ai_engine() -> LocalAIEngine:
    global _ai_engine
    if _ai_engine is None:
        with _ai_engine_lock:
            if _ai_engine is None:
                _ai_engine = LocalAIEngine(get_settings())
    return _ai_engine
