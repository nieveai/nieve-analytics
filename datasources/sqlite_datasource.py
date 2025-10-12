import pandas as pd
import sqlite3
from .base_datasource import BaseDatasource

class SQLiteDatasource(BaseDatasource):
    def _load_original_dataframe(self):
        config = self.get_config()
        file_path = config.get('filePath')
        query = config.get('query')
        if not file_path or not query:
            raise ValueError("SQLite file path or query not found in config.")
        
        conn = sqlite3.connect(file_path)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def preview(self):
        config = self.get_config()
        file_path = config.get('filePath')
        query = config.get('query')
        if not file_path or not query:
            raise ValueError("SQLite file path or query not found in config.")
        
        conn = sqlite3.connect(file_path)
        preview_query = f"SELECT * FROM ({query}) LIMIT 5"
        df = pd.read_sql_query(preview_query, conn)
        conn.close()
        return {
            "columns": df.columns.tolist(),
            "rows": df.values.tolist()
        }

def get_sqlite_schema(file_path):
    conn = sqlite3.connect(file_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view';")
    views = [row[0] for row in cursor.fetchall()]
    conn.close()
    return {"tables": tables, "views": views}
