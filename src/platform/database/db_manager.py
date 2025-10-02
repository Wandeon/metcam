"""
Database manager for FootballVision Pro
Handles all database operations with connection pooling
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

DB_PATH = "/var/lib/footballvision/footballvision.db"


class DatabaseManager:
    """Singleton database manager"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.db_path = DB_PATH
            self.initialized = True

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def execute(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute query and return results"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def execute_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """Execute query and return single result"""
        results = self.execute(query, params)
        return results[0] if results else None

    def insert(self, query: str, params: tuple = ()) -> int:
        """Execute insert and return last row id"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.lastrowid


# Global instance
db = DatabaseManager()
