# app/utils.py
import os
from loguru import logger
from database import insert_xlsx_to_db
from config import settings

def load_initial_data():
    """Loads initial data from Excel into the database on startup."""
    try:
        db_path = settings.database_api_path
        data_path = settings.data_path
        
        if not os.path.exists(db_path):
            logger.info("Database not found. Starting data load process from Excel file...")
            insert_xlsx_to_db(
                data_path=data_path,
                tables_config=settings.tables_config,
                db_path=db_path
            )
            logger.success("Initial data load process complete.")
        else:
            logger.info(f"Database already exists at '{db_path}'. Skipping initial data load.")
            
    except Exception as e:
        logger.error(f"Initial data load failed: {e}")
        raise