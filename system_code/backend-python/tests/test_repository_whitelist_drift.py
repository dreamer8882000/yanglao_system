"""仓库白名单必须与数据库 schema 保持同步。

**为什么需要这条测试**：`TABLE_COLUMNS` 是一份手写的插入/更新白名单，
`_filter_data` 会**静默丢弃**不在其中的键。这个机制已经造成过三次真实事故：
  * `tenant_id`   被丢 → 插入撞 NOT NULL，报一句与租户毫无关系的 500；
  * `bed_no`      被丢 → 床位号永远是默认值，双人间加人撞唯一键；
  * 22 个告警证据列被丢 → `POST /alerts/ingest` 返回「告警已接收」，
    而 posture_type / evidence_mode / fall_score / expression_top …**全部落库为 NULL**。
    这些列正是迁移 004/009 为了「效果评测能回答哪类几何特征在误报」而加的。

每一次的表现都一样：**接口说成功，数据是错的**。人眼审查抓不住，
因为要逐列比对 schema 与一份硬编码列表。

所以把它变成断言：白名单允许比 schema **多**（历史列可以保留），
但**不允许少** —— 少了就意味着有一个字段正在被静默吞掉。
"""
from __future__ import annotations

import pytest

from app.core.database import db
from app.repositories.base import CLIENT_UNWRITABLE, TABLE_COLUMNS

#: 这些列由仓库层/数据库自行管理，不参与白名单
META_COLUMNS = {'id', 'created_at', 'updated_at', 'tenant_id'}


def _schema_columns(table: str) -> set[str]:
    rows = db.query(
        'SELECT COLUMN_NAME AS c FROM information_schema.COLUMNS '
        'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', [table])
    return {r['c'] for r in rows} - META_COLUMNS


@pytest.mark.parametrize('table', sorted(TABLE_COLUMNS))
def test_whitelist_covers_every_business_column(table: str) -> None:
    """白名单必须覆盖该表除元数据列以外的**所有**列。

    不覆盖 = 那个字段通过通用 CRUD 写入时会被静默丢弃。
    """
    schema = _schema_columns(table)
    if not schema:
        pytest.skip(f'{table} 表不存在')
    # 明确拒绝写入的列（如 users.is_platform）不算"被静默丢弃"：
    # 它们在 CLIENT_UNWRITABLE 里写清了原因，且**不应该**可写。
    missing = sorted(schema - TABLE_COLUMNS[table] - set(CLIENT_UNWRITABLE.get(table, {})))
    assert not missing, (
        f'{table} 的白名单缺少 {len(missing)} 列，这些字段会被 _filter_data 静默丢弃：\n'
        f'  {missing}\n'
        f'修法：把它们补进 TABLE_COLUMNS["{table}"]；'
        f'若某列确实不该由客户端写，请在 base.py 的拒绝名单里显式说明原因。'
    )


def test_whitelist_has_no_unknown_columns() -> None:
    """白名单里不能出现数据库里根本不存在的列。

    多出来的条目是死配置：它让读代码的人以为某个字段可写，
    而实际上写入时会由数据库抛错（或什么也没发生）。
    """
    problems = []
    for table, cols in sorted(TABLE_COLUMNS.items()):
        schema = _schema_columns(table)
        if not schema:
            continue
        unknown = sorted(set(cols) - schema)
        # created_by / recorder_id 之类是真实列，这里只报数据库里没有的
        if unknown:
            problems.append(f'{table}: {unknown}')
    assert not problems, '白名单里有数据库中不存在的列：\n  ' + '\n  '.join(problems)


def test_client_unwritable_entries_have_reasons() -> None:
    """拒绝名单里每一条都必须写明原因。

    没有原因的"不可写"和漏写白名单在代码上长得一模一样，
    后来的人分不清是"刻意拒绝"还是"忘了加"。
    """
    missing = [(t, c) for t, cols in CLIENT_UNWRITABLE.items()
               for c, reason in cols.items() if not str(reason or '').strip()]
    assert not missing, f'CLIENT_UNWRITABLE 缺少原因: {missing}'


def test_client_unwritable_columns_are_not_in_whitelist() -> None:
    """同一列不能既"不可写"又在白名单里 —— 那是自相矛盾的配置，
    实际生效的是白名单，于是"拒绝"形同虚设。"""
    bad = [(t, c) for t, cols in CLIENT_UNWRITABLE.items()
           for c in cols if c in TABLE_COLUMNS.get(t, set())]
    assert not bad, f'这些列同时出现在白名单与拒绝名单里: {bad}'
