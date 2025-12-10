import os
import sqlite3
import pandas as pd
from typing import List, Dict, Any
from loguru import logger
from pathlib import Path

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

def insert_xlsx_to_db(data_path: str, db_path: str, tables_config: List[Dict[str, Any]] = None) -> None:
    """
    Converts Excel files in the data directory to a SQLite database.
    Uses tables_config to determine which files to load and how to map them to tables.
    """
    logger.info(f"Starting Excel to DB loading process for: {db_path}")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Remove existing DB to start fresh
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            logger.info(f"Removed existing database: {db_path}")
        except Exception as e:
            logger.warning(f"Could not remove existing database: {e}")

    data_dir = Path(data_path)
    if not data_dir.exists():
        logger.error(f"Data directory '{data_path}' does not exist.")
        return

    try:
        with get_db_connection(db_path) as conn:
            if tables_config:
                for table_cfg in tables_config:
                    table_name = table_cfg.get("table_name", "cfu_performance_data")
                    sources = table_cfg.get("sources", [])
                    
                    first_chunk = True
                    
                    for source in sources:
                        file_name = source.get("file_name")
                        sheet_names = source.get("sheet_names", [])
                        
                        if not file_name:
                            continue

                        file_path = data_dir / file_name
                        if not file_path.exists():
                            logger.warning(f"File not found: {file_name}")
                            continue
                            
                        logger.info(f"Processing {file_name} for table {table_name}...")
                        
                        try:
                            xl_file = pd.ExcelFile(file_path)
                            available_sheets = xl_file.sheet_names
                            
                            # If sheet_names is empty, use all available sheets
                            sheets_to_load = sheet_names if sheet_names else available_sheets
                            
                            for sheet in sheets_to_load:
                                if sheet not in available_sheets:
                                    logger.warning(f"Sheet '{sheet}' not found in {file_name}")
                                    continue
                                    
                                logger.info(f"Loading sheet: {sheet}")
                                df = pd.read_excel(file_path, sheet_name=sheet)
                                
                                # Clean columns
                                df.columns = [str(col).replace(" ", "_").replace("-", "_") for col in df.columns]
                                
                                # Write to DB
                                if_exists_mode = 'replace' if first_chunk else 'append'
                                df.to_sql(table_name, conn, if_exists=if_exists_mode, index=False)
                                logger.success(f"Wrote {len(df)} rows to '{table_name}' (Mode: {if_exists_mode})")
                                first_chunk = False
                                
                        except Exception as e:
                            logger.error(f"Error processing {file_name}: {e}")
            else:
                # Fallback: Process all Excel files if no config provided
                logger.warning("No tables_config provided. Processing all Excel files found.")
                excel_files = list(data_dir.glob("*.xlsx")) + list(data_dir.glob("*.xls"))
                
                if not excel_files:
                    logger.error(f"No Excel files found in '{data_path}'.")
                    return

                for excel_file in excel_files:
                    logger.info(f"Processing {excel_file.name}...")
                    try:
                        xl_file = pd.ExcelFile(excel_file)
                        for sheet_name in xl_file.sheet_names:
                            table_name = f"{excel_file.stem}_{sheet_name}".replace(" ", "_").replace("-", "_")
                            df = pd.read_excel(excel_file, sheet_name=sheet_name)
                            df.columns = [str(col).replace(" ", "_").replace("-", "_") for col in df.columns]
                            df.to_sql(table_name, conn, if_exists='replace', index=False)
                            logger.success(f"Created table '{table_name}'")
                    except Exception as e:
                        logger.error(f"Error processing {excel_file.name}: {e}")

            conn.commit()
            logger.success(f"Database successfully created at {db_path}")

    except Exception as e:
        logger.error(f"Error processing Excel files: {e}")
        raise