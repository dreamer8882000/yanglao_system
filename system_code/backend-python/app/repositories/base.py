import re
from typing import Any
from app.core.database import db
from app.core.tenant import context_tenant_id

TABLE_COLUMNS: dict[str, set[str]] = {
    'users': {'username', 'name', 'email', 'dept_name', 'avatar', 'password_hash', 'last_login_at', 'role'},
    'elders': {'name', 'gender', 'age', 'room_no', 'bed_no', 'admission_date', 'health_notes', 'contact_name', 'contact_phone', 'avatar', 'status'},
    'cameras': {'name', 'room_no', 'stream_url', 'source_type', 'status', 'last_heartbeat', 'offline_notified', 'yolo_enabled', 'yolo_model', 'yolo_models', 'model_weights', 'confidence_threshold', 'inference_fps', 'note'},
    # alerts 的证据明细列（迁移 004/009 加的）必须在这里全部列出。
    # 它们曾经全部缺失，后果是 `POST /alerts/ingest` 返回「告警已接收」
    # 而 posture_type / evidence_mode / fall_score / expression_top …**全落成 NULL**
    # —— 接口说成功、数据是错的。`/alerts/ingest` 的用途正是把证据一并收进来，
    # 所以这些列在这里是**应该**可写的。
    # 注意：alerts 没有走 crud_router（它有自己的路由），因此这个白名单的实际
    # 影响面只有 ingest 这一条 repo.insert 路径。
    'alerts': {'elder_id', 'camera_id', 'risk_level', 'confidence', 'alert_time', 'status',
               'handler_id', 'assigned_to', 'handler_notes', 'handled_at', 'escalated_at',
               # 证据明细
               'posture_type', 'evidence_mode', 'fall_score', 'pain_score',
               'torso_angle', 'knee_hip_ratio', 'pose_quality', 'body_keypoints',
               'rapid_descent', 'fall_state', 'track_id', 'fall_event_at',
               'expression_top', 'expression_confidence', 'expr_quality',
               'face_available', 'face_method', 'belief_fall', 'belief_unknown',
               # 身份判定（迁移 009）
               'identity_method', 'identity_confidence', 'identity_candidates'},
    'schedules': {'user_id', 'shift_date', 'shift_type', 'start_time', 'end_time', 'note', 'created_by'},
    'messages': {'user_id', 'type', 'title', 'content', 'related_id', 'is_read'},
    'audit_logs': {'user_id', 'username', 'action', 'resource_type', 'resource_id', 'detail', 'ip'},
    # task_id 必须可写：巡查记录要能关联到"产生它的那条巡查任务"，
    # 否则完成任务的闭环断在最后一步（记录里永远查不到它是哪次任务的结果）。
    'patrol_records': {'elder_id', 'patrol_time', 'nurse_id', 'location', 'notes', 'task_id'},
    'medications': {'elder_id', 'medication_name', 'dosage', 'frequency', 'time_slots', 'duration_days', 'notes', 'status', 'created_by'},
    'medication_records': {'medication_id', 'elder_id', 'scheduled_time', 'actual_time', 'nurse_id', 'status', 'notes'},
    'vital_signs': {'elder_id', 'record_time', 'systolic_pressure', 'diastolic_pressure', 'heart_rate', 'blood_glucose', 'temperature', 'spo2', 'weight', 'notes', 'recorder_id'},
    'settings': {'setting_key', 'setting_value'},
}

#: 需要按机构隔离的表。本表里**全部**业务表都带 tenant_id（settings 在迁移 006
#: 之后各自持有一份），唯一不在此列的是全局字典表 shifts（班次定义全平台一致）。
TENANT_SCOPED_TABLES = frozenset(TABLE_COLUMNS)

#: 租户列不参与 TABLE_COLUMNS 白名单校验 —— 它由仓库层统一注入，
#: 而不是由路由决定。放在白名单里会让"某个路由忘了传"变成一条 NOT NULL
#: 报错或（更糟）一条无归属的数据。
TENANT_COLUMN = 'tenant_id'


#: **明确不允许客户端写入**的列（必须写明原因）。
#:
#: 与 TABLE_COLUMNS 的关系是互补的：TABLE_COLUMNS 说"允许写"，这里说
#: "数据库里确实有、但绝不能由请求体决定"。schema 里的每一列都必须落在
#: 两者之一，否则就是被 _filter_data 静默丢弃的字段
#: （tests/test_repository_whitelist_drift.py 会强制这个覆盖关系）。
CLIENT_UNWRITABLE: dict[str, dict[str, str]] = {
    'users': {
        'is_platform':
            '平台级账号标记。若允许客户端写入，任何机构管理员都能把自己'
            '（或别人）提升为平台账号，从而看到所有机构的规模与安全事件 —— '
            '提权漏洞。只能由迁移脚本或直接运维改库。',
    },
}


COLUMN_ALIASES: dict[str, dict[str, str]] = {
    # 前端老人表单用的字段名（emergencyContact / emergencyPhone）与表列名
    # （contact_name / contact_phone）不一致，而白名单是按**列名**过滤的，
    # 于是这两个字段在 camelCase→snake_case 之后被静默丢弃：
    # 页面上填了紧急联系人，保存成功、界面不报错，库里却永远是空串。
    'elders': {'emergency_contact': 'contact_name', 'emergency_phone': 'contact_phone'},
    'patrol_records': {'room_no': 'location', 'patrol_by': 'nurse_id'},
    'medications': {'medicine_name': 'medication_name'},
    'medication_records': {'confirmed_by': 'nurse_id'},
    'vital_signs': {
        'blood_pressure_systolic': 'systolic_pressure',
        'blood_pressure_diastolic': 'diastolic_pressure',
        'oxygen_saturation': 'spo2',
        'recorded_at': 'record_time',
        'recorded_by': 'recorder_id',
    },
}


_SAFE_ORDER_COLUMN_RE = re.compile(r'^[a-z_][a-z0-9_]*(\s+(ASC|DESC))?$', re.IGNORECASE)


def _safe_order_by(order_by: str, default: str = 'id DESC') -> str:
    parts = [p.strip() for p in order_by.split(',')]
    if all(_SAFE_ORDER_COLUMN_RE.match(p) for p in parts):
        return order_by
    return default


def snake_to_camel(name: str) -> str:
    return re.sub(r'_([a-z])', lambda m: m.group(1).upper(), name)


def camel_to_snake(name: str) -> str:
    return re.sub(r'(?<!^)([A-Z])', r'_\1', name).lower()


def keys_to_camel(value: Any) -> Any:
    if isinstance(value, list):
        return [keys_to_camel(item) for item in value]
    if isinstance(value, dict):
        return {snake_to_camel(k): keys_to_camel(v) for k, v in value.items()}
    return value


def keys_to_snake(value: dict[str, Any]) -> dict[str, Any]:
    return {camel_to_snake(k): v for k, v in value.items() if v is not None}


class BaseRepository:
    def __init__(self, table_name: str):
        if table_name not in TABLE_COLUMNS:
            raise ValueError(f'Unsupported table: {table_name}')
        self.table_name = table_name
        self.allowed_columns = TABLE_COLUMNS[table_name]
        self.tenant_scoped = table_name in TENANT_SCOPED_TABLES

    def _filter_data(self, data: dict[str, Any]) -> dict[str, Any]:
        aliases = COLUMN_ALIASES.get(self.table_name, {})
        snake_data = {aliases.get(k, k): v for k, v in keys_to_snake(data).items()}
        out = {k: v for k, v in snake_data.items() if k in self.allowed_columns}
        # tenant_id 不走白名单：它是仓库层管理的元数据，不是业务字段。
        # 之前漏掉这一步的后果很隐蔽 —— 路由写 `payload['tenant_id'] = ...`
        # 会被白名单**静默丢弃**，插入随即撞上 NOT NULL 约束报 500，
        # 而错误信息完全看不出是租户字段被过滤掉了。
        if TENANT_COLUMN in snake_data:
            out[TENANT_COLUMN] = snake_data[TENANT_COLUMN]
        return out

    def query(self, sql: str, params: list[Any] | None = None, camel: bool = True) -> Any:
        rows = db.query(sql, params or [])
        return keys_to_camel(rows) if camel else rows

    def find_by_id(self, item_id: int) -> dict[str, Any] | None:
        rows = self.query(f'SELECT * FROM {self.table_name} WHERE id=%s LIMIT 1', [item_id])
        return rows[0] if rows else None

    def find_all(self, where: str = '', params: list[Any] | None = None, order_by: str = 'id DESC', limit: int = 100) -> list[dict[str, Any]]:
        sql = f'SELECT * FROM {self.table_name}'
        if where:
            sql += f' WHERE {where}'
        safe_ob = _safe_order_by(order_by)
        if safe_ob:
            sql += f' ORDER BY {safe_ob}'
        sql += ' LIMIT %s'
        return self.query(sql, (params or []) + [min(max(limit, 1), 500)])

    def paginate(self, page: int = 1, page_size: int = 20, where: str = '', params: list[Any] | None = None, order_by: str = 'id DESC') -> dict[str, Any]:
        page = max(1, int(page or 1))
        page_size = min(100, max(1, int(page_size or 20)))
        sql = f'SELECT * FROM {self.table_name}'
        count_sql = f'SELECT COUNT(*) AS cnt FROM {self.table_name}'
        if where:
            sql += f' WHERE {where}'
            count_sql += f' WHERE {where}'
        safe_ob = _safe_order_by(order_by)
        if safe_ob:
            sql += f' ORDER BY {safe_ob}'
        sql += ' LIMIT %s OFFSET %s'
        args = params or []
        data = self.query(sql, args + [page_size, (page - 1) * page_size])
        total_rows = self.query(count_sql, args)
        total = int(total_rows[0].get('cnt') or 0) if total_rows else 0
        return {'data': data, 'total': total, 'page': page, 'pageSize': page_size}

    def insert(self, data: dict[str, Any]) -> dict[str, Any] | None:
        snake_data = self._filter_data(data)
        if self.tenant_scoped and TENANT_COLUMN not in snake_data:
            # 由**当前请求上下文**注入，而不是信任调用方传进来的值：
            # 客户端若能自报 tenant_id，隔离就形同虚设。
            snake_data[TENANT_COLUMN] = context_tenant_id()
        if not snake_data:
            raise ValueError('没有可创建的数据')
        keys = list(snake_data.keys())
        placeholders = ','.join(['%s'] * len(keys))
        sql = f"INSERT INTO {self.table_name} ({','.join(keys)}) VALUES ({placeholders})"
        new_id = db.insert(sql, [snake_data[k] for k in keys])
        return self.find_by_id(new_id)

    def update(self, item_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        # tenant_id 从 _filter_data 出来后会被丢弃，这里显式剔除，
        # 保证通用更新**永远无法**把一条记录搬到另一个机构去。
        snake_data = self._filter_data(data)
        snake_data.pop(TENANT_COLUMN, None)
        if not snake_data:
            return self.find_by_id(item_id)
        keys = list(snake_data.keys())
        sets = ', '.join([f'{k}=%s' for k in keys])
        db.execute(f'UPDATE {self.table_name} SET {sets} WHERE id=%s', [snake_data[k] for k in keys] + [item_id])
        return self.find_by_id(item_id)

    def delete(self, item_id: int) -> bool:
        db.execute(f'DELETE FROM {self.table_name} WHERE id=%s', [item_id])
        return True

    def count(self, where: str = '', params: list[Any] | None = None) -> int:
        sql = f'SELECT COUNT(*) AS cnt FROM {self.table_name}'
        if where:
            sql += f' WHERE {where}'
        rows = self.query(sql, params or [])
        return int(rows[0].get('cnt') or 0) if rows else 0
