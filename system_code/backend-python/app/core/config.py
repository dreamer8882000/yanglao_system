from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

# Load environment overrides from a gitignored .env if present, so secrets
# never live in the committed source. Must run before Settings is defined.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / '.env')
except Exception:
    pass


def _find_root_dir() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / 'expression_recognition').exists():
            return parent
    return current.parents[2]


ROOT_DIR = _find_root_dir()
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


@dataclass(frozen=True)
class Settings:
    env: str = os.getenv('APP_ENV', os.getenv('NODE_ENV', 'development'))
    app_name: str = os.getenv('APP_NAME', '智慧养老告警系统')
    app_version: str = os.getenv('APP_VERSION', '1.0.0')
    host: str = os.getenv('HOST', '0.0.0.0')
    port: int = _int_env('PORT', 8090)
    api_base_path: str = os.getenv('API_BASE_PATH', '/api')

    db_host: str = os.getenv('DB_HOST', 'localhost')
    db_port: int = _int_env('DB_PORT', 3306)
    db_user: str = os.getenv('DB_USER', 'root')
    db_password: str = os.getenv('DB_PASSWORD', '')
    db_name: str = os.getenv('DB_NAME', 'elderly_care_sbbr0v5jespt')

    jwt_secret: str = os.getenv('JWT_SECRET', '')
    jwt_algorithm: str = os.getenv('JWT_ALGORITHM', 'HS256')
    jwt_expire_minutes: int = _int_env('JWT_EXPIRE_MINUTES', 60 * 24)

    # 工程部署：YOLO26-l-pose（Ultralytics 最新一代，n/s/m/l 全档实测见
    # docs/planning/10_姿态模型整体对比_YOLOv8l_vs_YOLO26.md）。
    # 与 YOLOv8l-pose 在同一评测协议下对比（URFD 侧视 30 跌倒 + 40 日常）：
    #   参数   44.5M → 28.6M（-36%）
    #   误报   8.0%  → 2.5%（3.2 倍改善）
    #   确认率 30%   → 30%（持平）
    #   召回   73%   → 67%（-6pp，代价）
    # 养老监护场景中误报的代价是"告警疲劳"（护理员被假警拖垮后忽略真警），
    # 实际后果重于单次漏检，故取精确率优先。
    # 论文贡献模型（第3章 YOLOv8s+BiFPN 消融产物）仍是 pose_bifpn_best.pt；
    # 需要更高召回时回退 yolov8l-pose.pt，需要论文模型时改 pose_bifpn_best.pt。
    ai_pose_model_path: str = os.getenv(
        'AI_POSE_MODEL_PATH',
        str(ROOT_DIR / 'thesis_assets' / 'pose' / 'weights' / 'yolo26l-pose.pt'),
    )
    # 2 类（平静/痛苦）微调模型 —— 基于 expr_lka_best.pt 的骨干微调而来，
    # 是"痛苦检测"这一系统目标的直接对口模型；8 类映射存在"平静被误判成悲伤"
    # 等合成脸域不匹配问题。pain 权重在 system.py 里已对齐（痛苦=1.0 / 平静=0.0）。
    ai_expr_model_path: str = os.getenv(
        'AI_EXPR_MODEL_PATH',
        str(ROOT_DIR / 'runs' / 'detect' / 'data' / 'pain2_run'
            / 'train' / 'weights' / 'best.pt'),
    )
    ai_device: str = os.getenv('AI_DEVICE', 'auto')
    ai_fall_threshold: float = _float_env('AI_FALL_THRESHOLD', 0.3)
    ai_pose_conf: float = _float_env('AI_POSE_CONF', 0.12)
    ai_pose_iou: float = _float_env('AI_POSE_IOU', 0.45)
    # 姿态推理输入尺寸：640 → 480。
    # 实测在自采数据（1080×1920 竖屏、中距）上 480 与 640 关键点完全一致
    # （17/17、置信度 0.98），但姿态耗时从 30ms 降到 20ms，配合人脸降频把
    # 骨架更新率从 ~20fps 提到 ~30fps。远处小目标若退化可调回 640。
    ai_pose_imgsz: int = _int_env('AI_POSE_IMGSZ', 480)
    ai_pose_max_det: int = _int_env('AI_POSE_MAX_DET', 3)
    ai_expr_conf: float = _float_env('AI_EXPR_CONF', 0.25)
    # 时序融合跌倒模型（骨架时序 CNN + 画面几何 + 表情证据）。
    # 默认指向用自建数据训练出的权重；设成空字符串则回退到几何规则。
    ai_fall_model_path: str = os.getenv(
        'AI_FALL_MODEL_PATH',
        str(ROOT_DIR / 'data' / 'processed' / 'self' / 'fall_fusion.pt'),
    )
    ai_fall_model_smooth: float = _float_env('AI_FALL_MODEL_SMOOTH', 0.6)
    ai_allow_remote_image: bool = _bool_env('AI_ALLOW_REMOTE_IMAGE', False)
    ai_allowed_image_root: str = os.getenv('AI_ALLOWED_IMAGE_ROOT', str(BACKEND_DIR / 'uploads'))

    cors_origins: str = os.getenv('CORS_ORIGINS', '*')

    deepseek_api_key: str = os.getenv('DEEPSEEK_API_KEY', '')
    deepseek_base_url: str = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    deepseek_model: str = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')

    # Unhandled-alert auto-escalation.
    alert_escalate_after_minutes: int = _int_env('ALERT_ESCALATE_AFTER_MINUTES', 10)
    alert_escalate_interval_minutes: int = _int_env('ALERT_ESCALATE_INTERVAL_MINUTES', 5)

    # Login throttling (brute-force protection).
    login_max_attempts: int = _int_env('LOGIN_MAX_ATTEMPTS', 5)
    login_window_minutes: int = _int_env('LOGIN_WINDOW_MINUTES', 10)
    login_lockout_minutes: int = _int_env('LOGIN_LOCKOUT_MINUTES', 10)

    def validate(self) -> None:
        if self.env.lower() in {'production', 'prod'}:
            weak = {'', 'jwt-secret-key', 'change-me-in-production'}
            if self.jwt_secret in weak or len(self.jwt_secret) < 32:
                raise RuntimeError('生产环境必须设置长度不少于 32 位的 JWT_SECRET')
            if not self.db_password:
                raise RuntimeError('生产环境必须设置 DB_PASSWORD')

    @property
    def database_kwargs(self) -> dict:
        return {
            'host': self.db_host,
            'port': self.db_port,
            'user': self.db_user,
            'password': self.db_password,
            'database': self.db_name,
            'charset': 'utf8mb4',
            'autocommit': True,
        }


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate()
    return settings
