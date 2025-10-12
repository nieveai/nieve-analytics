import pandas as pd
from .base_datasource import BaseDatasource

class CSVFileDatasource(BaseDatasource):
    def _load_original_dataframe(self):
        file_path = self.get_config().get('filePath')
        if not file_path:
            raise ValueError("CSV file path not found in config.")
        return pd.read_csv(file_path)

    def preview(self):
        file_path = self.get_config().get('filePath')
        if not file_path:
            raise ValueError("CSV file path not found in config.")
        df = pd.read_csv(file_path, nrows=5)
        return {
            "columns": df.columns.tolist(),
            "rows": df.fillna('').values.tolist()
        }
