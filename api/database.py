import os
import sqlite3
import pandas as pd
from typing import List, Dict, Any
from loguru import logger

def get_db_connection(db_path: str):
    """Creates and returns a database connection with row factory for dict-like rows."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    return conn

def get_table_columns(db_path: str, table_name: str) -> List[str]:
    """Retrieves column names for a given table."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = cursor.fetchall()
        if columns_info:
            return [col[1] for col in columns_info]
        else:
            logger.warning(f"No columns found for table: {table_name}")
            return []
    except Exception as e:
        logger.error(f"Error getting columns for table {table_name}: {e}")
        raise

def execute_query(db_path: str, query: str) -> List[Dict[str, Any]]:
    """
    Executes a SQL query and returns the results as a list of dicts.
    If the query doesn't return rows (e.g., DML), returns an empty list.
    """
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            if cursor.description is None:
                logger.debug("Query executed with no row result set.")
                return []
            rows = cursor.fetchall()  # sqlite3.Row items
            dict_rows = [dict(row) for row in rows]
        return dict_rows
    except Exception as e:
        logger.error(f"Error executing query '{query}': {e}")
        raise

def _normalize_period(sheet_name: str) -> str:
    """
    Normalizes sheet name into a consistent period format (e.g., 'Jan24').
    """
    try:
        return pd.to_datetime(sheet_name, format='%m%Y').strftime('%b%y')
    except ValueError:
        try:
            return pd.to_datetime(sheet_name, format='%b%y').strftime('%b%y')
        except ValueError:
            logger.warning(f"Could not parse period from sheet name: {sheet_name}")
            return sheet_name

def insert_xlsx_to_db(data_path: str, db_path: str, tables_config: List[Dict[str, Any]]) -> None:
    """
    Reads data from multiple Excel files and sheets as defined in the config,
    handles multi-row headers, normalizes period, combines them, and saves
    them into a single table in SQLite.
    """
    logger.info(f"Starting Excel to DB loading process for: {db_path}")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    try:
        with get_db_connection(db_path) as conn:
            for config in tables_config:
                table_name = config["table_name"]
                sources = config.get("sources", [])
                
                if not sources:
                    logger.warning(f"Skipping table '{table_name}' due to missing 'sources' config.")
                    continue

                all_dataframes = []

                for source in sources:
                    excel_file_name = source.get("file_name")
                    sheet_list = source.get("sheet_names")

                    if not excel_file_name or not sheet_list:
                        logger.warning(f"Skipping a source in '{table_name}' due to missing config.")
                        continue

                    file_path = os.path.join(data_path, excel_file_name)
                    
                    if not os.path.isfile(file_path):
                        logger.error(f"Excel file not found: {file_path}")
                        continue

                    for sheet_name in sheet_list:
                        try:
                            df = pd.read_excel(file_path, sheet_name=sheet_name, header=[0, 1])
                            
                            new_columns = []
                            for col in df.columns:
                                level1 = str(col[0]).lower().replace(' ', '_').replace('.', '')
                                level2 = str(col[1]).lower().replace(' ', '_').replace('.', '')
                                if 'unnamed' in level1: new_col = level2
                                elif 'unnamed' in level2: new_col = level1
                                else: new_col = f"{level1}_{level2}"
                                new_col = new_col.replace('(', '').replace(')', '').replace('/', '_').replace('-', '_')
                                new_columns.append(new_col)
                            df.columns = new_columns
                            
                            df['period_source'] = _normalize_period(sheet_name)
                            
                            all_dataframes.append(df)
                            logger.debug(f"Successfully processed {len(df)} rows from sheet '{sheet_name}' in '{excel_file_name}'")
                        except Exception as e:
                            logger.error(f"Failed to process sheet '{sheet_name}' from '{excel_file_name}': {e}")
                
                if all_dataframes:
                    final_df = pd.concat(all_dataframes, ignore_index=True)
                    final_df.to_sql(table_name, conn, if_exists='replace', index=False)
                    logger.success(f"Successfully inserted {len(final_df)} total rows from {len(sources)} source(s) into table '{table_name}'.")
                else:
                    logger.warning(f"No dataframes were loaded to insert into table '{table_name}'.")

    except Exception as e:
        logger.error(f"Critical failure during Excel insertion: {e}")
        raise