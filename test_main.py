import unittest
from unittest.mock import Mock, patch
import pandas as pd
from main import analyze_data, CodeExecutionError

class TestAnalyzeData(unittest.TestCase):

    def setUp(self):
        # Create a mock DataFrame for the original data source
        self.original_df = pd.DataFrame({
            'col1': [1, 2, 3],
            'col2': ['A', 'B', 'C']
        })

        # Create a mock DataFrame for the transformed data
        self.transformed_df = pd.DataFrame({
            'col1_transformed': [10, 20, 30],
            'col2_transformed': ['X', 'Y', 'Z']
        })

        # Create a mock datasource_handler
        self.mock_datasource_handler = Mock()
        self.mock_datasource_handler.get_dataframe.side_effect = self._get_dataframe_mock

    def _get_dataframe_mock(self, transform_id=None):
        if transform_id == "test_transform_id":
            return self.transformed_df
        return self.original_df

    @patch('main.ModelClient')
    def test_analyze_data_without_transformation_id(self, MockModelClient):
        # Mock the model client to return a simple analysis code
        mock_model_client_instance = Mock()
        mock_model_client_instance.generate_content.return_value = "analysis_result = df['col1'].sum()"
        MockModelClient.get_client.return_value = mock_model_client_instance

        command = "sum of col1"
        result = analyze_data(self.mock_datasource_handler, command)

        self.assertEqual(result['resultData'], 6)
        self.assertEqual(result['resultType'], 'int64')
        self.mock_datasource_handler.get_dataframe.assert_called_with(transform_id=None)

    @patch('main.ModelClient')
    def test_analyze_data_with_transformation_id(self, MockModelClient):
        # Mock the model client to return a simple analysis code
        mock_model_client_instance = Mock()
        mock_model_client_instance.generate_content.return_value = "analysis_result = df['col1_transformed'].sum()"
        MockModelClient.get_client.return_value = mock_model_client_instance

        command = "sum of col1_transformed"
        transformation_id = "test_transform_id"
        result = analyze_data(self.mock_datasource_handler, command, transformation_id)

        self.assertEqual(result['resultData'], 60)
        self.assertEqual(result['resultType'], 'int64')
        self.mock_datasource_handler.get_dataframe.assert_called_with(transform_id=transformation_id)

    @patch('main.ModelClient')
    def test_analyze_data_code_execution_error(self, MockModelClient):
        mock_model_client_instance = Mock()
        mock_model_client_instance.generate_content.return_value = "raise ValueError('Test error')"
        MockModelClient.get_client.return_value = mock_model_client_instance

        command = "some command"
        with self.assertRaises(CodeExecutionError):
            analyze_data(self.mock_datasource_handler, command)

if __name__ == '__main__':
    unittest.main()
