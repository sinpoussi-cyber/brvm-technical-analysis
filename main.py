# ==============================================================================
# ANALYSE TECHNIQUE BRVM - V2.1 (GitHub Actions & Logique Métier Corrigée)
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
import logging

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

# --- Authentification via Compte de Service ---
def authenticate_gsheets():
    try:
        logging.info("Authentification via compte de service Google...")
        creds_json_str = os.environ.get('GSPREAD_SERVICE_ACCOUNT')
        if not creds_json_str:
            logging.error("❌ Secret GSPREAD_SERVICE_ACCOUNT introuvable.")
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
    if pd.isna(value) or value == '' or value is None: return np.nan
    str_value = re.sub(r'[^\d.,\-+]', '', str(value).strip()).replace(',', '.')
    try:
        return float(str_value)
    except (ValueError, TypeError):
        return np.nan

# ==============================================================================
# CORRECTION : Rajout de la fonction manquante
# ==============================================================================
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
def calculate_moving_averages(df, price_col='Cours (F CFA)'):
    logging.info("  -> Calcul des Moyennes Mobiles...")
    df['MM5'] = df[price_col].rolling(window=5).mean()
    df['MM10'] = df[price_col].rolling(window=10).mean()
    df['MM20'] = df[price_col].rolling(window=20).mean()
    df['MM50'] = df[price_col].rolling(window=50).mean()

    def mm_decision(row):
        price, mm5, mm10, mm20, mm50 = row[price_col], row['MM5'], row['MM10'], row['MM20'], row['MM50']
        if any(pd.isna(val) for val in [price, mm5, mm10, mm20, mm50]):
            return "Attendre"
        
        cond1 = (price > mm5) and (mm5 > mm10)
        cond2 = (mm5 > mm10) and (mm10 > mm20)
        cond3 = (mm10 > mm20) and (mm20 > mm50)
        
        if cond1 or cond2 or cond3:
            return "Achat"
        else:
            return "Vente"

    df['MMdecision'] = df.apply(mm_decision, axis=1)
    return df

def calculate_bollinger_bands(df, price_col='Cours (F CFA)', window=35, num_std=2):
    logging.info("  -> Calcul des Bandes de Bollinger...")
    df['Bande_centrale'] = df[price_col].rolling(window=window).mean()
    rolling_std = df[price_col].rolling(window=window).std()
    df['Bande_Supérieure'] = df['Bande_centrale'] + (rolling_std * num_std)
    df['Bande_Inferieure'] = df['Bande_centrale'] - (rolling_std * num_std)

    def bollinger_decision(row):
        price, lower, upper = row[price_col], row['Bande_Inferieure'], row['Bande_Supérieure']
        if any(pd.isna(val) for val in [price, lower, upper]):
            return "Attendre"
        if price <= lower: return "Achat"
        if price >= upper: return "Vente"
        return "Neutre"

    df['Boldecision'] = df.apply(bollinger_decision, axis=1)
    return df

def calculate_macd(df, price_col='Cours (F CFA)', fast=12, slow=26, signal=9):
    logging.info("  -> Calcul du MACD...")
    df['MME_fast'] = df[price_col].ewm(span=fast, adjust=False).mean()
    df['MME_slow'] = df[price_col].ewm(span=slow, adjust=False).mean()
    df['Ligne MACD'] = df['MME_fast'] - df['MME_slow']
    df['Ligne de signal'] = df['Ligne MACD'].ewm(span=signal, adjust=False).mean()
    df['Histogramme'] = df['Ligne MACD'] - df['Ligne de signal']

    def macd_decision(row, prev_row):
        histo = row['Histogramme']
        prev_histo = prev_row['Histogramme'] if prev_row is not None else 0
        if pd.isna(histo) or pd.isna(prev_histo): return "Attendre"

        if prev_histo <= 0 and histo > 0: return "Achat (Fort)"
        if prev_histo >= 0 and histo < 0: return "Vente (Fort)"
        
        if histo > 0: return "Achat"
        if histo < 0: return "Vente"
        
        return "Neutre"

    decisions = ["Attendre"] * len(df)
    for i in range(1, len(df)):
        decisions[i] = macd_decision(df.iloc[i], df.iloc[i-1])
    df['MACDdecision'] = decisions
    return df

def calculate_rsi(df, price_col='Cours (F CFA)', period=20):
    logging.info("  -> Calcul du RSI...")
    delta = df[price_col].diff(1)
    gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
    loss = -delta.where(delta < 0, 0).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RS'] = rs
    df['RSI'] = 100 - (100 / (1 + rs))

    def rsi_decision(row, prev_row):
        rsi = row['RSI']
        prev_rsi = prev_row['RSI'] if prev_row is not None else np.nan
        if pd.isna(rsi) or pd.isna(prev_rsi): return "Attendre"
        
        if prev_rsi <= 30 and rsi > 30: return "Achat"
        if prev_rsi >= 70 and rsi < 70: return "Vente"
        
        return "Neutre"

    decisions = ["Attendre"] * len(df)
    for i in range(1, len(df)):
        decisions[i] = rsi_decision(df.iloc[i], df.iloc[i-1])
    df['RSIdecision'] = decisions
    return df

def calculate_stochastic(df, price_col='Cours (F CFA)', k_period=20, d_period=5):
    logging.info("  -> Calcul du Stochastique...")
    rolling_high = df[price_col].rolling(window=k_period).max()
    rolling_low = df[price_col].rolling(window=k_period).min()
    denominator = (rolling_high - rolling_low).replace(0, np.nan)
    df['%K'] = 100 * ((df[price_col] - rolling_low) / denominator)
    df['%D'] = df['%K'].rolling(window=d_period).mean()

    def stochastic_decision(row, prev_row):
        k, d = row['%K'], row['%D']
        prev_k, prev_d = (prev_row['%K'], prev_row['%D']) if prev_row is not None else (np.nan, np.nan)
        if any(pd.isna(val) for val in [k, d, prev_k, prev_d]): return "Attendre"
        
        if prev_k <= prev_d and k > d and d < 20: return "Achat (Fort)"
        if prev_k >= prev_d and k < d and d > 80: return "Vente (Fort)"
        if prev_k <= prev_d and k > d: return "Achat"
        if prev_k >= prev_d and k < d: return "Vente"
        
        if d > 80: return "Surachat"
        if d < 20: return "Survente"
        
        return "Neutre"

    decisions = ["Attendre"] * len(df)
    for i in range(1, len(df)):
        decisions[i] = stochastic_decision(df.iloc[i], df.iloc[i-1])
    df['Stocdecision'] = decisions
    return df

def process_single_sheet(gc, spreadsheet_id, sheet_name):
    try:
        spreadsheet = gc.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        data = worksheet.get_all_records(numericise_ignore=['all'])
        df = pd.DataFrame(data)

        if df.empty:
            logging.warning(f"  La feuille {sheet_name} est vide.")
            return
        
        price_col = 'Cours (F CFA)'
        if price_col not in df.columns:
            logging.error(f"  ✗ Colonne '{price_col}' introuvable dans {sheet_name}")
            return

        df[price_col] = pd.to_numeric(df[price_col], errors='coerce')
        
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
            df = df.sort_values('Date').reset_index(drop=True)

        df_clean = df.dropna(subset=[price_col]).reset_index(drop=True)

        if len(df_clean) < 50:
            logging.warning(f"  ✗ Pas assez de données pour {sheet_name} ({len(df_clean)} lignes) pour calculer MM50.")
            return

        df_clean = calculate_moving_averages(df_clean, price_col)
        df_clean = calculate_bollinger_bands(df_clean, price_col)
        df_clean = calculate_macd(df_clean, price_col)
        df_clean = calculate_rsi(df_clean, price_col)
        df_clean = calculate_stochastic(df_clean, price_col)
        
        final_df = df.merge(df_clean, on=list(df.columns.intersection(df_clean.columns)), how='left')

        headers_to_write = ['MM5','MM10','MM20','MM50','MMdecision','Bande_centrale','Bande_Inferieure','Bande_Supérieure','Boldecision','Ligne MACD','Ligne de signal','Histogramme','MACDdecision','RS','RSI','RSIdecision','%K','%D','Stocdecision']
        
        df_to_write = final_df[headers_to_write].copy()
        numeric_cols = ['MM5','MM10','MM20','MM50','Bande_centrale','Bande_Supérieure','Bande_Inferieure','Ligne MACD','Ligne de signal','Histogramme','RS','RSI','%K','%D']
        for col in numeric_cols:
            df_to_write[col] = df_to_write[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
        
        worksheet.update('F1:X1', [[
            'MM5','MM10','MM20','MM50','MMdecision','Bande_centrale','Bande_Inferieure','Bande_Supérieure','Boldecision','Ligne MACD','Ligne de signal','Histogramme','MACDdecision','RS','RSI','RSIdecision','%K','%D','Stocdecision'
        ]])
        
        data_list = df_to_write.values.tolist()
        worksheet.update(f'F2:X{len(data_list)+1}', data_list)
        
        logging.info(f"  ✓ Traitement terminé pour {sheet_name}")

    except Exception as e:
        logging.error(f"  ✗ Erreur lors du traitement de {sheet_name}: {e}")

def main():
    spreadsheet_id = "1EGXyg13ml8a9zr4OaUPnJN3i-rwVO2uq330yfxJXnSM"
    gc = authenticate_gsheets()
    if not gc:
        return

    try:
        spreadsheet = gc.open_by_key(spreadsheet_id)
        logging.info(f"Fichier ouvert: {spreadsheet.title}")

        sheet_names = [ws.title for ws in spreadsheet.worksheets() if ws.title not in ["UNMATCHED", "Actions_BRVM"]]
        logging.info(f"Feuilles à traiter: {sheet_names}")

        for sheet_name in sheet_names:
            logging.info(f"\n--- TRAITEMENT DE LA FEUILLE: {sheet_name} ---")
            
            time.sleep(5)
            convert_columns_to_numeric(gc, spreadsheet_id, sheet_name)
            
            time.sleep(5)
            process_single_sheet(gc, spreadsheet_id, sheet_name)

    except Exception as e:
        logging.error(f"Erreur générale: {e}")

if __name__ == "__main__":
    logging.info("="*60)
    logging.info("DÉMARRAGE DE L'ANALYSE TECHNIQUE BRVM")
    logging.info("="*60)
    main()
