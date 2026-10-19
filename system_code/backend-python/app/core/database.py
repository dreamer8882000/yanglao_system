from contextlib import contextmanager
from typing import Any, Iterable
import logging
from .config import get_settings

logger = logging.getLogger(__name__)


class Database:
    def __init__(self) -> None:
        self.settings = get_settings()

    @contextmanager
    def connection(self):
        try:
            import pymysql
        except ImportError as exc:
            raise RuntimeError('缺少 PyMySQL 依赖，请先执行 pip install -r requirements.txt') from exc
        conn = pymysql.connect(**self.settings.database_kwargs)
        try:
            yield conn
        finally:
            conn.close()

    def query(self, sql: str, params: Iterable[Any] | None = None) -> list[dict]:
        try:
            from pymysql.cursors import DictCursor
        except ImportError as exc:
            raise RuntimeError('缺少 PyMySQL 依赖，请先执行 pip install -r requirements.txt') from exc
        with self.connection() as conn:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute(sql, params or [])
                rows = cursor.fetchall()
                return list(rows)

    def query_one(self, sql: str, params: Iterable[Any] | None = None) -> dict | None:
        """取单行；不存在返回 None。用于存在性/归属校验，避免到处 rows[0]。"""
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> int:
        with self.connection() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, params or [])
                conn.commit()
                return affected

    def insert(self, sql: str, params: Iterable[Any] | None = None) -> int:
        with self.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params or [])
                conn.commit()
                return int(cursor.lastrowid)

    def health(self) -> bool:
        try:
            self.query('SELECT 1 AS ok')
            return True
        except Exception as exc:
            logger.warning('database health check failed: %s', exc)
            return False

    @contextmanager
    def transaction(self):
        try:
            import pymysql
            from pymysql.cursors import DictCursor
        except ImportError as exc:
            raise RuntimeError('缺少 PyMySQL 依赖') from exc
        conn = pymysql.connect(**{**self.settings.database_kwargs, 'autocommit': False})
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


db = Database()
