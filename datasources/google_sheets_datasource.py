import os
import pandas as pd
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from datasources.base_datasource import BaseDatasource

class GoogleSheetsDatasource(BaseDatasource):
    def __init__(self, datasource_id: str, config: dict):
        super().__init__(datasource_id)
        self.sheet_url = config.get("sheet_url")
        self.scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        self.creds = self._get_credentials()
        self.client = gspread.authorize(self.creds)

    def _get_credentials(self):
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', self.scopes)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.scopes)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        return creds

    def _load_original_dataframe(self) -> pd.DataFrame:
        spreadsheet = self.client.open_by_url(self.sheet_url)
        worksheet = spreadsheet.sheet1
        data = worksheet.get_all_values()
        return pd.DataFrame(data[1:], columns=data[0])

    def preview(self) -> pd.DataFrame:
        df = self._load_original_dataframe()
        return df.head(5)
