"""把多租户 SQL 覆盖扫描纳入常规测试。

`scripts/eval/audit_tenant_coverage.py` 是独立的命令行脚本，但独立脚本的问题
是**没人会记得跑**。这里把它包成一条 pytest 用例：任何人执行 `pytest tests/`
都会顺带检查"有没有新写的 SQL 忘了带 tenant_id"。

扫描本身是纯静态的（读源码、不连库），所以这条用例很快，也不依赖服务在跑。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'scripts' / 'eval' / 'audit_tenant_coverage.py'


def _load_scanner():
    spec = importlib.util.spec_from_file_location('_tenant_coverage', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_no_unscoped_tenant_sql() -> None:
    """app/ 下不存在"碰了业务表却没有 tenant_id"的 SQL。"""
    scanner = _load_scanner()
    findings = []
    for path in sorted(scanner.APP.rglob('*.py')):
        rel = str(path.relative_to(ROOT / 'system_code' / 'backend-python'))
        for lineno, sql, dynamic in scanner.string_literals(path):
            if not scanner.looks_like_sql(sql):
                continue
            tables, problem = scanner.check_statement(sql, dynamic)
            if not problem:
                continue
            for table in sorted(tables):
                if (rel, table) in scanner.WHITELIST:
                    continue
                findings.append(f'{rel}:{lineno} [{table}] {problem}')

    assert not findings, (
        '发现未按租户过滤的 SQL（要么加 tenant_id，要么加进 '
        'audit_tenant_coverage.WHITELIST 并写明理由）:\n  '
        + '\n  '.join(findings)
    )


def test_whitelist_entries_have_reasons() -> None:
    """白名单里每一条都必须有理由 —— 没写理由的例外等于没有例外。"""
    scanner = _load_scanner()
    missing = [key for key, reason in scanner.WHITELIST.items()
               if not str(reason or '').strip()]
    assert not missing, f'白名单缺少理由: {missing}'


def test_whitelist_has_no_stale_entries() -> None:
    """白名单不能留"已经不需要豁免"的死条目。

    死条目会让后来的人以为某处仍然需要特别照顾，也会掩盖"这个文件已经被
    重构成安全写法"的信息。这里只报警告性的失败：把不再触发的条目删掉即可。
    """
    scanner = _load_scanner()
    triggered: set[tuple[str, str]] = set()
    for path in sorted(scanner.APP.rglob('*.py')):
        rel = str(path.relative_to(ROOT / 'system_code' / 'backend-python'))
        for lineno, sql, dynamic in scanner.string_literals(path):
            if not scanner.looks_like_sql(sql):
                continue
            tables, problem = scanner.check_statement(sql, dynamic)
            if problem:
                triggered.update((rel, t) for t in tables)

    stale = sorted(set(scanner.WHITELIST) - triggered)
    assert not stale, f'白名单里这些条目已不再触发，可以删除: {stale}'
