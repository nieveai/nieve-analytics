import pandas as pd
from .base_datasource import BaseDatasource

class DerivedDatasource(BaseDatasource):
    PREVIEW_ROW_LIMIT = 5

    def __init__(self, data_source_config):
        super().__init__(data_source_config)
        self.type = 'derived'

    def _load_original_dataframe(self):
        from . import get_datasource_handler
        config = self.get_config()
        generated_code = config.get('generatedCode')
        if not generated_code:
            raise ValueError(f"Derived data source {self.id} has no generated code.")

        parent_sources = config.get('sources', [])
        if not parent_sources:
            raise ValueError(f"Derived data source {self.id} has no parent sources defined.")

        all_data_sources = self.data_source_info.get('all_data_sources', [])
        if not all_data_sources:
            raise ValueError("The 'all_data_sources' attribute is missing from the data source configuration.")

        all_sources_map = all_data_sources

        scope_dfs = {}
        for i, parent_ref_str in enumerate(parent_sources):
            df_name = f"df{i}"
            parent_df = None

            if parent_ref_str.startswith('ds:'):
                ds_id = parent_ref_str[3:]
                if ds_id not in all_sources_map:
                    raise ValueError(f"Parent data source with id {ds_id} not found in all_data_sources.")
                
                parent_config = all_sources_map[ds_id]
                parent_config['all_data_sources'] = all_data_sources
                parent_handler = get_datasource_handler(parent_config)
                parent_df = parent_handler.get_dataframe(transform_id=None)

            elif parent_ref_str.startswith('tr:'):
                parent_ds_id, transform_id = parent_ref_str[3:].split(":")
                
                parent_ds_config = all_sources_map[parent_ds_id]
                parent_ds_config['all_data_sources'] = all_data_sources
                parent_handler = get_datasource_handler(parent_ds_config)
                parent_df = parent_handler.get_dataframe(transform_id=transform_id)

                if not parent_ds_config:
                    raise ValueError(f"Data source for transform id {transform_id} not found.")
            
            else:
                raise ValueError(f"Invalid parent source reference '{parent_ref_str}'. Must start with 'ds:' or 'tr:'.")

            if parent_df is not None:
                scope_dfs[df_name] = parent_df.copy()
            else:
                raise ValueError(f"Failed to load dataframe for parent source '{parent_ref_str}'")

        scope = {**scope_dfs, 'pd': pd}
        exec(generated_code, scope)
        
        derived_df = scope.get('derived_df')

        if not isinstance(derived_df, pd.DataFrame):
            raise ValueError("Generated code did not produce a pandas DataFrame named 'derived_df'.")

        return derived_df

    def preview(self):
        df = self.get_dataframe()
        return {
            "columns": df.columns.tolist(),
            "rows": df.head(self.PREVIEW_ROW_LIMIT).values.tolist()
        }
