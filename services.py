import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime


@st.cache_data(ttl=60)
def load_data_from_gsheet(sheet_name):
    """
    Load data from Google Sheets using gspread and oauth2client.
    
    Args:
        sheet_name: Name of the Google Spreadsheet to open
        
    Returns:
        pandas.DataFrame: DataFrame containing all records from the sheet
        
    Raises:
        Exception: If connection or data loading fails
    """
    try:
        # Get service account credentials from Streamlit secrets
        if "gcp_service_account" not in st.secrets:
            raise ValueError("gcp_service_account not found in st.secrets. Please configure it in your Streamlit secrets.")
        
        service_account_info = st.secrets["gcp_service_account"]
        
        # Define the scope
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Authenticate using service account
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            service_account_info,
            scope
        )
        
        # Authorize and open the client
        gc = gspread.authorize(credentials)
        
        # Open the spreadsheet by name
        spreadsheet = gc.open(sheet_name)
        
        # Get the first worksheet (you can modify this to select a specific worksheet)
        worksheet = spreadsheet.sheet1
        
        # Get all records as a list of dictionaries
        records = worksheet.get_all_records()
        
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Data Cleaning
        # 1. Handle empty rows - remove rows where all values are empty/None
        df = df.dropna(how='all')
        
        # 2. Convert 'Date' column to datetime (format is MM/DD/YYYY in the sheet)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(
                df['Date'],
                format='%m/%d/%Y',
                errors='coerce'
            )
        
        # Return the cleaned DataFrame
        return df
        
    except gspread.exceptions.SpreadsheetNotFound:
        error_msg = f"❌ Spreadsheet '{sheet_name}' not found. Please check the sheet name."
        st.error(error_msg)
        raise Exception(error_msg)
    except gspread.exceptions.APIError as e:
        error_msg = f"❌ Google Sheets API Error: {str(e)}"
        st.error(error_msg)
        raise Exception(error_msg)
    except KeyError as e:
        error_msg = f"❌ Missing key in service account credentials: {str(e)}"
        st.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"❌ Error loading data from Google Sheets: {str(e)}"
        st.error(error_msg)
        raise Exception(error_msg)
