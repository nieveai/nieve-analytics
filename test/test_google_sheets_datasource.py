import unittest
import pandas as pd
from unittest.mock import patch, MagicMock
from datasources.google_sheets_datasource import GoogleSheetsDatasource

class TestGoogleSheetsDatasource(unittest.TestCase):
    @patch('gspread.authorize')
    def test_load_and_preview(self, mock_authorize):
        # Mock gspread client and worksheet
        mock_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_authorize.return_value = mock_client
        mock_client.open_by_url.return_value = mock_spreadsheet
        mock_spreadsheet.sheet1 = mock_worksheet

        # Mock data
        mock_data = [
            ['col1', 'col2'],
            ['1', 'a'],
            ['2', 'b'],
            ['3', 'c'],
            ['4', 'd'],
            ['5', 'e'],
            ['6', 'f']
        ]
        mock_worksheet.get_all_values.return_value = mock_data

        # Datasource configuration
        config = {
            "sheet_url": "https://docs.google.com/spreadsheets/d/12345",
            "credentials_path": "path/to/credentials.json"
        }
        datasource = GoogleSheetsDatasource("test_ds", config)

        # Test _load_original_dataframe
        df = datasource._load_original_dataframe()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(df.shape, (6, 2))
        self.assertEqual(list(df.columns), ['col1', 'col2'])

        # Test preview
        preview_df = datasource.preview()
        self.assertIsInstance(preview_df, pd.DataFrame)
        self.assertEqual(preview_df.shape, (5, 2))

if __name__ == '__main__':
    unittest.main()
