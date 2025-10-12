from .csv_file_datasource import CSVFileDatasource
from .sqlite_datasource import SQLiteDatasource
from .derived_datasource import DerivedDatasource

def get_datasource_handler(data_source):
    ds_type = data_source.get('type')
    if ds_type == 'csv':
        return CSVFileDatasource(data_source)
    elif ds_type == 'sqlite':
        return SQLiteDatasource(data_source)
    elif ds_type == 'derived':
        return DerivedDatasource(data_source)
    else:
        raise ValueError(f"Unsupported data source type: {ds_type}")
