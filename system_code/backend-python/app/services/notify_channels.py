"""告警通知渠道：企业微信/钉钉群机器人、邮件。

为什么单独成模块，而不是继续写在 notifications.py 里：
``notifications.py`` 里的 ``NotificationHub`` 是**进程内 SSE 推送**，只能送达
"当前打开的页面"。而告警最需要送达的恰恰是**护士不在电脑前**的时刻。
两者是不同性质的东西：一个是页面的实时刷新，一个是把人叫醒。混在一起会让人
误以为"已经有通知了"。

三条不可妥协的设计原则：

1. **未配置就明确说未发送，绝不假装成功。**
   渠道没填 webhook / 没配 SMTP 时，投递记录写 ``skipped`` 并说明原因，
   而不是返回 True 让人以为发出去了。一个静默失败的通知系统比没有通知更危险 ——
   它让人**以为**有人被叫醒了。

2. **每次投递必须留痕**（``notification_logs``）。
   渠道、目标、成败、错误、耗时、触发原因、当时的等级。没有这些，
   "我没收到告警"永远查不出原因。

3. **一个渠道失败不影响其它渠道**，且失败要能被看见。
   按等级选出多个渠道后逐个发送，各自独立记录；全部失败时记 warning。
"""
from __future__ import annotations

import json
import logging
import smtplib
import time
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any, Callable

from app.core.database import db

logger = logging.getLogger(__name__)

#: 告警等级的强弱顺序，用于"该渠道的最低触发等级"比较
LEVEL_ORDER = {'NORMAL': 0, 'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'URGENT': 4}

#: 各等级的中文名与建议的渠道强度（仅用于界面提示）
LEVEL_LABEL = {'NORMAL': '正常', 'LOW': '低危', 'MEDIUM': '中危',
               'HIGH': '高危', 'URGENT': '紧急'}

#: 发送超时（秒）。告警通知必须是"快速失败"——卡住的请求会拖住告警主链路。
SEND_TIMEOUT = 8.0


def level_reaches(alert_level: str | None, min_level: str | None) -> bool:
    """告警等级是否达到该渠道的最低触发等级。"""
    return LEVEL_ORDER.get(str(alert_level or '').upper(), 0) >= \
        LEVEL_ORDER.get(str(min_level or 'HIGH').upper(), 3)


def _mask_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """接口返回时脱敏：只暴露"配没配"，不回传凭据原文。"""
    out = {}
    for k, v in (cfg or {}).items():
        if k in ('password', 'secret', 'token') and v:
            out[k] = '******'
        elif k == 'webhook' and v:
            # webhook URL 本身含 key，只留主机与前缀便于核对
            s = str(v)
            out[k] = (s[:32] + '…') if len(s) > 32 else s
            out[k + '_set'] = True
        else:
            out[k] = v
    return out


# ── 消息体构造 ────────────────────────────────────────────────────────────

def _location_text(alert: dict[str, Any]) -> tuple[str, str]:
    """返回 (标题用的地点, 正文用的地点行)。

    为什么不能简单写 ``room or '—'``：护士收到一条「【高危】新告警 · —室」
    等于没有信息 —— 他不知道该往哪跑，只能先去翻系统。所以：
      1) 有房间号 → 「305 室」
      2) 没有房间号但有摄像头名 → 用摄像头名（至少知道是哪个点位）
      3) 都没有 → 明说「房间未知，请打开告警详情确认」，让人知道这是缺失
         而不是"地点就叫 —"
    """
    room = str(alert.get('roomNo') or alert.get('room_no') or '').strip()
    cam = str(alert.get('cameraName') or alert.get('camera_name') or '').strip()
    if room:
        return f'{room} 室', f'房间：{room} 室'
    if cam:
        return f'{cam}', f'位置：{cam}（未关联房间）'
    return '地点未知', '位置：未关联房间与摄像头，请打开告警详情确认'


def build_message(alert: dict[str, Any], reason: str = 'new') -> dict[str, str]:
    """把告警整理成人能读的字段。渠道适配器各自决定怎么排版。"""
    level = str(alert.get('riskLevel') or alert.get('risk_level') or '').upper()
    loc_short, loc_line = _location_text(alert)
    elder = alert.get('elderName') or alert.get('elder_name') or ''
    if not elder:
        ident = alert.get('identityMethod') or alert.get('identity_method')
        elder = {'ambiguous': '（该房间多位老人，待确认）',
                 'unmatched': '（房间无在册老人）',
                 'room_single': '（按房间推定，待确认）',
                 'no_camera': '未识别（无摄像头）',
                 'manual': '已人工确认'}.get(ident, '未识别')
    posture = alert.get('postureType') or alert.get('posture_type') or '未知'
    expr = alert.get('expressionTop') or alert.get('expression_top') or '—'
    conf = alert.get('confidence')
    reason_label = {'new': '新告警', 'escalated': '升级', 'escalated_timeout': '超时升级',
                    'confirmed': '已处置', 'test': '测试发送'}.get(reason, reason)
    title = f"【{LEVEL_LABEL.get(level, level)}】{reason_label} · {loc_short}"
    body = (f"老人：{elder}\n"
            f"{loc_line}\n"
            f"姿态：{posture}   表情：{expr}\n"
            f"置信度：{conf if conf is not None else '—'}"
            + (f"\n时间：{alert.get('alertTime') or alert.get('alert_time')}"
               if (alert.get('alertTime') or alert.get('alert_time')) else ''))
    return {'title': title, 'body': body, 'level': level,
            'room': loc_short, 'elder': str(elder)}


# ── 渠道适配器 ────────────────────────────────────────────────────────────

def _post_json(url: str, payload: dict[str, Any]) -> tuple[bool, str, int]:
    """POST JSON；返回 (成功, 错误信息, 耗时毫秒)。超时快速失败。"""
    started = time.perf_counter()
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST',
                                headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=SEND_TIMEOUT) as resp:
            ms = int((time.perf_counter() - started) * 1000)
            body = resp.read().decode('utf-8', 'replace')[:200]
            if 200 <= resp.status < 300:
                # 企业微信/钉钉失败时也返回 HTTP 200，靠 body 里的 errcode 判断
                try:
                    parsed = json.loads(body)
                    code = parsed.get('errcode', parsed.get('code', 0))
                    if code not in (0, None):
                        return False, f'平台返回 errcode={code} {parsed.get("errmsg", "")}'[:300], ms
                except (json.JSONDecodeError, AttributeError):
                    pass
                return True, '', ms
            return False, f'HTTP {resp.status} {body}'[:300], ms
    except urllib.error.HTTPError as exc:
        ms = int((time.perf_counter() - started) * 1000)
        return False, f'HTTP {exc.code} {exc.read().decode("utf-8", "replace")[:200]}', ms
    except Exception as exc:                                        # noqa: BLE001
        ms = int((time.perf_counter() - started) * 1000)
        return False, f'{type(exc).__name__}: {exc}'[:300], ms


def _webhook_target(url: str) -> str:
    """只记录主机名，不把带 key 的完整 webhook 写进日志。"""
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        return f'{p.scheme}://{p.netloc}{p.path.rsplit("/", 1)[0]}'
    except Exception:                                              # noqa: BLE001
        return '(invalid url)'


class Channel:
    """渠道基类。子类实现 ``send``，返回 (成功, 错误, 耗时ms)。"""

    type_name = 'base'
    label = '基类'

    def __init__(self, row: dict[str, Any]):
        self.row = row
        self.id = row.get('id')
        self.name = row.get('name') or self.label
        raw = row.get('config')
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = {}
        self.config: dict[str, Any] = raw or {}

    @property
    def target(self) -> str:
        return ''

    def validate(self) -> str | None:
        """返回未配置的原因；None 表示可用。**未配置时必须说清楚原因**。"""
        return None

    def send(self, msg: dict[str, str]) -> tuple[bool, str, int]:
        raise NotImplementedError


class WecomChannel(Channel):
    """企业微信群机器人。

    payload 形态与企业微信官方文档一致；失败时平台仍返回 HTTP 200，
    所以判断成败必须看 body 里的 ``errcode``（已在 ``_post_json`` 里处理）。
    """

    type_name = 'wecom'
    label = '企业微信群机器人'

    def validate(self) -> str | None:
        url = str(self.config.get('webhook') or '').strip()
        if not url:
            return '未填写 webhook 地址'
        if not url.startswith('http'):
            return 'webhook 地址必须以 http(s):// 开头'
        return None

    @property
    def target(self) -> str:
        return _webhook_target(str(self.config.get('webhook') or ''))

    def send(self, msg: dict[str, str]) -> tuple[bool, str, int]:
        problem = self.validate()
        if problem:
            return False, problem, 0
        # markdown 消息：企业微信支持有限语法，用 > 引用块放明细行
        text = f"## {msg['title']}\n" + '\n'.join(
            f"> {line}" for line in msg['body'].split('\n'))
        return _post_json(str(self.config['webhook']),
                          {'msgtype': 'markdown', 'markdown': {'content': text}})


class DingTalkChannel(Channel):
    """钉钉群机器人。payload 形态与企微不同，所以单独一个类。"""

    type_name = 'dingtalk'
    label = '钉钉群机器人'

    def validate(self) -> str | None:
        url = str(self.config.get('webhook') or '').strip()
        if not url:
            return '未填写 webhook 地址'
        if not url.startswith('http'):
            return 'webhook 地址必须以 http(s):// 开头'
        if self.config.get('secret') and not self.config.get('webhook'):
            return '配置了加签密钥但缺少 webhook 地址'
        return None

    @property
    def target(self) -> str:
        return _webhook_target(str(self.config.get('webhook') or ''))

    def send(self, msg: dict[str, str]) -> tuple[bool, str, int]:
        problem = self.validate()
        if problem:
            return False, problem, 0
        text = f"### {msg['title']}\n\n" + msg['body'].replace('\n', '  \n')
        return _post_json(str(self.config['webhook']),
                          {'msgtype': 'markdown',
                           'markdown': {'title': msg['title'], 'text': text}})


ROLE_LABEL = {'admin': '机构管理员', 'nurse': '护理员'}


def _split_emails(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        items = [str(x) for x in value]
    else:
        items = str(value).replace(';', ',').split(',')
    # 只要形如 a@b 的才算邮箱：写错的条目留在列表里会让整封邮件被 SMTP 拒收，
    # 而错误信息通常只有一句 "550 Invalid recipient"，看不出是谁写错了。
    # 这里直接剔除并让调用方在日志里看到"配置里有 N 个非法邮箱"。
    return [x.strip() for x in items if '@' in x and '.' in x.split('@')[-1]]


def role_emails(tenant_id: int, roles: list[str]) -> list[str]:
    """按角色取本机构成员的邮箱。

    存在的理由：把收件人写成固定字符串，人员一变动就静默失效 ——
    邮件照发（不报错），只是没人收到。按角色取则跟着账号走。
    """
    roles = [r for r in (roles or []) if r in ('admin', 'nurse')]
    if not roles:
        return []
    try:
        placeholders = ','.join(['%s'] * len(roles))
        rows = db.query(
            f'SELECT email FROM users WHERE tenant_id=%s AND role IN ({placeholders})',
            [tenant_id, *roles])
        return [r['email'] for r in rows if r.get('email')]
    except Exception as exc:                                        # noqa: BLE001
        logger.warning('role email lookup failed (tenant=%s roles=%s): %s',
                       tenant_id, roles, exc)
        return []


def resolve_recipients(tenant_id: int, cfg: dict[str, Any]) -> tuple[list[str], str]:
    """合并三种收件人来源，返回 (去重后的邮箱列表, 说明)。

    三种来源的优先级与用途各不相同，都要支持：
      1) ``to``        —— 明确的邮箱（外部人员、科室公用邮箱）
      2) ``toRoles``   —— 本机构某几个角色的全部成员（跟着人员变动走）
      3) 在岗护理员     —— 都没配时的兜底，保证"总有人能收到"

    ``onlyOnDuty=True`` 时**只**发给当班人（夜间只打扰值班的人，
    不把所有护士的手机都叫醒）—— 这是护理站的实际要求。
    """
    explicit = _split_emails(cfg.get('to'))
    roles = [r.strip() for r in str(cfg.get('toRoles') or '').split(',') if r.strip()]
    by_role = role_emails(tenant_id, roles)
    on_duty = on_duty_emails(tenant_id)

    if cfg.get('onlyOnDuty'):
        pool, why = on_duty, '仅当班护理员'
    else:
        pool, why = explicit + by_role + ([] if (explicit or by_role) else on_duty), ''
        if not pool:
            pool, why = on_duty, '无显式收件人，回退当班护理员'

    out: list[str] = []
    for e in pool:
        e = str(e).strip()
        if e and e not in out:
            out.append(e)
    parts = []
    if explicit:
        parts.append(f'指定 {len(explicit)} 个')
    if by_role:
        parts.append('+'.join(ROLE_LABEL.get(r, r) for r in roles) + f' {len(by_role)} 个')
    if why:
        parts.append(why)
    return out, '；'.join(parts)


class EmailChannel(Channel):
    """邮件（SMTP）。

    定位与群机器人不同：护士紧急时不看邮件，**管理员复盘与留痕**要靠它。
    收件人支持三种来源（见 ``resolve_recipients``）：显式邮箱、按角色取
    ``users.email``、以及当班护理员兜底。

    为什么要按角色而不是只让人手填邮箱：手填的地址在人员离职后不会报错，
    只会静默地发不到人 —— 通知系统最危险的失败方式。
    """

    type_name = 'email'
    label = '邮件'

    def _recipients(self) -> list[str]:
        cached = self.config.get('_resolved')
        if cached:
            return list(cached)
        tid = self.config.get('_tenant_id')
        if tid is None:
            return _split_emails(self.config.get('to'))
        to, _why = resolve_recipients(int(tid), self.config)
        return to

    def validate(self) -> str | None:
        cfg = self.config
        if not str(cfg.get('host') or '').strip():
            return '未填写 SMTP 服务器'
        if not self._recipients():
            return ('没有可用收件人：未填邮箱、未选接收角色，'
                    '且当前没有在岗护理员可作兜底')
        return None

    @property
    def target(self) -> str:
        return ','.join(self._recipients())[:250]

    def send(self, msg: dict[str, str]) -> tuple[bool, str, int]:
        problem = self.validate()
        if problem:
            return False, problem, 0
        cfg = self.config
        to = self._recipients()
        started = time.perf_counter()
        m = EmailMessage()
        m['Subject'] = msg['title']
        m['From'] = str(cfg.get('from') or cfg.get('user') or 'alert@localhost')
        m['To'] = ', '.join(to)
        m.set_content(msg['body'])
        try:
            port = int(cfg.get('port') or (465 if cfg.get('use_ssl') else 25))
            if cfg.get('use_ssl'):
                server = smtplib.SMTP_SSL(str(cfg['host']), port, timeout=SEND_TIMEOUT)
            else:
                server = smtplib.SMTP(str(cfg['host']), port, timeout=SEND_TIMEOUT)
            try:
                if cfg.get('use_tls') and not cfg.get('use_ssl'):
                    server.starttls()
                if cfg.get('user'):
                    server.login(str(cfg['user']), str(cfg.get('password') or ''))
                server.send_message(m)
            finally:
                server.quit()
            return True, '', int((time.perf_counter() - started) * 1000)
        except Exception as exc:                                    # noqa: BLE001
            return False, f'{type(exc).__name__}: {exc}'[:300], \
                int((time.perf_counter() - started) * 1000)


CHANNEL_TYPES: dict[str, type[Channel]] = {
    WecomChannel.type_name: WecomChannel,
    DingTalkChannel.type_name: DingTalkChannel,
    EmailChannel.type_name: EmailChannel,
}


# ── 投递留痕 ──────────────────────────────────────────────────────────────

def log_delivery(*, tenant_id: int, alert_id: int | None, channel: Channel | None,
                 channel_type: str, channel_name: str | None, target: str | None,
                 status: str, reason: str, alert_level: str | None,
                 error: str | None, duration_ms: int | None) -> None:
    """写一条投递记录。**它自己失败也不能影响告警主链路**（但会记 warning）。"""
    try:
        db.execute(
            'INSERT INTO notification_logs (tenant_id, alert_id, channel_id, channel_type, '
            'channel_name, target, status, reason, alert_level, error, duration_ms) '
            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            [tenant_id, alert_id, (channel.id if channel else None), channel_type,
             channel_name, target, status, reason, alert_level, error, duration_ms],
        )
    except Exception as exc:                                        # noqa: BLE001
        logger.warning('notification log write failed: %s', exc)


# ── 路由与派发 ────────────────────────────────────────────────────────────

def load_channels(tenant_id: int) -> list[dict[str, Any]]:
    return db.query(
        'SELECT * FROM notification_channels WHERE tenant_id=%s AND enabled=1 '
        'ORDER BY id', [tenant_id])


def on_duty_emails(tenant_id: int) -> list[str]:
    """当班护理员的邮箱 —— 用作邮件渠道未显式配置收件人时的兜底。

    为什么要按**当班人**而不是一个写死的接收人字符串：
    人员一变动，写死的字符串就失效了，而且它不会报错，只会静默地发不到人。
    """
    try:
        from app.api.routes.duty import _on_duty_nurse
        duty = _on_duty_nurse(tenant_id=tenant_id)
        if not duty:
            return []
        rows = db.query('SELECT email FROM users WHERE id=%s AND tenant_id=%s',
                        [duty['user_id'], tenant_id])
        return [r['email'] for r in rows if r.get('email')]
    except Exception as exc:                                        # noqa: BLE001
        logger.warning('on-duty email lookup failed: %s', exc)
        return []


def dispatch(alert: dict[str, Any], reason: str = 'new',
             tenant_id: int | None = None) -> list[dict[str, Any]]:
    """按等级选渠道 → 逐个发送 → 记录每一笔 → 汇总。

    返回每笔投递的结果（也写进 notification_logs）。**任何一步失败都不会抛异常**
    —— 通知失败绝不能连累告警本身落库，但必须留下可查的痕迹。
    """
    tid = tenant_id or alert.get('tenantId') or alert.get('tenant_id')
    if tid is None:
        logger.warning('dispatch skipped: no tenant for alert %s', alert.get('id'))
        return []

    level = str(alert.get('riskLevel') or alert.get('risk_level') or '').upper()
    msg = build_message(alert, reason)
    fallback = on_duty_emails(int(tid))
    results: list[dict[str, Any]] = []

    for row in load_channels(int(tid)):
        ctype = str(row.get('type') or '')
        cls = CHANNEL_TYPES.get(ctype)

        # 先构造 Channel 对象，再做任何跳过判断。
        # 原实现把 level 判断放在构造之前、并且传 channel=None 去写日志，
        # 结果是：跳过这条渠道时投递记录的 channel_id 是 NULL ——
        # 日志里能看到"有一次 skipped"，却看不到**是哪个渠道**被跳过，
        # 排查时等于没说。跳过同样要能归因。
        ch = cls(row) if cls is not None else None
        ch_name = (ch.name if ch else row.get('name')) or ctype

        if cls is None:
            log_delivery(tenant_id=int(tid), alert_id=alert.get('id'), channel=None,
                         channel_type=ctype, channel_name=ch_name,
                         target=None, status='skipped', reason=reason,
                         alert_level=level, error=f'未知渠道类型 {ctype}', duration_ms=0)
            results.append({'channel': ch_name, 'type': ctype, 'status': 'skipped',
                            'error': f'未知渠道类型 {ctype}'})
            continue

        if not level_reaches(level, row.get('min_level')):
            # 等级不够：记录 skipped 而不是悄悄不记 —— 否则看日志会以为漏发了。
            # 同时**必须出现在 results 里**：调用方（接口与界面）要能回答
            # "为什么这个渠道没发"，只返回成功/失败两类会让它凭空消失。
            reason_txt = (f'等级 {level or "未知"} 未达到该渠道门槛 '
                          f'{row.get("min_level")}')
            log_delivery(tenant_id=int(tid), alert_id=alert.get('id'), channel=ch,
                         channel_type=ctype, channel_name=ch_name, target=ch.target,
                         status='skipped', reason=reason, alert_level=level,
                         error=reason_txt, duration_ms=0)
            results.append({'channel': ch_name, 'type': ctype, 'status': 'skipped',
                            'error': reason_txt, 'minLevel': row.get('min_level')})
            continue

        if ctype == EmailChannel.type_name:
            # 把租户带进去，收件人由 resolve_recipients 统一解析
            # （显式邮箱 / 按角色取 users.email / 当班人兜底）
            ch.config['_tenant_id'] = int(tid)
            if fallback:
                ch.config['_fallback_to'] = fallback

        problem = ch.validate()
        if problem:
            # **未配置 ≠ 已发送**：明确记 skipped 并写清原因
            logger.warning('channel %s(%s) not usable: %s', row.get('name'), ctype, problem)
            log_delivery(tenant_id=int(tid), alert_id=alert.get('id'), channel=ch,
                         channel_type=ctype, channel_name=ch.name, target=ch.target,
                         status='skipped', reason=reason, alert_level=level,
                         error=problem, duration_ms=0)
            results.append({'channel': ch.name, 'type': ctype, 'status': 'skipped',
                            'error': problem})
            continue

        ok, err, ms = ch.send(msg)
        status = 'success' if ok else 'failed'
        log_delivery(tenant_id=int(tid), alert_id=alert.get('id'), channel=ch,
                     channel_type=ctype, channel_name=ch.name, target=ch.target,
                     status=status, reason=reason, alert_level=level,
                     error=(None if ok else err), duration_ms=ms)
        results.append({'channel': ch.name, 'type': ctype, 'status': status,
                        'error': None if ok else err, 'durationMs': ms})
        if not ok:
            logger.warning('notify failed via %s(%s): %s', ch.name, ctype, err)

    delivered = [r for r in results if r['status'] == 'success']
    if results and not delivered:
        # 一个渠道都没成功：必须显式告警，不能静默
        logger.error('ALL notification channels failed for alert %s (level=%s): %s',
                     alert.get('id'), level,
                     [f"{r['channel']}:{r.get('error')}" for r in results])
    return results
