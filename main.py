import sys
import json
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
import google.generativeai as genai
import logging
import sqlite3
import sklearn
import zmq

from datasources import get_datasource_handler
from datasources.base_datasource import BaseDatasource
from datasources.sqlite_datasource import get_sqlite_schema
import numpy as np

from models.model_client import ModelClient

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

class CodeExecutionError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def preview_data(datasource_handler):
    return datasource_handler.preview()

def clean_code(code):
    code = code.strip()
    loc = code.split("\n")
    cleaned_code = []
    for line in loc:
        if line[0:3] == "```":
            continue
        else:
            cleaned_code.append(line)
    return "\n".join(cleaned_code)

def generate_plot(datasource_handler, command, visualization_id, transform_id=None):
    df = datasource_handler.get_dataframe(transform_id=transform_id)
    logging.info(f"transform id : {transform_id}")
    prompt = f"""
    You are a data visualization expert. Your task is to generate Python code to create a plot using matplotlib based on a user's command.
    The data is available in a pandas DataFrame named `df`.
    User Command: "{command}"
    DataFrame Columns: {df.columns.tolist()}
    Data Preview (first 3 rows):
    {df.head(3).to_string()}
    **CRITICAL INSTRUCTIONS:**
    1. You MUST generate ONLY Python code for plotting.
    2. Do NOT include any imports.
    3. Do NOT include markdown specifiers like ```python.
    4. You MUST use the provided variables directly: `df`, `plt`, `buf`.
    5. You MUST save the final plot to the `buf` buffer.
    6. Do NOT call `plt.close()`.
    """

    model = ModelClient.get_client()
    logging.info("calling model to generate code")
    response = model.generate_content(prompt)
    generated_code = clean_code(response)
    logging.info(f"code generated ${generated_code[0:10]}")
    buf = io.BytesIO()
    scope = {'pd': pd, 'df': df, 'plt': plt, 'buf': buf}
    try:
        exec(generated_code, scope)
    except Exception as e:
        raise CodeExecutionError(f"Error executing generated code: {e}", generated_code) from e

    if buf.getbuffer().nbytes == 0:
        raise ValueError("Generated code failed to save a plot to the buffer.")

    plt.close()
    buf.seek(0)
    plot_data = base64.b64encode(buf.read()).decode('utf-8')
    
    return {
        "plotData": plot_data,
        "generatedCode": generated_code
    }

def modify_plot(datasource_handler, existing_code, instruction, visualization_id, transform_id=None):
    df = datasource_handler.get_dataframe(transform_id=transform_id)

    prompt = f"""
    You are a data visualization expert. Your task is to modify an existing Python script that uses matplotlib to generate a plot.
    The data is available in a pandas DataFrame named `df`.
    Existing Code:
    ```python
    {existing_code}
    ```
    User's Modification Instruction: "{instruction}"
    DataFrame Columns: {df.columns.tolist()}
    **CRITICAL INSTRUCTIONS:**
    1. Generate a new, complete Python script that incorporates the user's modification.
    2. Do NOT include any imports.
    3. Do NOT include markdown specifiers like ```python.
    4. You MUST use the provided variables directly: `df`, `plt`, `buf`.
    5. Do not add any explanations or comments.
    """
    model = ModelClient.get_client()
    response = model.generate_content(prompt)
    generated_code = clean_code(response)

    buf = io.BytesIO()
    scope = {'pd': pd, 'df': df, 'plt': plt, 'buf': buf}
    try:
        exec(generated_code, scope)
    except Exception as e:
        raise CodeExecutionError(f"Error executing generated code: {e}", generated_code) from e

    if buf.getbuffer().nbytes == 0:
        raise ValueError("Generated code failed to save a plot to the buffer.")

    plt.close()
    buf.seek(0)
    plot_data = base64.b64encode(buf.read()).decode('utf-8')
    
    return {
        "plotData": plot_data,
        "generatedCode": generated_code,
        "id": visualization_id
    }

def run_code(datasource_handler, code_to_run, visualization_id, transform_id=None):
    logging.info(f"modify visualization for {visualization_id}")
    df = datasource_handler.get_dataframe(transform_id=transform_id)
    buf = io.BytesIO()
    scope = {'pd': pd, 'df': df, 'plt': plt, 'buf': buf}
    try:
        exec(code_to_run, scope)
    except Exception as e:
        raise CodeExecutionError(f"Error executing code: {e}", code_to_run) from e

    if buf.getbuffer().nbytes == 0:
        raise ValueError("Code failed to save a plot to the buffer.")

    plt.close()
    buf.seek(0)
    plot_data = base64.b64encode(buf.read()).decode('utf-8')
    logging.info(f"plotdata {plot_data[0:5]}")
    return { "plotData": plot_data, "id": visualization_id }

def analyze_data(datasource_handler, command, transform_id=None):
    df = datasource_handler.get_dataframe(transform_id=transform_id)
    
    prompt = f"""
    You are a data analysis expert. Your task is to generate Python code to analyze a pandas DataFrame.
    The data is in a DataFrame named `df`. The scikit-learn library is available as `sklearn`.
    User Command: "{command}"
    DataFrame Columns: {df.columns.tolist()}
    **CRITICAL INSTRUCTIONS:**
    1. Generate ONLY Python code for the analysis.
    2. The code must store the result in a variable called `analysis_result`.
    3. The result can be a string, number, list, dictionary, or a pandas DataFrame/Series.
    4. Do NOT include any imports or markdown specifiers.
    5. You MUST use the provided variables `df` and `sklearn`.
    6. DO NOT include any markdown such as ```
    """

    model = ModelClient.get_client()
    response = model.generate_content(prompt)
    generated_code = clean_code(response)

    logging.debug(f"generated code: {generated_code}")

    scope = {'pd': pd, 'df': df.copy(), 'sklearn': sklearn}
    try:
        exec(generated_code, scope)
    except Exception as e:
        raise CodeExecutionError(f"Error executing generated code: {e}", generated_code) from e
    
    analysis_result = scope.get('analysis_result')

    if isinstance(analysis_result, (pd.DataFrame, pd.Series)):
        result_data = analysis_result.to_json(orient='split')
        result_type = 'dataframe' if isinstance(analysis_result, pd.DataFrame) else 'series'
    else:
        result_data = analysis_result
        result_type = type(analysis_result).__name__

    return {
        "resultData": result_data,
        "resultType": result_type,
        "generatedCode": generated_code
    }

def modify_analysis(datasource_handler, existing_code, instruction, transform_id=None):
    df = datasource_handler.get_dataframe(transform_id=transform_id)

    prompt = f"""
    You are a data analysis expert. Your task is to modify an existing Python script that uses pandas to analyze data.
    The data is in a DataFrame named `df`. The scikit-learn library is available as `sklearn`.
    Existing Code:
    ```python
    {existing_code}
    ```
    User's Modification Instruction: "{instruction}"
    DataFrame Columns: {df.columns.tolist()}
    **CRITICAL INSTRUCTIONS:**
    1. Generate a new, complete Python script with the modification.
    2. The code must store the result in a variable called `analysis_result`.
    3. Do NOT include any imports or markdown specifiers.
    4. You MUST use the provided variables `df` and `sklearn`.
    """

    model = ModelClient.get_client()
    response = model.generate_content(prompt)
    generated_code = clean_code(response)

    scope = {'pd': pd, 'df': df.copy(), 'sklearn': sklearn}
    try:
        exec(generated_code, scope)
    except Exception as e:
        raise CodeExecutionError(f"Error executing generated code: {e}", generated_code) from e
    
    analysis_result = scope.get('analysis_result')

    if isinstance(analysis_result, (pd.DataFrame, pd.Series)):
        result_data = analysis_result.to_json(orient='split')
        result_type = 'dataframe' if isinstance(analysis_result, pd.DataFrame) else 'series'
    else:
        result_data = analysis_result
        result_type = type(analysis_result).__name__

    return {
        "resultData": result_data,
        "resultType": result_type,
        "generatedCode": generated_code
    }

def run_analysis_code(datasource_handler, code_to_run, transform_id=None):
    df = datasource_handler.get_dataframe(transform_id=transform_id)
    scope = {'pd': pd, 'df': df.copy(), 'sklearn': sklearn}
    try:
        exec(code_to_run, scope)
    except Exception as e:
        raise CodeExecutionError(f"Error executing code: {e}", code_to_run) from e
    
    analysis_result = scope.get('analysis_result')

    if isinstance(analysis_result, (pd.DataFrame, pd.Series)):
        result_data = analysis_result.to_json(orient='split')
        result_type = 'dataframe' if isinstance(analysis_result, pd.DataFrame) else 'series'
    else:
        result_data = analysis_result
        result_type = type(analysis_result).__name__

    return {
        "resultData": result_data,
        "resultType": result_type
    }

def transform_data(datasource_handler, command, transform_id):
    df = datasource_handler.get_dataframe()

    prompt = f"""
    You are a data transformation expert. Your task is to generate Python code to transform a pandas DataFrame.
    The data is in a DataFrame named `df`.
    User Command: "{command}"
    DataFrame Columns: {df.columns.tolist()}
    **CRITICAL INSTRUCTIONS:**
    1. Generate ONLY Python code for the transformation.
    2. The code must store the transformed DataFrame in a variable called `transformed_df`.
    3. Do NOT include any imports or markdown specifiers.
    4. You MUST use the provided variables `df`.
    """

    model = ModelClient.get_client()
    response = model.generate_content(prompt)
    generated_code = clean_code(response)

    scope = {'pd': pd, 'df': df.copy()} # Use a copy to avoid modifying the cached df
    try:
        exec(generated_code, scope)
    except Exception as e:
        raise CodeExecutionError(f"Error executing generated code: {e}", generated_code) from e
    
    transformed_df = scope.get('transformed_df')

    if not isinstance(transformed_df, pd.DataFrame):
        raise ValueError("Generated code did not produce a pandas DataFrame.")

    # Update the cache with the transformed data
    BaseDatasource.add_to_cache(transform_id, transformed_df)
    
    # Return a preview of the transformed data
    preview_data = {
        "columns": transformed_df.columns.tolist(),
        "rows": transformed_df.head(5).fillna('').values.tolist()
    }

    return {
        "previewData": preview_data,
        "generatedCode": generated_code,
        "totalRows": len(transformed_df)
    }

def modify_transform_data(datasource_handler, existing_code, instruction, transform_id):
    
    # Find the current transform to get its parent
    transform = next((t for t in datasource_handler.get_transforms() if t['id'] == transform_id), None)
    if not transform:
        raise ValueError(f"Transform with id '{transform_id}' not found in data source.")
        
    parent_transform_id = transform.get('basedOn')
    df = datasource_handler.get_dataframe(transform_id=parent_transform_id)

    prompt = f"""
    You are a data transformation expert. Your task is to modify an existing Python script that uses pandas to transform data.
    The data is in a DataFrame named `df`.
    Existing Code:
    ```python
    {existing_code}
    ```
    User's Modification Instruction: "{instruction}"
    DataFrame Columns: {df.columns.tolist()}
    **CRITICAL INSTRUCTIONS:**
    1. Generate a new, complete Python script with the modification.
    2. The code must store the result in a variable called `transformed_df`.
    3. Do NOT include any imports or markdown specifiers.
    4. You MUST use the provided variables `df`.
    """

    model = ModelClient.get_client()
    response = model.generate_content(prompt)
    generated_code = clean_code(response)

    scope = {'pd': pd, 'df': df.copy()}
    try:
        exec(generated_code, scope)
    except Exception as e:
        raise CodeExecutionError(f"Error executing generated code: {e}", generated_code) from e
    
    transformed_df = scope.get('transformed_df')

    if not isinstance(transformed_df, pd.DataFrame):
        raise ValueError("Generated code did not produce a pandas DataFrame.")

    BaseDatasource.add_to_cache(transform_id, transformed_df)
    
    preview_data = {
        "columns": transformed_df.columns.tolist(),
        "rows": transformed_df.head(5).fillna('').values.tolist()
    }

    return {
        "previewData": preview_data,
        "generatedCode": generated_code,
        "totalRows": len(transformed_df)
    }

def run_transform_code(datasource_handler, code_to_run, transform_id):
    # Find the current transform to get its parent
    transform = next((t for t in datasource_handler.get_transforms() if t['id'] == transform_id), None)
    if not transform:
        raise ValueError(f"Transform with id '{transform_id}' not found in data source.")
        
    parent_transform_id = transform.get('basedOn')
    df = datasource_handler.get_dataframe(transform_id=parent_transform_id)

    scope = {'pd': pd, 'df': df.copy()}
    try:
        exec(code_to_run, scope)
    except Exception as e:
        raise CodeExecutionError(f"Error executing code: {e}", code_to_run) from e
    
    transformed_df = scope.get('transformed_df')

    if not isinstance(transformed_df, pd.DataFrame):
        raise ValueError("Generated code did not produce a pandas DataFrame.")

    BaseDatasource.add_to_cache(transform_id, transformed_df)
    
    preview_data = {
        "columns": transformed_df.columns.tolist(),
        "rows": transformed_df.head(5).fillna('').values.tolist()
    }

    return {
        "previewData": preview_data,
        "totalRows": len(transformed_df)
    }

def new_transform_data(datasource_handler, parent_transform_id, instruction, new_transform_id):
    
    # Get the DataFrame from the parent transform by passing the parent_transform_id
    df = datasource_handler.get_dataframe(transform_id=parent_transform_id)

    prompt = f"""
    You are a data transformation expert. Your task is to generate Python code to transform a pandas DataFrame.
    The data is in a DataFrame named `df`.
    User Command: "{instruction}"
    DataFrame Columns: {df.columns.tolist()}
    **CRITICAL INSTRUCTIONS:**
    1. Generate ONLY Python code for the transformation.
    2. The code must store the transformed DataFrame in a variable called `transformed_df`.
    3. Do NOT include any imports or markdown specifiers.
    4. You MUST use the provided variables `df`.
    """

    model = ModelClient.get_client()
    response = model.generate_content(prompt)
    generated_code = clean_code(response)

    scope = {'pd': pd, 'df': df.copy()} # Use a copy to avoid modifying the cached df
    try:
        exec(generated_code, scope)
    except Exception as e:
        raise CodeExecutionError(f"Error executing generated code: {e}", generated_code) from e
    
    transformed_df = scope.get('transformed_df')

    if not isinstance(transformed_df, pd.DataFrame):
        raise ValueError("Generated code did not produce a pandas DataFrame.")

    # Update the cache with the new transformed data
    BaseDatasource.add_to_cache(new_transform_id, transformed_df)
    
    # Return a preview of the transformed data
    preview_data = {
        "columns": transformed_df.columns.tolist(),
        "rows": transformed_df.head(5).fillna('').values.tolist()
    }

    return {
        "previewData": preview_data,
        "generatedCode": generated_code,
        "totalRows": len(transformed_df)
    }

def create_derived_data_source(sources, instruction, new_data_source_id):
    
    # Load the dataframes for each source
    # The variable names for the dataframes will be df0, df1, df2, etc.
    df_vars = {}
    prompt_parts = []
    for i, source_data in enumerate(sources):
        handler = get_datasource_handler(source_data)
        # The latest_transform_id is passed within the source_data object
        transform_id = source_data.get('latest_transform_id') 
        df = handler.get_dataframe(transform_id=transform_id)
        df_name = f"df{i}"
        df_vars[df_name] = df
        
        prompt_parts.append(f"DataFrame `{df_name}` (from source: {source_data['name']}):")
        prompt_parts.append(f"  - Columns: {df.columns.tolist()}")
        prompt_parts.append(f"  - Preview:\n{df.head(2).to_string()}")

    data_description = "\n".join(prompt_parts)

    prompt = f"""
    You are a data manipulation expert. Your task is to generate Python code to combine multiple pandas DataFrames into a single DataFrame.
    The available DataFrames are:
    {data_description}
    User's Instruction: "{instruction}"
    **CRITICAL INSTRUCTIONS:**
    1. Generate ONLY Python code to perform the combination.
    2. The final combined DataFrame MUST be stored in a variable named `derived_df`.
    3. Do NOT include any imports or markdown specifiers.
    4. Use the provided DataFrame variables (df0, df1, etc.) directly.
    """

    model = ModelClient.get_client()
    response = model.generate_content(prompt)
    generated_code = clean_code(response)

    # The scope will contain the input dataframes (df0, df1, ...)
    scope = {**df_vars, 'pd': pd}
    try:
        exec(generated_code, scope)
    except Exception as e:
        raise CodeExecutionError(f"Error executing generated code: {e}", generated_code) from e
    
    derived_df = scope.get('derived_df')

    if not isinstance(derived_df, pd.DataFrame):
        raise ValueError("Generated code did not produce a pandas DataFrame named 'derived_df'.")

    # Cache the new derived dataframe
    BaseDatasource.add_to_cache(new_data_source_id, derived_df)
    
    preview_data = {
        "columns": derived_df.columns.tolist(),
        "rows": derived_df.head(5).fillna('').values.tolist()
    }

    return {
        "previewData": preview_data,
        "generatedCode": generated_code,
        "totalRows": len(derived_df)
    }

def load_more_data(datasource_handler, transform_id, offset, limit):
    df = datasource_handler.get_dataframe(transform_id=transform_id)
    
    # Ensure offset and limit are within bounds
    offset = max(0, offset)
    limit = min(100, limit) # Enforce a max limit for safety
    
    if offset >= len(df):
        return [] # Return empty list if offset is beyond the dataframe length

    end_index = min(offset + limit, len(df))
    
    more_rows_df = df.iloc[offset:end_index]
    
    return more_rows_df.fillna('').values.tolist()

def export_transform_data(datasource_handler, transform_id):
    df = datasource_handler.get_dataframe(transform_id=transform_id)
    return df.to_csv(index=False)

def main():
    logging.basicConfig(level=logging.INFO)
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://127.0.0.1:5555")
    logging.info("Socket bound to tcp://127.0.0.1:5555 and ready to receive requests.")
    print("PYTHON_ZMQ_READY", flush=True)

    while True:
        try:
            logging.debug("Waiting to receive message...")
            message = socket.recv_string()
            logging.debug(f"Received message: {message}")
            request = json.loads(message)
            command = request.get("command")
            payload = request.get("payload", {})
            request_id = request.get("requestId")

            if not command or not request_id:
                raise ValueError("'command' and 'requestId' are required.")

            result = None
            
            data_source = payload.pop('data_source', None)
            if data_source:
                handler = get_datasource_handler(data_source)
                payload['datasource_handler'] = handler

            if command == 'preview_data':
                result = preview_data(**payload)
            elif command == 'get_sqlite_schema':
                result = get_sqlite_schema(**payload)
            elif command == 'invalidate_cache':
                result = BaseDatasource.invalidate_cache(**payload)
            elif command == 'generate_plot':
                payload['transform_id'] = payload.get('transform_id')
                result = generate_plot(**payload)
            elif command == 'modify_plot':
                payload['transform_id'] = payload.get('transform_id')
                result = modify_plot(**payload)
            elif command == 'run_code':
                payload['transform_id'] = payload.get('transform_id')
                result = run_code(**payload)
            elif command == 'analyze':
                payload['transform_id'] = payload.get('transform_id')
                result = analyze_data(**payload)
            elif command == 'modify_analysis':
                payload['transform_id'] = payload.get('transform_id')
                result = modify_analysis(**payload)
            elif command == 'run_analysis_code':
                payload['transform_id'] = payload.get('transform_id')
                result = run_analysis_code(**payload)
            elif command == 'transform':
                result = transform_data(**payload)
            elif command == 'modify_transform':
                result = modify_transform_data(**payload)
            elif command == 'run_transform_code':
                result = run_transform_code(**payload)
            elif command == 'new_transform':
                result = new_transform_data(**payload)
            elif command == 'create_derived_data_source':
                result = create_derived_data_source(**payload)
            elif command == 'load_more_data':
                result = load_more_data(**payload)
            elif command == 'export_transform_data':
                result = export_transform_data(**payload)
            elif command == 'initialize_model_client':
                ModelClient.initialize(payload['model_provider'], payload['model_name'], payload['api_key'], payload.get('base_url'))
                result = {"status": "Model client initialized"}
            else:
                raise ValueError(f"Unknown command: {command}")

            response = {
                "requestId": request_id,
                "success": True,
                "payload": result
            }

        except CodeExecutionError as e:
            logging.error(f"Code execution error processing command '{command}': {e.code}", exc_info=True)
            response = {
                "requestId": request_id,
                "success": False,
                "error": {
                    "type": "CodeExecutionError",
                    "message": str(e),
                    "code": e.code
                }
            }
        except Exception as e:
            logging.error(f"Error processing command '{command}': {e}", exc_info=True)
            response = {
                "requestId": request_id,
                "success": False,
                "error": {
                    "type": "GenericError",
                    "message": str(e)
                }
            }
        try:
            response_json = json.dumps(response, cls=NumpyEncoder, default=str)
            logging.debug(f"Sending response: {response_json}")
        except Exception as e:
            logging.error(f"failed to serialize the response because of {str(e)}")
            response = {
                "requestId": request_id,
                "success": False,
                "error": {
                    "type": "GenericError",
                    "message": str(e)
                }
            }
        
        try:
            socket.send_string(response_json)
        except Exception as e:
            logging.error(f"failed to send to the socket")


if __name__ == "__main__":
    main()
