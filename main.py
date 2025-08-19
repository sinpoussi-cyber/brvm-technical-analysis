# ==============================================================================
# ANALYSE TECHNIQUE BRVM - V1.0 (GitHub Actions & Service Account)
# ==============================================================================

# --- Imports ---
import gspread
from google.oauth2 import service_account
import pandas as pd
import numpy as np
import warnings
import re
import os
import json
import time

warnings.filterwarnings('ignore')

# --- Authentification via Compte de Service (pour GitHub Actions) ---
def authenticate_gsheets():
    """
    Authentification via compte de service Google.
    """
    try:
        logging.info("Authentification via compte de service Google...")
        creds_json_str = os.environ.get('GSPREAD_SERVICE_ACCOUNT')
        if not creds_json_str:
            logging.error("❌ Secret GSPREAD_SERVICE_ACCOUNT introuvable dans l'environnement.")
            return None
        creds_dict = json.loads(creds_json_str)
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        logging.info("✅ Authentification Google réussie.")
        return gc
    except Exception as e:
        logging.error(f"❌ Erreur d'authentification : {e}")
        return None

def clean_numeric_value(value):
    """
    Nettoie et convertit une valeur en nombre.
    """
    if pd.isna(value) or value == '' or value is None:
        return np.nan
    str_value = str(value).strip()
    str_value = re.sub(r'[^\d.,\-+]', '', str_value)
    str_value = str_value.replace(',', '.')
    try:
        return float(str_value)
    except (ValueError, TypeError):
        return np.nan

def convert_columns_to_numeric(gc, spreadsheet_id, sheet_name):
    """
    Convertit les colonnes C, D et E en valeurs numériques.
    """
    try:
        spreadsheet = gc.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        logging.info(f"Conversion des données numériques pour {sheet_name}...")
        all_values = worksheet.get_all_values()

        if len(all_values) < 2:
            logging.warning(f"Pas assez de données dans {sheet_name}")
            return False

        headers = all_values[0]
        data = all_values[1:]
        
        columns_to_convert = []
        if len(headers) > 2: columns_to_convert.append((2, 'C')) # Cours
        if len(headers) > 3: columns_to_convert.append((3, 'D')) # Volume
        if len(headers) > 4: columns_to_convert.append((4, 'E')) # Valeurs

        updates = []
        for col_index, col_letter in columns_to_convert:
            numeric_values = []
            for row in data:
                if col_index < len(row):
                    cleaned_value = clean_numeric_value(row[col_index])
                    numeric_values.append([cleaned_value if not pd.isna(cleaned_value) else ""])
                else:
                    numeric_values.append([""])
            
            if numeric_values:
                updates.append({
                    'range': f'{col_letter}2:{col_letter}{len(data) + 1}',
                    'values': numeric_values
                })

        if updates:
            worksheet.batch_update(updates, value_input_option='USER_ENTERED')
            logging.info(f"  ✓ Colonnes converties avec succès pour {sheet_name}")
        return True

    except Exception as e:
        logging.error(f"  ✗ Erreur lors de la conversion pour {sheet_name}: {e}")
        return False

# --- Fonctions de calcul des indicateurs ---
def calculate_moving_averages(df, price_col):
    df['MM5'] = df[price_col].rolling(window=5).mean()
    df['MM10'] = df[price_col].rolling(window=10).mean()
    df['MM20'] = df[price_col].rolling(window=20).mean()
    df['MM50'] = df[price_col].rolling(window=50).mean()
    def mm_decision(row):
        if pd.isna(row['MM5']) or pd.isna(row['MM20']): return "Attendre"
        if row['MM5'] > row['MM20']: return "Achat"
        elif row['MM5'] < row['MM20']: return "Vente"
        return "Neutre"
    df['MMdecision'] = df.apply(mm_decision, axis=1)
    return df

def calculate_bollinger_bands(df, price_col, window=20, num_std=2):
    rolling_mean = df[price_col].rolling(window=window).mean()
    rolling_std = df[price_col].rolling(window=window).std()
    df['Bande_Superieure'] = rolling_mean + (rolling_std * num_std)
    df['Bande_Inferieure'] = rolling_mean - (rolling_std * num_std)
    def bollinger_decision(row):
        if pd.isna(row['Bande_Superieure']): return "Attendre"
        if row[price_col] <= row['Bande_Inferieure']: return "Achat"
        elif row[price_col] >= row['Bande_Superieure']: return "Vente"
        return "Neutre"
    df['Boldecision'] = df.apply(bollinger_decision, axis=1)
    return df

def calculate_macd(df, price_col):
    ema_fast = df[price_col].ewm(span=10, adjust=False).mean()
    ema_slow = df[price_col].ewm(span=20, adjust=False).mean()
    df['Ligne_MACD'] = ema_fast - ema_slow
    df['Ligne_Signal'] = df['Ligne_MACD'].ewm(span=5, adjust=False).mean()
    def macd_decision(row):
        if pd.isna(row['Ligne_MACD']) or pd.isna(row['Ligne_Signal']): return "Attendre"
        if row['Ligne_MACD'] > row['Ligne_Signal']: return "Achat"
        elif row['Ligne_MACD'] < row['Ligne_Signal']: return "Vente"
        return "Neutre"
    df['deciMACD'] = df.apply(macd_decision, axis=1)
    return df

def calculate_rsi(df, price_col, period=10):
    delta = df[price_col].diff(1)
    gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
    loss = -delta.where(delta < 0, 0).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    def rsi_decision(row):
        if pd.isna(row['RSI']): return "Attendre"
        if row['RSI'] < 30: return "Achat"
        elif row['RSI'] > 70: return "Vente"
        return "Neutre"
    df['DeciRSI'] = df.apply(rsi_decision, axis=1)
    return df

def calculate_stochastic(df, price_col, k_period=10, d_period=3):
    rolling_high = df[price_col].rolling(window=k_period).max()
    rolling_low = df[price_col].rolling(window=k_period).min()
    denominator = (rolling_high - rolling_low).replace(0, np.nan)
    df['%K'] = 100 * ((df[price_col] - rolling_low) / denominator)
    df['%D'] = df['%K'].rolling(window=d_period).mean()
    def stochastic_decision(row):
        if pd.isna(row['%K']) or pd.isna(row['%D']): return "Attendre"
        if row['%K'] < 20 and row['%D'] < 20: return "Achat"
        elif row['%K'] > 80 and row['%D'] > 80: return "Vente"
        return "Neutre"
    df['deciStoc'] = df.apply(stochastic_decision, axis=1)
    return df

def process_single_sheet(gc, spreadsheet_id, sheet_name):
    try:
        spreadsheet = gc.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)

        if df.empty:
            logging.warning(f"  La feuille {sheet_name} est vide.")
            return False
        
        price_col = 'Cours (F CFA)'
        if price_col not in df.columns:
            logging.error(f"  ✗ Colonne '{price_col}' introuvable dans {sheet_name}")
            return False

        df[price_col] = pd.to_numeric(df[price_col], errors='coerce')
        df_clean = df.dropna(subset=[price_col]).reset_index(drop=True)

        if len(df_clean) < 50:
            logging.warning(f"  ✗ Pas assez de données pour {sheet_name} ({len(df_clean)} lignes)")
            return False

        logging.info(f"  Calcul des indicateurs pour {sheet_name}...")
        df_clean = calculate_moving_averages(df_clean, price_col)
        df_clean = calculate_bollinger_bands(df_clean, price_col)
        df_clean = calculate_macd(df_clean, price_col)
        df_clean = calculate_rsi(df_clean, price_col)
        df_clean = calculate_stochastic(df_clean, price_col)
        
        # Préparation des données pour l'écriture
        final_df = df_clean.drop(columns=[col for col in df.columns if col not in DEFAULT_HEADERS], errors='ignore')
        
        # Arrondir les valeurs numériques pour un affichage propre
        for col in ['MM5', 'MM10', 'MM20', 'MM50', 'Bande_Superieure', 'Bande_Inferieure', 'Ligne_MACD', 'Ligne_Signal', 'RSI', '%K', '%D']:
            if col in final_df.columns:
                final_df[col] = final_df[col].round(2)
        
        # Remplacer NaN par des chaînes vides
        final_df = final_df.fillna('')

        # Préparer les données pour la mise à jour par lot
        updates = []
        headers_to_write = ['MM5','MM10','MM20','MM50','MMdecision','Bande_Superieure','Bande_Inferieure','Boldecision','Ligne_MACD','Ligne_Signal','deciMACD','RSI','DeciRSI','%K','%D','deciStoc']
        
        # Mettre à jour les en-têtes (Colonnes F à Y)
        worksheet.update('F1:Y1', [[
            'MM5','MM10','MM20','MM50','MMdecision','','Bande_Superieure','Bande_Inferieure','Boldecision','','Ligne_MACD','Ligne_Signal','deciMACD','','RSI','DeciRSI','','%K','%D','deciStoc'
        ]])
        
        # Mettre à jour les données
        data_to_write = final_df[headers_to_write].values.tolist()
        worksheet.update(f'F2:Y{len(data_to_write)+1}', data_to_write)
        
        logging.info(f"  ✓ Traitement terminé pour {sheet_name}")
        return True

    except Exception as e:
        logging.error(f"  ✗ Erreur lors du traitement de {sheet_name}: {e}")
        return False

def main():
    spreadsheet_id = "1EGXyg13ml8a9zr4OaUPnJN3i-rwVO2uq330yfxJXnSM"
    gc = authenticate_gsheets()
    if not gc:
        return

    try:
        spreadsheet = gc.open_by_key(spreadsheet_id)
        logging.info(f"Fichier ouvert: {spreadsheet.title}")

        sheet_names = [ws.title for ws in spreadsheet.worksheets() if ws.title != "UNMATCHED"]
        logging.info(f"Feuilles à traiter: {sheet_names}")

        for sheet_name in sheet_names:
            logging.info(f"\n--- TRAITEMENT DE LA FEUILLE: {sheet_name} ---")
            
            # Pause pour gérer le quota de l'API Sheets
            time.sleep(2)
            
            convert_columns_to_numeric(gc, spreadsheet_id, sheet_name)
            
            # Une autre pause avant la prochaine série de lectures/écritures
            time.sleep(2)
            
            process_single_sheet(gc, spreadsheet_id, sheet_name)

    except Exception as e:
        logging.error(f"Erreur générale: {e}")

if __name__ == "__main__":
    logging.info("="*60)
    logging.info("DÉMARRAGE DE L'ANALYSE TECHNIQUE BRVM")
    logging.info("="*60)
    main()
