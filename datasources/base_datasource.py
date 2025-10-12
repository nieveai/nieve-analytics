import pandas as pd
import logging

class BaseDatasource:
    _df_cache = {}

    def __init__(self, data_source_info):
        self.data_source_info = data_source_info
        self.id = data_source_info['id']

    @staticmethod
    def add_to_cache(key, df):
        BaseDatasource._df_cache[key] = df

    @staticmethod
    def get_from_cache(key):
        return BaseDatasource._df_cache.get(key)

    def get_visualizations(self):
        return self.data_source_info.get('visualizations', [])

    def get_analyses(self):
        return self.data_source_info.get('analyses', [])

    def get_transforms(self):
        return self.data_source_info.get('transforms', [])

    def get_config(self):
        return self.data_source_info.get('config', {})

    def get_dataframe(self, transform_id=None):
        if transform_id:
            cached_df = BaseDatasource.get_from_cache(transform_id)
            if cached_df is not None:
                return cached_df
            else:
                logging.info(f"DataFrame for transform '{transform_id}' not in cache. Regenerating...")
                transform = next((t for t in self.get_transforms() if t['id'] == transform_id), None)
                if not transform:
                    raise ValueError(f"Transform with id '{transform_id}' not found in data source.")
                
                generated_code = transform.get('generatedCode')
                if not generated_code:
                    raise ValueError(f"Transform with id '{transform_id}' has no generated code.")

                parent_transform_id = transform.get('basedOn')
                parent_df = self.get_dataframe(transform_id=parent_transform_id)
                
                scope = {'pd': pd, 'df': parent_df.copy()}
                exec(generated_code, scope)
                
                transformed_df = scope.get('transformed_df')

                if not isinstance(transformed_df, pd.DataFrame):
                    raise ValueError(f"Regeneration for transform '{transform_id}' did not produce a pandas DataFrame.")
                
                BaseDatasource.add_to_cache(transform_id, transformed_df)
                logging.info(f"Successfully regenerated and cached DataFrame for transform '{transform_id}'.")
                return transformed_df

        cached_df = BaseDatasource.get_from_cache(self.id)
        if cached_df is not None:
            return cached_df
        
        df = self._load_original_dataframe()
        BaseDatasource.add_to_cache(self.id, df)
        return df

    def _load_original_dataframe(self):
        raise NotImplementedError("Subclasses must implement _load_original_dataframe")

    def preview(self):
        raise NotImplementedError("Subclasses must implement preview")

    @staticmethod
    def invalidate_cache(data_source_id):
        if data_source_id in BaseDatasource._df_cache:
            del BaseDatasource._df_cache[data_source_id]
            logging.info(f"Cache invalidated for data source: {data_source_id}")
            return {"status": "success"}
        return {"status": "not_found"}
