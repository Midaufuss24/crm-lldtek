import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime


def _load_single_sheet(sheet_name, gc):
    """
    Helper function to load data from a single Google Sheet.
    
    Args:
        sheet_name: Name of the Google Spreadsheet to open
        gc: Authorized gspread client
        
    Returns:
        pandas.DataFrame: DataFrame containing all records from the sheet, or None if failed
    """
    try:
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
        
        # Add a column to track source sheet (optional, for debugging)
        df['_Source_Sheet'] = sheet_name
        
        # Return the cleaned DataFrame
        return df
        
    except gspread.exceptions.SpreadsheetNotFound:
        st.warning(f"⚠️ Cannot access '{sheet_name}'. Spreadsheet not found or not shared with service account.")
        return None
    except gspread.exceptions.APIError as e:
        st.warning(f"⚠️ Cannot access '{sheet_name}'. API Error: {str(e)}")
        return None
    except Exception as e:
        st.warning(f"⚠️ Cannot access '{sheet_name}'. Error: {str(e)}")
        return None


@st.cache_data(ttl=60)
def load_data_from_gsheet(list_of_sheet_names):
    """
    Load data from multiple Google Sheets and combine them into one DataFrame.
    
    Args:
        list_of_sheet_names: List of Google Spreadsheet names to open
        
    Returns:
        pandas.DataFrame: Combined DataFrame containing all records from all accessible sheets
        
    Raises:
        Exception: If authentication fails or no sheets can be loaded
    """
    if not list_of_sheet_names or len(list_of_sheet_names) == 0:
        return pd.DataFrame()
    
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
        
        # List to store all successfully loaded DataFrames
        dataframes_list = []
        
        # Loop through each sheet name
        for sheet_name in list_of_sheet_names:
            df = _load_single_sheet(sheet_name, gc)
            if df is not None and not df.empty:
                dataframes_list.append(df)
        
        # Check if we loaded any data
        if len(dataframes_list) == 0:
            return pd.DataFrame()
        
        # Combine all DataFrames using pd.concat
        combined_df = pd.concat(dataframes_list, ignore_index=True)
        
        # Remove the temporary source column if it exists (optional cleanup)
        if '_Source_Sheet' in combined_df.columns:
            combined_df = combined_df.drop(columns=['_Source_Sheet'])
        
        return combined_df
        
    except KeyError as e:
        error_msg = f"❌ Missing key in service account credentials: {str(e)}"
        st.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"❌ Error loading data from Google Sheets: {str(e)}"
        st.error(error_msg)
        raise Exception(error_msg)
