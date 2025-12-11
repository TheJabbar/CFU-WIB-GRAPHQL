# config.py
import os
from dotenv import load_dotenv
from typing import List, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings
from loguru import logger

from lib.prompt import create_generic_sql, greeting_and_general_prompt
from lib.cfu_prompt import (
    monthly_performance_prompt,
    trend_analysis_prompt,
    comparison_trend_prompt,
    underperforming_products_prompt,
    revenue_success_analysis_prompt,
    revenue_failure_analysis_prompt,
    ebitda_success_analysis_prompt,
    ebitda_failure_analysis_prompt,
    netincome_success_analysis_prompt,
    netincome_failure_analysis_prompt,
    negative_growth_products_prompt,
    ebitda_negative_growth_prompt,
    external_revenue_prompt,
    external_revenue_trend_prompt,
    top_contributing_segments_prompt,
    revenue_proportion_analysis_prompt,
)
from lib.general_q_prompt import cfu_wib_prompt

class Settings(BaseSettings):
    x_api_key: str = Field(..., env="X_API_KEY")
    URL_CUSTOM_LLM: str = Field(..., env="URL_CUSTOM_LLM")
    TOKEN_CUSTOM_LLM: str = Field(..., env="TOKEN_CUSTOM_LLM")

    # Paths
    data_path: str = "data/"
    database_api_path: str = os.path.join(data_path, "CFU_API.db")

    # Static Table Configuration for ETL (single consolidated table)
    tables_config: List[Dict[str, Any]] = [
        {
            "table_name": "cfu_performance_data",
            "table_description": (
                "A consolidated table containing all monthly performance data for CFU. "
                "Use this table for all queries about MTD/YTD performance, Achievement (ACH), "
                "Month-over-Month Growth (GMOM), Year-over-Year Growth (GYOY), Units, and "
                "hierarchy category levels L0 through L6."
            ),
            "sources": [
                {
                    "file_name": "telkomshareddp-dbv_cfuwibs_financial_performance-1765163852098.xlsx",
                    "sheet_names": [], # Empty list implies all sheets or auto-detection
                }
            ]
        }
    ]

    # Updated prompt configuration mapping
    prompt_config: List[Dict[str, Any]] = [
        {
            "prompt_name": "Greeting or General Question",
            "prompt_description": "Handles conversational greetings, introductions, and questions that are not related to data analysis.",
            "instruction_prompt": greeting_and_general_prompt,
        },
        {
            "prompt_name": "CFU Monthly Performance Analysis",
            "prompt_description": "Analyze division performance for specific period showing Revenue, COE, EBITDA, EBIT, EBT, Net Income with achievement and growth (MTD/YTD).",
            "instruction_prompt": monthly_performance_prompt,
        },
        {
            "prompt_name": "CFU Trend Analysis",
            "prompt_description": "Show Revenue/COE/EBITDA/EBIT/EBT/Net Income trends over multiple periods for specific division with monthly breakdown.",
            "instruction_prompt": trend_analysis_prompt,
        },
        {
            "prompt_name": "CFU Comparison Trend Analysis",
            "prompt_description": "Display trend comparison of actual vs target vs previous year for Revenue/COE/EBITDA/EBIT/EBT/Net Income over time periods.",
            "instruction_prompt": comparison_trend_prompt,
        },
        {
            "prompt_name": "CFU Underperforming Products Analysis",
            "prompt_description": "Identify products/categories with achievement below 100% for specific division, showing detailed product breakdown.",
            "instruction_prompt": underperforming_products_prompt,
        },
        {
            "prompt_name": "CFU Revenue Success Analysis",
            "prompt_description": "Analyze why revenue performance achieved target by finding products with 100%+ achievement and largest positive gaps.",
            "instruction_prompt": revenue_success_analysis_prompt,
        },
        {
            "prompt_name": "CFU Revenue Failure Analysis",
            "prompt_description": "Analyze why revenue performance failed by finding products with <100% achievement and largest negative gaps.",
            "instruction_prompt": revenue_failure_analysis_prompt,
        },
        {
            "prompt_name": "CFU EBITDA Success Analysis",
            "prompt_description": "Analyze EBITDA success by examining Revenue achievements and COE cost savings that contributed to EBITDA target achievement.",
            "instruction_prompt": ebitda_success_analysis_prompt,
        },
        {
            "prompt_name": "CFU EBITDA Failure Analysis",
            "prompt_description": "Analyze EBITDA failure by examining Revenue shortfalls and COE cost overruns that caused EBITDA underperformance.",
            "instruction_prompt": ebitda_failure_analysis_prompt,
        },
        {
            "prompt_name": "CFU Net Income Success Analysis",
            "prompt_description": "Analyze Net Income success by examining EBITDA and below-EBITDA factors like Depreciation, Amortization, Other Income.",
            "instruction_prompt": netincome_success_analysis_prompt,
        },
        {
            "prompt_name": "CFU Net Income Failure Analysis",
            "prompt_description": "Analyze Net Income failure by examining EBITDA shortfalls and negative below-EBITDA factors.",
            "instruction_prompt": netincome_failure_analysis_prompt,
        },
        {
            "prompt_name": "CFU Negative Growth Products Analysis",
            "prompt_description": "Identify products/categories with negative growth (GMOM < 0%) showing detailed product breakdown and growth rates.",
            "instruction_prompt": negative_growth_products_prompt,
        },
        {
            "prompt_name": "CFU EBITDA Negative Growth Analysis",
            "prompt_description": "Analyze EBITDA negative growth by examining Revenue decline and COE cost increases that impact EBITDA growth.",
            "instruction_prompt": ebitda_negative_growth_prompt,
        },
        {
            "prompt_name": "CFU External Revenue Analysis",
            "prompt_description": "Analyze External Revenue performance with achievement, growth metrics, and both MTD/YTD breakdown.",
            "instruction_prompt": external_revenue_prompt,
        },
        {
            "prompt_name": "CFU External Revenue Trend Analysis",
            "prompt_description": "Show External Revenue trend comparison of actual vs target vs previous year over multiple periods.",
            "instruction_prompt": external_revenue_trend_prompt,
        },
        {
            "prompt_name": "CFU WIB General Information",
            "prompt_description": "Provides general information about CFU WIB including its definition and components.",
            "instruction_prompt": cfu_wib_prompt,
        },
        {
            "prompt_name": "CFU Top Contributing Segments Analysis",
            "prompt_description": "Identify which business segments/divisions provide the largest contribution to Revenue, COE, and EBITDA for CFU WIB.",
            "instruction_prompt": top_contributing_segments_prompt,
        },
        {
            "prompt_name": "CFU Revenue Proportion Analysis",
            "prompt_description": "Calculate the proportion of revenue for a specific unit against total CFU WIB revenue and analyze trends over time.",
            "instruction_prompt": revenue_proportion_analysis_prompt,
        }
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

    def get_prompt_by_name(self, prompt_name: str) -> str:
        """
        Return the instruction prompt string for the given prompt name.
        Falls back to a generic prompt if the name is not found.
        """
        for prompt_entry in self.prompt_config:
            if prompt_entry.get("prompt_name") == prompt_name:
                return prompt_entry.get("instruction_prompt")

        logger.warning(
            f"Prompt '{prompt_name}' not found in config. Falling back to generic SQL creation."
        )
        return create_generic_sql

settings = Settings()