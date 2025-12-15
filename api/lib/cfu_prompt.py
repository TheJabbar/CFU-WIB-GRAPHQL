import json
import os

# Load valid values from JSON
current_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(current_dir, 'valid_values.json')

try:
    with open(json_path, 'r') as f:
        valid_values_data = json.load(f)

    valid_values_str = f"""
Valid Values Reference:
- DIV: {valid_values_data['DIV']} (Note: 'CFU WIB' is the aggregate of these 5. 'WINS' is NOT supported.)
- PERIOD: [202401, ..., 202507] (integers)
- L2 Key Metrics: {valid_values_data['L2_Key_Metrics']}
- HIERARCHY REFERENCE (L2 -> L3 -> L4 -> L5 -> L6):
  L2 (Top Hierarchy): {valid_values_data['HIERARCHY_REFERENCE']['L2']}
  L3: {valid_values_data['HIERARCHY_REFERENCE']['L3']}
  L4: {valid_values_data['HIERARCHY_REFERENCE']['L4']}
  L5: {valid_values_data['HIERARCHY_REFERENCE']['L5']}
"""
except Exception as e:
    # Fallback if file not found
    valid_values_str = """
Valid Values Reference:
- DIV: ['DMT', 'DWS', 'TELIN', 'TIF', 'TSAT']
- PERIOD: [202401, ..., 202507] (integers)
- L2 Key Metrics: ['REVENUE', 'COE', 'EBITDA', 'EBIT', 'EBT', 'NET INCOME']
"""
    print(f"Warning: Could not load valid_values.json: {e}")

monthly_performance_prompt = f'''
Task: Generate a SQLite query to get performance data for a specific division and period. Filter metrics based on user request.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
- CFU WIB HANDLING (CRITICAL):
    - IF user says "CFU WIB" AND ("detail", "breakdown", "per unit", "per div") -> SELECT div ... GROUP BY div, l2, l3, l4. (Must show individual divisions).
    - IF user says "CFU WIB" ONLY -> SELECT 'CFU WIB' ... GROUP BY l2, l3, l4. (Must aggregate all divisions, do NOT group by div).
- METRIC FILTERING (CRITICAL):
    - IF user mentions specific metrics (e.g., "Revenue", "COE"), YOU MUST FILTER `l2` to ONLY those metrics.
    - Example: `AND l2 = 'REVENUE'` or `AND l2 IN ('REVENUE', 'COE')`.
    - DO NOT include other metrics even if the user says "performance" (e.g. "performance revenue" -> ONLY Revenue).
    - ONLY include all 6 metrics if user asks for "performance", "summary", or generic "data" WITHOUT specifying any metric name.
- IF user asks for "WINS", return a message that it is not supported.
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a period (e.g., "Juli 2025", "July 2025", "202507"), YOU MUST EXTRACT IT as integer YYYYMM (e.g., 202507) and use `period = 202507`.
    - DO NOT use `MAX(period)` if a specific period is requested.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- HIERARCHY LOGIC (Crucial):
  - To get the aggregate value for a level, filter the *next* level as '-'.
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 Aggregate: Filter `l4 = '-'`.
  - L4 Aggregate: Filter `l5 = '-'`.
  - L5 Aggregate: Filter `l6 = '-'`.
- Include both MTD and YTD for comprehensive view.
- ALWAYS include `period` in the SELECT clause to identify the time of data.
- Order by importance: REVENUE, COE, EBITDA, EBIT, EBT, NET INCOME.

Reference pattern 1 (Specific Metric - e.g. Revenue):
SELECT
    div,
    period,
    l2,
    l3,
    l4,
    SUM(real_mtd) AS real_mtd,
    ROUND(AVG(ach_mtd), 2) AS ach_mtd,
    ROUND(AVG(mom), 2) AS mom,
    SUM(real_ytd) AS real_ytd,
    ROUND(AVG(ach_ytd), 2) AS ach_ytd,
    ROUND(AVG(yoy), 2) AS yoy
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN'
    AND l2 = 'REVENUE' -- Filter ONLY for the requested metric
    AND l3 = '-'
GROUP BY period, div, l2, l3, l4;

Reference pattern 2 (Full Performance Summary):
SELECT
    div,
    period,
    l2,
    l3,
    l4,
    SUM(real_mtd) AS real_mtd,
    ROUND(AVG(ach_mtd), 2) AS ach_mtd,
    ROUND(AVG(mom), 2) AS mom,
    SUM(real_ytd) AS real_ytd,
    ROUND(AVG(ach_ytd), 2) AS ach_ytd,
    ROUND(AVG(yoy), 2) AS yoy
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN'
    AND l2 IN ('REVENUE', 'COE', 'EBITDA', 'EBIT', 'EBT', 'NET INCOME') -- Include ALL metrics
    AND l3 = '-'
GROUP BY period, div, l2, l3, l4
ORDER BY CASE l2
    WHEN 'REVENUE' THEN 1
    WHEN 'COE' THEN 2
    WHEN 'EBITDA' THEN 3
    WHEN 'EBIT' THEN 4
    WHEN 'EBT' THEN 5
    WHEN 'NET INCOME' THEN 6
    ELSE 7 END;
'''

trend_analysis_prompt = f'''
Task: Generate a SQLite query to show trends for Revenue/COE/EBITDA/EBIT/EBT/NET INCOME over multiple periods.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
- CFU WIB HANDLING (CRITICAL):
    - IF user says "CFU WIB" AND ("detail", "breakdown", "per unit", "per div") -> SELECT div ... GROUP BY period, div, l2, l3, l4.
    - IF user says "CFU WIB" ONLY -> SELECT 'CFU WIB' ... GROUP BY period, l2, l3, l4.
- For period ranges, use BETWEEN with integer periods.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 Aggregate: Filter `l4 = '-'`.
- METRIC FILTERING (CRITICAL):
    - IF user mentions specific metrics (e.g., "Revenue", "COE"), YOU MUST FILTER `l2` to ONLY those metrics.
    - Example: `AND l2 = 'REVENUE'` or `AND l2 IN ('REVENUE', 'COE')`.
    - DO NOT include other metrics even if the user says "performance" (e.g. "performance revenue" -> ONLY Revenue).
    - ONLY include all 6 metrics if user asks for "performance", "summary", or generic "data" WITHOUT specifying any metric name.
- Group by period and division for trend analysis.
- Include actual values for trend visualization.
- Order chronologically by period.

Reference pattern (Monthly trend for specific division - Default L2):
SELECT
    div,
    period,
    l2,
    l3,
    l4,
    SUM(real_mtd) AS real_mtd
FROM cfu_performance_data
WHERE period >= (SELECT MIN(period) FROM (SELECT DISTINCT period FROM cfu_performance_data ORDER BY period DESC LIMIT 6))
    AND div = 'TELIN'
    AND l2 IN ('REVENUE', 'COE', 'EBITDA', 'EBIT', 'EBT', 'NET INCOME') -- CHANGE THIS if user asks for specific metric
    AND l3 = '-' -- Get L2 Aggregate
GROUP BY period, div, l2, l3, l4
ORDER BY period ASC, CASE l2
    WHEN 'REVENUE' THEN 1
    WHEN 'COE' THEN 2
    WHEN 'EBITDA' THEN 3
    WHEN 'EBIT' THEN 4
    WHEN 'EBT' THEN 5
    WHEN 'NET INCOME' THEN 6
    ELSE 7 END;
'''

comparison_trend_prompt = f'''
Task: Generate a SQLite query to compare actual, target, and prev year values over time periods.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
- CFU WIB HANDLING (CRITICAL):
    - IF user says "CFU WIB" AND ("detail", "breakdown", "per unit", "per div") -> SELECT div ... GROUP BY period, div, l2, l3, l4.
    - IF user says "CFU WIB" ONLY -> SELECT 'CFU WIB' ... GROUP BY period, l2, l3, l4.
- Include actual, target, and previous year data.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 Aggregate: Filter `l4 = '-'`.
- METRIC FILTERING (CRITICAL):
    - IF user mentions specific metrics (e.g., "Revenue", "COE"), YOU MUST FILTER `l2` to ONLY those metrics.
    - Example: `AND l2 = 'REVENUE'` or `AND l2 IN ('REVENUE', 'COE')`.
    - DO NOT include other metrics even if the user says "performance" (e.g. "performance revenue" -> ONLY Revenue).
    - ONLY include all 6 metrics if user asks for "performance", "summary", or generic "data" WITHOUT specifying any metric name.
- Group by period for time series comparison.

Reference pattern (Comparison trend for division - Default L2):
SELECT
    div,
    period,
    l2,
    l3,
    l4,
    SUM(real_mtd) AS real_mtd,
    SUM(target_mtd) AS target_mtd,
    SUM(prev_year) AS prev_year -- Note: Using prev_year column
FROM cfu_performance_data
WHERE period >= (SELECT MIN(period) FROM (SELECT DISTINCT period FROM cfu_performance_data ORDER BY period DESC LIMIT 6))
    AND div = 'TELIN'
    AND l2 IN ('REVENUE', 'COE', 'EBITDA', 'EBIT', 'EBT', 'NET INCOME') -- CHANGE THIS if user asks for specific metric
    AND l3 = '-' -- Get L2 Aggregate
GROUP BY period, div, l2, l3, l4
ORDER BY period ASC;
'''

underperforming_products_prompt = f'''
Task: Find products/categories with achievement < 100% for a specific division.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
- IF user asks for "CFU WIB", do NOT filter by `div`.
- Filter for underperforming: ach_ytd < 100.
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a single period (e.g. "March 2025"), use `period = 202503`.
    - IF user specifies a RANGE (e.g. "March to May 2025"), use `period BETWEEN 202503 AND 202505`.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- Show detailed breakdown using L3/L4 levels (Filter l5 = '-' to get L4 items).
- ORDERING (CRITICAL):
    1. Filter for underperformance (`ach_ytd < 100`).
    2. Select top worst performers (lowest achievement) first (e.g. LIMIT 50).
    3. THEN, order the final result by: `period ASC`, then `l2` (Revenue -> Net Income), then `l3`, `l4`.
    - Use a SUBQUERY to achieve "Top Worst" filtering + "Chronological/Hierarchical" display sorting.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (Underperforming products - Sorted Chronologically & Hierarchically):
SELECT * FROM (
    SELECT
        div,
        period,
        l2,
        l3,
        l4,
        SUM(real_ytd) AS real_ytd,
        ROUND(AVG(ach_ytd), 2) AS ach_ytd,
        ROUND(AVG(yoy), 2) AS yoy
    FROM cfu_performance_data
    WHERE period BETWEEN 202503 AND 202505 -- Example range
        AND div = 'TELIN'
        AND ach_ytd < 100
        AND l5 = '-' -- Get L4 items
    GROUP BY period, div, l2, l3, l4
    ORDER BY ach_ytd ASC
    LIMIT 50 -- Top 50 worst performers
)
ORDER BY period ASC,
    CASE l2
        WHEN 'REVENUE' THEN 1
        WHEN 'COE' THEN 2
        WHEN 'EBITDA' THEN 3
        WHEN 'EBIT' THEN 4
        WHEN 'EBT' THEN 5
        WHEN 'NET INCOME' THEN 6
        ELSE 7 END,
    l3, l4;
'''

revenue_success_analysis_prompt = f'''
Task: Find revenue products with achievement > 100% and largest positive gaps for a division.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
- Filter for: l2 = 'REVENUE' AND ach_ytd > 100.
- Calculate positive gap: actual - target.
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a single period (e.g. "March 2025"), use `period = 202503`.
    - IF user specifies a RANGE (e.g. "March to May 2025"), use `period BETWEEN 202503 AND 202505`.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- ORDERING (CRITICAL):
    1. Filter for success (`ach_ytd > 100`).
    2. Select top best performers (largest positive gap) first (e.g. LIMIT 50).
    3. THEN, order the final result by: `period ASC`, then `l3`, `l4`.
    - Use a SUBQUERY to achieve "Top Best" filtering + "Chronological/Hierarchical" display sorting.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (Revenue success factors - Sorted Chronologically & Hierarchically):
SELECT * FROM (
    SELECT
        div,
        period,
        l3,
        l4,
        ROUND(AVG(ach_ytd), 2) AS ach_ytd,
        SUM(real_ytd) AS real_ytd,
        ROUND(AVG(yoy), 2) AS yoy,
        (SUM(real_ytd) - SUM(target_ytd)) AS gap_val
    FROM cfu_performance_data
    WHERE period BETWEEN 202503 AND 202505
        AND div = 'TELIN'
        AND l2 = 'REVENUE' AND ach_ytd > 100
        AND l5 = '-' -- Get L4 items
    GROUP BY period, div, l3, l4
    ORDER BY gap_val DESC
    LIMIT 50 -- Top 50 best performers
)
ORDER BY period ASC, l3, l4;
'''

revenue_failure_analysis_prompt = f'''
Task: Find revenue products with achievement < 100% and largest negative gaps for a division.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
- Filter for: l2 = 'REVENUE' AND ach_ytd < 100.
- Calculate negative gap: target - actual (shortfall).
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a single period (e.g. "March 2025"), use `period = 202503`.
    - IF user specifies a RANGE (e.g. "March to May 2025"), use `period BETWEEN 202503 AND 202505`.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- ORDERING (CRITICAL):
    1. Filter for failure (`ach_ytd < 100`).
    2. Select top worst performers (largest shortfall) first (e.g. LIMIT 50).
    3. THEN, order the final result by: `period ASC`, then `l3`, `l4`.
    - Use a SUBQUERY to achieve "Top Worst" filtering + "Chronological/Hierarchical" display sorting.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (Revenue failure factors - Sorted Chronologically & Hierarchically):
SELECT * FROM (
    SELECT
        div,
        period,
        l3,
        l4,
        ROUND(AVG(ach_ytd), 2) AS ach_ytd,
        SUM(real_ytd) AS real_ytd,
        ROUND(AVG(yoy), 2) AS yoy,
        (SUM(target_ytd) - SUM(real_ytd)) AS shortfall_val
    FROM cfu_performance_data
    WHERE period BETWEEN 202503 AND 202505
        AND div = 'TELIN'
        AND l2 = 'REVENUE' AND ach_ytd < 100
        AND l5 = '-' -- Get L4 items
    GROUP BY period, div, l3, l4
    ORDER BY shortfall_val DESC
    LIMIT 50 -- Top 50 worst performers
)
ORDER BY period ASC, l3, l4;
'''

ebitda_success_analysis_prompt = f'''
Task: Analyze why EBITDA achieved target by examining Revenue success and COE underperformance.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
- Check Revenue products with achievement > 100%.
- Check COE categories with achievement < 100% (cost savings).
- EBITDA = Revenue - COE, so high revenue + low COE = good EBITDA.
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a single period (e.g. "March 2025"), use `period = 202503`.
    - IF user specifies a RANGE (e.g. "March to May 2025"), use `period BETWEEN 202503 AND 202505`.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- ORDERING (CRITICAL):
    1. Filter for positive impact factors.
    2. Select top contributors (largest gap) first (e.g. LIMIT 20).
    3. THEN, order the final result by: `period ASC`, then `l2` (Revenue -> COE), then `l3`.
    - Use a SUBQUERY to achieve "Top Contributors" filtering + "Chronological/Hierarchical" display sorting.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (EBITDA success factors - Sorted Chronologically & Hierarchically):
SELECT * FROM (
    SELECT
        div,
        period,
        l2,
        l3,
        ROUND(AVG(ach_ytd), 2) AS ach_ytd,
        (SUM(real_ytd) - SUM(target_ytd)) AS gap_mtd,
        CASE
            WHEN l2 = 'REVENUE' AND AVG(ach_ytd) > 100 THEN 'Revenue Driver'
            WHEN l2 = 'COE' AND AVG(ach_ytd) < 100 THEN 'Cost Savings'
            ELSE 'Other Factor'
        END AS ebitda_impact
    FROM cfu_performance_data
    WHERE period BETWEEN 202503 AND 202505
        AND div = 'TELIN'
        AND l2 IN ('REVENUE', 'COE')
        AND ((l2 = 'REVENUE' AND ach_ytd > 100)
             OR (l2 = 'COE' AND ach_ytd < 100))
        AND l4 = '-' -- Get L3 items
    GROUP BY period, div, l2, l3
    ORDER BY gap_mtd DESC
    LIMIT 20 -- Top 20 contributors
)
ORDER BY period ASC,
    CASE l2 WHEN 'REVENUE' THEN 1 WHEN 'COE' THEN 2 ELSE 3 END,
    l3;
'''

ebitda_failure_analysis_prompt = f'''
Task: Analyze why EBITDA failed to achieve target by examining Revenue shortfalls and COE overruns.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
- Check Revenue products with achievement < 100% (revenue shortfall).
- Check COE categories with achievement > 100% (cost overrun).
- Focus on largest negative impacts.
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a single period (e.g. "March 2025"), use `period = 202503`.
    - IF user specifies a RANGE (e.g. "March to May 2025"), use `period BETWEEN 202503 AND 202505`.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- ORDERING (CRITICAL):
    1. Filter for negative impact factors.
    2. Select top negative contributors (largest negative impact) first (e.g. LIMIT 20).
    3. THEN, order the final result by: `period ASC`, then `l2` (Revenue -> COE), then `l3`.
    - Use a SUBQUERY to achieve "Top Negative Contributors" filtering + "Chronological/Hierarchical" display sorting.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (EBITDA failure factors - Sorted Chronologically & Hierarchically):
SELECT * FROM (
    SELECT
        div,
        period,
        l2,
        l3,
        ROUND(AVG(ach_ytd), 2) AS ach_ytd,
        (SUM(real_ytd) - SUM(target_ytd)) AS negative_impact,
        CASE
            WHEN l2 = 'REVENUE' AND AVG(ach_ytd) < 100 THEN 'Revenue Shortfall'
            WHEN l2 = 'COE' AND AVG(ach_ytd) > 100 THEN 'Cost Overrun'
            ELSE 'Other Factor'
        END AS ebitda_drag
    FROM cfu_performance_data
    WHERE period BETWEEN 202503 AND 202505
        AND div = 'TELIN'
        AND l2 IN ('REVENUE', 'COE')
        AND ((l2 = 'REVENUE' AND ach_ytd < 100)
             OR (l2 = 'COE' AND ach_ytd > 100))
        AND l4 = '-' -- Get L3 items
    GROUP BY period, div, l2, l3
    ORDER BY negative_impact DESC
    LIMIT 20 -- Top 20 negative contributors
)
ORDER BY period ASC,
    CASE l2 WHEN 'REVENUE' THEN 1 WHEN 'COE' THEN 2 ELSE 3 END,
    l3;
'''

netincome_success_analysis_prompt = f'''
Task: Analyze Net Income success by examining EBITDA and below-EBITDA factors.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
- Check EBITDA achievement.
- Look for Depreciation/Amortization underperformance (cost savings).
- Look for Other Income overperformance.
- Use L3 level for detailed analysis.
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a single period (e.g. "March 2025"), use `period = 202503`.
    - IF user specifies a RANGE (e.g. "March to May 2025"), use `period BETWEEN 202503 AND 202505`.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- ORDERING (CRITICAL):
    1. Filter for positive contribution factors.
    2. Select top contributors (largest contribution) first (e.g. LIMIT 20).
    3. THEN, order the final result by: `period ASC`, then `l2` (EBITDA first), then `l3`.
    - Use a SUBQUERY to achieve "Top Contributors" filtering + "Chronological/Hierarchical" display sorting.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (Net Income success factors - Sorted Chronologically & Hierarchically):
SELECT * FROM (
    SELECT
        div,
        period,
        l2,
        l3,
        ROUND(AVG(ach_ytd), 2) AS ach_ytd,
        (SUM(real_ytd) - SUM(target_ytd)) AS contribution,
        CASE
            WHEN l2 = 'EBITDA' AND AVG(ach_mtd) > 100 THEN 'Core Business Success'
            WHEN l3 LIKE '%Depreciation%' AND AVG(ach_mtd) < 100 THEN 'Depreciation Savings'
            WHEN l3 LIKE '%Amortization%' AND AVG(ach_mtd) < 100 THEN 'Amortization Savings'
            WHEN l3 LIKE '%Other Income%' AND AVG(ach_mtd) > 100 THEN 'Other Income Boost'
            ELSE 'Other Factor'
        END AS netincome_driver
    FROM cfu_performance_data
    WHERE period BETWEEN 202503 AND 202505
        AND div = 'TELIN'
        AND (l2 = 'EBITDA' OR l3 LIKE '%Depreciation%' OR l3 LIKE '%Amortization%'
             OR l3 LIKE '%Other Income%')
        AND l4 = '-' -- Get L3 items
    GROUP BY period, div, l2, l3
    ORDER BY contribution DESC
    LIMIT 20 -- Top 20 contributors
)
ORDER BY period ASC,
    CASE l2 WHEN 'EBITDA' THEN 1 ELSE 2 END,
    l3;
'''

netincome_failure_analysis_prompt = f'''
Task: Analyze Net Income failure by examining EBITDA and below-EBITDA negative factors.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
- Check EBITDA underperformance.
- Look for Depreciation/Amortization overruns.
- Look for Other Income shortfalls.
- Focus on largest negative impacts.
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a single period (e.g. "March 2025"), use `period = 202503`.
    - IF user specifies a RANGE (e.g. "March to May 2025"), use `period BETWEEN 202503 AND 202505`.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- ORDERING (CRITICAL):
    1. Filter for negative impact factors.
    2. Select top negative contributors (largest negative impact) first (e.g. LIMIT 20).
    3. THEN, order the final result by: `period ASC`, then `l2` (EBITDA first), then `l3`.
    - Use a SUBQUERY to achieve "Top Negative Contributors" filtering + "Chronological/Hierarchical" display sorting.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (Net Income failure factors - Sorted Chronologically & Hierarchically):
SELECT * FROM (
    SELECT
        div,
        period,
        l2,
        l3,
        ROUND(AVG(ach_ytd), 2) AS ach_ytd,
        (SUM(real_ytd) - SUM(target_ytd)) AS negative_impact,
        CASE
            WHEN l2 = 'EBITDA' AND AVG(ach_mtd) < 100 THEN 'Core Business Issues'
            WHEN l3 LIKE '%Depreciation%' AND AVG(ach_mtd) > 100 THEN 'Higher Depreciation'
            WHEN l3 LIKE '%Amortization%' AND AVG(ach_mtd) > 100 THEN 'Higher Amortization'
            WHEN l3 LIKE '%Other Income%' AND AVG(ach_mtd) < 100 THEN 'Other Income Shortfall'
            ELSE 'Other Factor'
        END AS netincome_drag
    FROM cfu_performance_data
    WHERE period BETWEEN 202503 AND 202505
        AND div = 'TELIN'
        AND (l2 = 'EBITDA' OR l3 LIKE '%Depreciation%' OR l3 LIKE '%Amortization%'
             OR l3 LIKE '%Other Income%')
        AND l4 = '-' -- Get L3 items
    GROUP BY period, div, l2, l3
    ORDER BY negative_impact DESC
    LIMIT 20 -- Top 20 negative contributors
)
ORDER BY period ASC,
    CASE l2 WHEN 'EBITDA' THEN 1 ELSE 2 END,
    l3;
'''

negative_growth_products_prompt = f'''
Task: Find products with negative growth (MoM < 0%) for a specific division.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
- Filter for: mom < 0.
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a single period (e.g. "March 2025"), use `period = 202503`.
    - IF user specifies a RANGE (e.g. "March to May 2025"), use `period BETWEEN 202503 AND 202505`.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- Show product details with L3/L4 breakdown.
- Include YTD metrics for context.
- ORDERING (CRITICAL):
    1. Filter for negative growth (`mom < 0`).
    2. Select top worst performers (lowest MoM) first (e.g. LIMIT 50).
    3. THEN, order the final result by: `period ASC`, then `l2` (Revenue -> Net Income), then `l3`, `l4`.
    - Use a SUBQUERY to achieve "Top Worst" filtering + "Chronological/Hierarchical" display sorting.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (Negative growth products - Sorted Chronologically & Hierarchically):
SELECT * FROM (
    SELECT
        div,
        period,
        l2,
        l3,
        l4,
        ROUND(AVG(mom), 2) AS mom,
        ROUND(AVG(yoy), 2) AS yoy,
        SUM(real_mtd) AS real_mtd,
        SUM(real_ytd) AS real_ytd
    FROM cfu_performance_data
    WHERE period BETWEEN 202503 AND 202505 -- Example range
        AND div = 'TELIN'
        AND mom < 0
        AND l5 = '-' -- Get L4 items
    GROUP BY period, div, l2, l3, l4
    ORDER BY mom ASC
    LIMIT 50 -- Get top 50 worst performers first
)
ORDER BY period ASC,
    CASE l2
        WHEN 'REVENUE' THEN 1
        WHEN 'COE' THEN 2
        WHEN 'EBITDA' THEN 3
        WHEN 'EBIT' THEN 4
        WHEN 'EBT' THEN 5
        WHEN 'NET INCOME' THEN 6
        ELSE 7 END,
    l3, l4;
'''

ebitda_negative_growth_prompt = f'''
Task: Analyze why EBITDA has negative growth by checking Revenue and COE growth patterns.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
- Check Revenue products with negative growth (mom < 0).
- Check COE categories with positive growth (mom > 0) - increasing costs.
- Focus on significant contributors.
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a single period (e.g. "March 2025"), use `period = 202503`.
    - IF user specifies a RANGE (e.g. "March to May 2025"), use `period BETWEEN 202503 AND 202505`.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- ORDERING (CRITICAL):
    1. Filter for negative growth factors.
    2. Select top contributors (largest absolute MoM change) first (e.g. LIMIT 20).
    3. THEN, order the final result by: `period ASC`, then `l2` (Revenue -> COE), then `l3`.
    - Use a SUBQUERY to achieve "Top Contributors" filtering + "Chronological/Hierarchical" display sorting.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (EBITDA negative growth analysis - Sorted Chronologically & Hierarchically):
SELECT * FROM (
    SELECT
        div,
        period,
        l2,
        l3,
        ROUND(AVG(mom), 2) AS mom,
        SUM(real_mtd) AS real_mtd,
        CASE
            WHEN l2 = 'REVENUE' AND AVG(mom) < 0 THEN 'Revenue Declining'
            WHEN l2 = 'COE' AND AVG(mom) > 0 THEN 'Costs Increasing'
            ELSE 'Other Factor'
        END AS ebitda_growth_impact
    FROM cfu_performance_data
    WHERE period BETWEEN 202503 AND 202505
        AND div = 'TELIN'
        AND l2 IN ('REVENUE', 'COE')
        AND ((l2 = 'REVENUE' AND mom < 0) OR (l2 = 'COE' AND mom > 0))
        AND l4 = '-' -- Get L3 items
    GROUP BY period, div, l2, l3
    ORDER BY ABS(mom) DESC
    LIMIT 20 -- Top 20 contributors
)
ORDER BY period ASC,
    CASE l2 WHEN 'REVENUE' THEN 1 WHEN 'COE' THEN 2 ELSE 3 END,
    l3;
'''

external_revenue_prompt = f'''
Task: Generate a SQLite query to calculate External Revenue performance (actual, achievement, growth) for a given division and period.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
- Focus on External Revenue only → check L3 or L4 containing "External".
- Show detailed breakdown by L3 and L4 to identify specific external revenue streams.
- Must include: actual MTD, actual YTD, achievement MTD, achievement YTD, growth MoM, growth YoY.
- Order by actual MTD descending.
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a period (e.g., "Juli 2025", "July 2025", "202507"), YOU MUST EXTRACT IT as integer YYYYMM (e.g., 202507) and use `period = 202507`.
    - DO NOT use `MAX(period)` if a specific period is requested.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (External Revenue breakdown):
SELECT
    div,
    period,
    l3,
    l4,
    SUM(real_mtd) AS real_mtd,
    SUM(real_ytd) AS real_ytd,
    ROUND(AVG(ach_mtd), 2) AS ach_mtd,
    ROUND(AVG(ach_ytd), 2) AS ach_ytd,
    ROUND(AVG(mom), 2) AS mom,
    ROUND(AVG(yoy), 2) AS yoy
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
  AND div = 'TELIN'
  AND (l3 LIKE '%External%' OR l4 LIKE '%External%')
  AND l5 = '-' -- Get L4 items
GROUP BY period, div, l3, l4
ORDER BY real_mtd DESC;
'''

external_revenue_trend_prompt = f'''
Task: Show External Revenue trend comparison (actual, target, prev year) over multiple periods.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
- Look for External revenue categories (L3 or L4).
- Group by period for trend analysis.
- Include actual, target, and previous year data.
- Order chronologically.

Reference pattern (External Revenue trend):
SELECT
    div,
    period,
    SUM(real_mtd) AS real_mtd,
    SUM(target_mtd) AS target_mtd,
    SUM(prev_year) AS prev_year (but if user wants prev month, use prev_month instead)
FROM cfu_performance_data
WHERE period >= (SELECT MIN(period) FROM (SELECT DISTINCT period FROM cfu_performance_data ORDER BY period DESC LIMIT 6))
    AND div = 'TELIN'
    AND (l2 = 'REVENUE')
    AND (l3 LIKE '%External%' OR l4 LIKE '%External%')
    AND l5 = '-' -- Get L4 items
GROUP BY period, div
ORDER BY period ASC;
'''

top_contributing_segments_prompt = f'''
Task: Find the business segments/divisions that contribute the most to Revenue, COE, EBITDA, and Net Income for CFU WIB by analyzing actual values and their percentages against the total.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!
{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- CFU WIB HANDLING (CRITICAL):
    - IF user says "CFU WIB", aggregate across all divisions to show each unit's contribution.
- Focus on identifying top contributing business segments per metric (Revenue, COE, EBITDA, Net Income).
- Use latest period (use subquery: SELECT MAX(period) FROM cfu_performance_data) unless specified.
- Must handle queries for:
  - "which segment contributes most to revenue?" → Calculate actual revenue for each unit and percentage of total CFU WIB revenue
  - "which unit gives highest COE?" → Calculate actual COE for each unit and percentage of total CFU WIB COE
  - "which business unit has highest EBITDA contribution?" → Calculate actual EBITDA for each unit and percentage of total CFU WIB EBITDA
  - "Segmen / Unit bisnis apa yang memberikan kontribusi Net Income terbesar untuk CFU WIB?" → Calculate actual Net Income for each unit and percentage of total CFU WIB Net Income
- For each metric, show: unit name, actual value, and percentage of total.
- Calculate percentages by dividing each unit's actual by the total for all divisions combined.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 Aggregate: Filter `l4 = '-'`.
- ORDER BY actual value descending to show highest contributors first.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (Top contributing segments with percentages):
-- Calculate actual revenue for each unit and percentage of total CFU WIB revenue
SELECT
    div AS unit_name,
    SUM(real_mtd) AS actual_value,
    ROUND(SUM(real_mtd) * 100.0 / (SELECT SUM(real_mtd) FROM cfu_performance_data WHERE period = (SELECT MAX(period) FROM cfu_performance_data) AND l2 = 'REVENUE' AND l3 = '-' AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS percentage_of_total
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT') -- Only valid divisions for CFU WIB
    AND l2 = 'REVENUE' -- For revenue analysis
    AND l3 = '-' -- Get L2 aggregates
GROUP BY period, div
ORDER BY actual_value DESC;

-- Calculate actual COE for each unit and percentage of total CFU WIB COE
SELECT
    div AS unit_name,
    SUM(real_mtd) AS actual_value,
    ROUND(SUM(real_mtd) * 100.0 / (SELECT SUM(real_mtd) FROM cfu_performance_data WHERE period = (SELECT MAX(period) FROM cfu_performance_data) AND l2 = 'COE' AND l3 = '-' AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS percentage_of_total
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT') -- Only valid divisions for CFU WIB
    AND l2 = 'COE' -- For COE analysis
    AND l3 = '-' -- Get L2 aggregates
GROUP BY period, div
ORDER BY actual_value DESC;

-- Calculate actual EBITDA for each unit and percentage of total CFU WIB EBITDA
SELECT
    div AS unit_name,
    SUM(real_mtd) AS actual_value,
    ROUND(SUM(real_mtd) * 100.0 / (SELECT SUM(real_mtd) FROM cfu_performance_data WHERE period = (SELECT MAX(period) FROM cfu_performance_data) AND l2 = 'EBITDA' AND l3 = '-' AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS percentage_of_total
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT') -- Only valid divisions for CFU WIB
    AND l2 = 'EBITDA' -- For EBITDA analysis
    AND l3 = '-' -- Get L2 aggregates
GROUP BY period, div
ORDER BY actual_value DESC;

-- Calculate actual Net Income for each unit and percentage of total CFU WIB Net Income
SELECT
    div AS unit_name,
    SUM(real_mtd) AS actual_value,
    ROUND(SUM(real_mtd) * 100.0 / (SELECT SUM(real_mtd) FROM cfu_performance_data WHERE period = (SELECT MAX(period) FROM cfu_performance_data) AND l2 = 'NET INCOME' AND l3 = '-' AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS percentage_of_total
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT') -- Only valid divisions for CFU WIB
    AND l2 = 'NET INCOME' -- For Net Income analysis
    AND l3 = '-' -- Get L2 aggregates
GROUP BY period, div
ORDER BY actual_value DESC;
'''

revenue_proportion_analysis_prompt = f'''
Task: Calculate the proportion of revenue for a specific unit against total CFU WIB revenue and analyze trends over time.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!
{valid_values_str}
Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Handle the following specific queries:
  - "Berapa besar porsi revenue [unit] terhadap total CFU WIB?" → Calculate percentage of specified unit's revenue against total CFU WIB revenue for the latest period
  - "Bagaimana tren porsi revenue [unit] terhadap CFU WIB selama 3 tahun terakhir?" → Show annual trend of the unit's revenue percentage against total CFU WIB revenue for the last 3 years
  - "Bagaimana tren porsi revenue [unit] terhadap CFU WIB dalam tahun ini?" → Show monthly trend of the unit's revenue percentage against total CFU WIB revenue for the current year
- Calculate percentages by dividing unit revenue by total CFU WIB revenue and multiplying by 100.
- For single period: Use latest period from (SELECT MAX(period) FROM cfu_performance_data)
- For 3-year annual trend: Convert period to year and aggregate by year
- For current year monthly trend: Filter for current year and show monthly breakdowns
- ALWAYS include both actual values and percentages in the results
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.

Reference pattern 1 (Single Period Proportion): Calculate the portion of a specific unit's revenue against total CFU WIB revenue
SELECT
    div AS unit_name,
    period,
    SUM(real_mtd) AS unit_revenue,
    (SELECT SUM(real_mtd) FROM cfu_performance_data WHERE period = (SELECT MAX(period) FROM cfu_performance_data) AND l2 = 'REVENUE' AND l3 = '-' AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')) AS total_cfu_wib_revenue,
    ROUND(SUM(real_mtd) * 100.0 / (SELECT SUM(real_mtd) FROM cfu_performance_data WHERE period = (SELECT MAX(period) FROM cfu_performance_data) AND l2 = 'REVENUE' AND l3 = '-' AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS percentage_of_total
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN' -- Replace with specified unit
    AND l2 = 'REVENUE'
    AND l3 = '-' -- Get L2 aggregate
GROUP BY period, div;

Reference pattern 2 (3-Year Annual Trend): Show how a unit's revenue proportion has changed over the last 3 years
SELECT
    div AS unit_name,
    CAST(period AS TEXT) AS year, -- Extract year from period
    SUBSTR(CAST(period AS TEXT), 1, 4) AS year_only, -- Get year part from period (YYYYMM format)
    SUM(real_mtd) AS unit_revenue,
    (SELECT SUM(real_mtd) FROM cfu_performance_data c2 WHERE SUBSTR(CAST(c2.period AS TEXT), 1, 4) = SUBSTR(CAST(c1.period AS TEXT), 1, 4) AND c2.l2 = 'REVENUE' AND c2.l3 = '-' AND c2.div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')) AS total_yearly_cfu_wib_revenue,
    ROUND(SUM(real_mtd) * 100.0 / (SELECT SUM(real_mtd) FROM cfu_performance_data c3 WHERE SUBSTR(CAST(c3.period AS TEXT), 1, 4) = SUBSTR(CAST(c1.period AS TEXT), 1, 4) AND c3.l2 = 'REVENUE' AND c3.l3 = '-' AND c3.div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS percentage_of_total
FROM cfu_performance_data c1
WHERE SUBSTR(CAST(period AS TEXT), 1, 4) IN (
    SELECT DISTINCT SUBSTR(CAST(period AS TEXT), 1, 4)
    FROM cfu_performance_data
    ORDER BY period DESC
    LIMIT 3 -- Get last 3 years
)
    AND div = 'TELIN' -- Replace with specified unit
    AND l2 = 'REVENUE'
    AND l3 = '-' -- Get L2 aggregate
GROUP BY SUBSTR(CAST(period AS TEXT), 1, 4), div
ORDER BY year_only DESC;

Reference pattern 3 (Current Year Monthly Trend): Show monthly breakdown of the unit's revenue proportion for the current year
SELECT
    div AS unit_name,
    period,
    SUBSTR(CAST(period AS TEXT), 5, 2) AS month, -- Get month part from period (YYYYMM format)
    SUM(real_mtd) AS unit_revenue,
    (SELECT SUM(real_mtd) FROM cfu_performance_data c2 WHERE c2.period = c1.period AND c2.l2 = 'REVENUE' AND c2.l3 = '-' AND c2.div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')) AS total_monthly_cfu_wib_revenue,
    ROUND(SUM(real_mtd) * 100.0 / (SELECT SUM(real_mtd) FROM cfu_performance_data c3 WHERE c3.period = c1.period AND c3.l2 = 'REVENUE' AND c3.l3 = '-' AND c3.div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS percentage_of_total
FROM cfu_performance_data c1
WHERE SUBSTR(CAST(period AS TEXT), 1, 4) = (SELECT SUBSTR(CAST(MAX(period) AS TEXT), 1, 4) FROM cfu_performance_data) -- Current year
    AND div = 'TELIN' -- Replace with specified unit
    AND l2 = 'REVENUE'
    AND l3 = '-' -- Get L2 aggregate
GROUP BY period, div
ORDER BY period ASC;
'''

cfu_wib_mom_revenue_decline_check_prompt = f'''
Task: Check if there is a revenue decline (Month on Month / MOM) in CFU WIB by performing query to extract total actual and MoM revenue for CFU WIB and check units that contribute to the MoM decline.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!
{valid_values_str}
Rules:
- Query total revenue for CFU WIB (aggregate of all divisions) for MOM analysis
- Check for revenue decline: mom < 0 for REVENUE metric
- Compare current revenue vs previous month revenue to calculate absolute difference
- Show units that show negative MOM growth contributing to the overall decline
- Use latest period (use subquery: SELECT MAX(period) FROM cfu_performance_data) unless specified
- CFU WIB HANDLING (CRITICAL):
    - For total CFU WIB: Include all divisions (DMT, DWS, TELIN, TIF, TSAT) in the aggregation
    - Show individual divisions that are declining to identify contributors to the overall decline
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
- Include actual values, MOM growth percentage, and identify which units are declining
- ORDER BY MOM growth percentage ascending (worst performers first)
- ALWAYS include `period` in the SELECT clause

Reference pattern (Check total CFU WIB MoM revenue and identify declining units):
WITH cfu_wib_total AS (
    SELECT
        'CFU WIB' AS unit_name,
        period,
        SUM(real_mtd) AS total_revenue_current,
        SUM(prev_month) AS total_revenue_previous,
        SUM(real_mtd) - SUM(prev_month) AS absolute_change,
        ROUND(AVG(mom), 2) AS mom_growth_pct,
        CASE
            WHEN AVG(mom) < 0 THEN 'Decline'
            ELSE 'Growth'
        END AS mom_status
    FROM cfu_performance_data
    WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
        AND l2 = 'REVENUE'
        AND l3 = '-'
        AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
    GROUP BY period
)
SELECT
    unit_name,
    period,
    total_revenue_current,
    total_revenue_previous,
    absolute_change,
    mom_growth_pct,
    mom_status
FROM cfu_wib_total;

-- Identify units that contribute to the MoM decline (only if there is an overall decline)
SELECT
    div AS unit_name,
    period,
    SUM(real_mtd) AS revenue_current,
    SUM(prev_month) AS revenue_previous,
    SUM(real_mtd) - SUM(prev_month) AS absolute_change,
    ROUND(AVG(mom), 2) AS mom_growth_pct
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 = 'REVENUE'
    AND l3 = '-'
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
    AND EXISTS (
        SELECT 1
        FROM cfu_wib_total
        WHERE mom_status = 'Decline'
    )  -- Only return if overall CFU WIB has negative MoM growth
    AND AVG(mom) < 0  -- Only return units with negative MoM growth (contribute to decline)
GROUP BY period, div
ORDER BY mom_growth_pct ASC;
'''

mom_revenue_decrease_products_prompt = f'''
Task: Find products that experienced revenue decline (Month on Month / MOM) across all units and calculate absolute revenue decrease (current revenue - previous month revenue), then display top 5-10 products with biggest absolute decrease in order.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!
{valid_values_str}
Rules:
- Filter for products where: l2 = 'REVENUE' AND mom < 0 (declining revenue)
- Calculate absolute revenue decrease: current revenue (real_mtd) - previous month revenue (prev_month)
- Use latest period (use subquery: SELECT MAX(period) FROM cfu_performance_data) unless specified
- Show product details at L3/L4 level (filter l5 = '-' to get L4 items)
- Include ALL units that experienced MOM decline in the analysis
- Calculate absolute difference: real_mtd - prev_month
- ORDER BY absolute decrease amount (ascending - biggest decrease first, as negative values)
- LIMIT to 5-10 results initially (LIMIT 10), allow for more data to be displayed if user requests
- ALWAYS include `period` in the SELECT clause

Reference pattern (Products with biggest MoM revenue decrease):
SELECT
    div AS unit_name,
    l3 AS product_category,
    l4 AS product_detail,
    period,
    SUM(real_mtd) AS revenue_current,
    SUM(prev_month) AS revenue_previous_month,
    SUM(real_mtd) - SUM(prev_month) AS absolute_decrease,
    ROUND(AVG(mom), 2) AS mom_growth_pct
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 = 'REVENUE'
    AND mom < 0
    AND l5 = '-' -- Get L4 items for detailed product analysis
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
GROUP BY period, div, l3, l4
ORDER BY (SUM(real_mtd) - SUM(prev_month)) ASC -- ASC because we want biggest DECREASES (negative values)
LIMIT 10;
'''

mom_revenue_increase_products_prompt = f'''
Task: Find products that experienced revenue increase (Month on Month / MOM) across all units and calculate absolute revenue increase (current revenue - previous month revenue), then display top 5-10 products with biggest absolute increase in order.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!
{valid_values_str}
Rules:
- Filter for products where: l2 = 'REVENUE' AND mom > 0 (increasing revenue)
- Calculate absolute revenue increase: current revenue (real_mtd) - previous month revenue (prev_month)
- Use latest period (use subquery: SELECT MAX(period) FROM cfu_performance_data) unless specified
- Show product details at L3/L4 level (filter l5 = '-' to get L4 items)
- Include ALL units that experienced MOM increase in the analysis
- Calculate absolute difference: real_mtd - prev_month
- ORDER BY absolute increase amount (descending - biggest increase first)
- LIMIT to 5-10 results initially (LIMIT 10), allow for more data to be displayed if user requests
- ALWAYS include `period` in the SELECT clause

Reference pattern (Products with biggest MoM revenue increase):
SELECT
    div AS unit_name,
    l3 AS product_category,
    l4 AS product_detail,
    period,
    SUM(real_mtd) AS revenue_current,
    SUM(prev_month) AS revenue_previous_month,
    SUM(real_mtd) - SUM(prev_month) AS absolute_increase,
    ROUND(AVG(mom), 2) AS mom_growth_pct
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 = 'REVENUE'
    AND mom > 0
    AND l5 = '-' -- Get L4 items for detailed product analysis
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
GROUP BY period, div, l3, l4
ORDER BY (SUM(real_mtd) - SUM(prev_month)) DESC -- DESC to get biggest INCREASES (positive values)
LIMIT 10;
'''

yoy_revenue_decrease_products_prompt = f'''
Task: Find products that experienced revenue decline (Year on Year / YoY) across all units and calculate absolute revenue decrease (current revenue - previous year revenue same period), then display top 5-10 products with biggest absolute decrease in order.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!
{valid_values_str}
Rules:
- Filter for products where: l2 = 'REVENUE' AND yoy < 0 (declining revenue YoY)
- Calculate absolute revenue decrease: current revenue (real_mtd) - previous year revenue (prev_year)
- Use latest period (use subquery: SELECT MAX(period) FROM cfu_performance_data) unless specified
- Show product details at L3/L4 level (filter l5 = '-' to get L4 items)
- Include ALL units that experienced YoY decline in the analysis
- Calculate absolute difference: real_mtd - prev_year (same period last year)
- ORDER BY absolute decrease amount (ascending - biggest decrease first, as negative values)
- LIMIT to 5-10 results initially (LIMIT 10), allow for more data to be displayed if user requests
- ALWAYS include `period` in the SELECT clause

Reference pattern (Products with biggest YoY revenue decrease):
SELECT
    div AS unit_name,
    l3 AS product_category,
    l4 AS product_detail,
    period,
    SUM(real_mtd) AS revenue_current,
    SUM(prev_year) AS revenue_previous_year_same_period,
    SUM(real_mtd) - SUM(prev_year) AS absolute_decrease,
    ROUND(AVG(yoy), 2) AS yoy_growth_pct
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 = 'REVENUE'
    AND yoy < 0
    AND l5 = '-' -- Get L4 items for detailed product analysis
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
GROUP BY period, div, l3, l4
ORDER BY (SUM(real_mtd) - SUM(prev_year)) ASC -- ASC because we want biggest DECREASES (negative values)
LIMIT 10;
'''

yoy_revenue_increase_products_prompt = f'''
Task: Find products that experienced revenue increase (Year on Year / YoY) across all units and calculate absolute revenue increase (current revenue - previous year revenue same period), then display top 5-10 products with biggest absolute increase in order.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!
{valid_values_str}
Rules:
- Filter for products where: l2 = 'REVENUE' AND yoy > 0 (increasing revenue YoY)
- Calculate absolute revenue increase: current revenue (real_mtd) - previous year revenue (prev_year)
- Use latest period (use subquery: SELECT MAX(period) FROM cfu_performance_data) unless specified
- Show product details at L3/L4 level (filter l5 = '-' to get L4 items)
- Include ALL units that experienced YoY increase in the analysis
- Calculate absolute difference: real_mtd - prev_year (same period last year)
- ORDER BY absolute increase amount (descending - biggest increase first)
- LIMIT to 5-10 results initially (LIMIT 10), allow for more data to be displayed if user requests
- ALWAYS include `period` in the SELECT clause

Reference pattern (Products with biggest YoY revenue increase):
SELECT
    div AS unit_name,
    l3 AS product_category,
    l4 AS product_detail,
    period,
    SUM(real_mtd) AS revenue_current,
    SUM(prev_year) AS revenue_previous_year_same_period,
    SUM(real_mtd) - SUM(prev_year) AS absolute_increase,
    ROUND(AVG(yoy), 2) AS yoy_growth_pct
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 = 'REVENUE'
    AND yoy > 0
    AND l5 = '-' -- Get L4 items for detailed product analysis
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
GROUP BY period, div, l3, l4
ORDER BY (SUM(real_mtd) - SUM(prev_year)) DESC -- DESC to get biggest INCREASES (positive values)
LIMIT 10;
'''

unit_revenue_mom_decline_cause_prompt = f'''
Task: Find the cause for MoM revenue decline for a specific unit by querying for revenue products with negative MoM growth and displaying top 5-10 products with the biggest differences (decrease) with their percentages.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!
{valid_values_str}
Rules:
- Filter for specific division (unit) provided by user
- Filter for: l2 = 'REVENUE' AND mom < 0
- Calculate absolute decline: real_mtd - prev_month
- Calculate percentage decline: ((real_mtd - prev_month) / ABS(prev_month)) * 100 if prev_month != 0
- Show product/category details at L3/L4 level (filter l5 = '-' to get L4 items)
- ORDER BY biggest absolute decline first (most negative values)
- LIMIT to 5-10 results initially (if user wants more data, they can request additional results)
- ALWAYS include `period` in the SELECT clause
- Include both the difference amount and percentage in results

Reference pattern (Root cause analysis for specific unit MoM revenue decline):
SELECT
    div AS unit_name,
    l3 AS product_category,
    l4 AS product_detail,
    period,
    SUM(real_mtd) AS revenue_current,
    SUM(prev_month) AS revenue_previous_month,
    SUM(real_mtd) - SUM(prev_month) AS absolute_difference,
    ROUND(((SUM(real_mtd) - SUM(prev_month)) / CASE WHEN ABS(SUM(prev_month)) = 0 THEN 1 ELSE ABS(SUM(prev_month)) END) * 100, 2) AS percentage_change,
    ROUND(AVG(mom), 2) AS mom_growth_pct
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN' -- Replace with specific unit provided by user
    AND l2 = 'REVENUE'
    AND mom < 0
    AND l5 = '-' -- Get L4 items for detailed product analysis
GROUP BY period, div, l3, l4
ORDER BY (SUM(real_mtd) - SUM(prev_month)) ASC -- ASC for biggest decreases (most negative values)
LIMIT 10;
'''

top_revenue_contributing_products_prompt = f'''
Task: Find products that contribute the most to revenue for CFU WIB by analyzing actual values and their percentages against the total, displaying top 10 products with highest revenue contribution.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!
{valid_values_str}
Rules:
- Focus on identifying top revenue contributing products across all divisions
- Calculate revenue contribution: SUM of real_mtd for each product
- Calculate percentage of total: (product revenue / total CFU WIB revenue) * 100
- Use latest period (use subquery: SELECT MAX(period) FROM cfu_performance_data) unless specified
- Show product details at L3/L4 level (filter l5 = '-' to get L4 items) - this will show actual products/services, not the units
- Include ALL divisions in the analysis (DMT, DWS, TELIN, TIF, TSAT)
- ORDER BY revenue amount descending (highest contributors first)
- LIMIT to 10 results (top 10 contributors)
- ALWAYS include `period` in the SELECT clause

Reference pattern (Top revenue contributing products for CFU WIB):
SELECT
    div AS unit_name,
    l3 AS product_category,
    l4 AS product_detail,
    period,
    SUM(real_mtd) AS product_revenue,
    ROUND(SUM(real_mtd) * 100.0 / (SELECT SUM(real_mtd) FROM cfu_performance_data WHERE period = (SELECT MAX(period) FROM cfu_performance_data) AND l2 = 'REVENUE' AND l3 = '-' AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS percentage_of_total_cfu_wib
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 = 'REVENUE'
    AND l3 != '-' -- Exclude L2 aggregates to get actual products
    AND l4 != '-' -- Exclude L3 aggregates to get actual products
    AND l5 = '-' -- Get L4 items for detailed product analysis
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
GROUP BY period, div, l3, l4
ORDER BY SUM(real_mtd) DESC  -- Order by total revenue descending (highest contributors first)
LIMIT 10;
'''

revenue_underachievement_products_prompt = f'''
Task: Find products that contribute most to revenue underachievement for CFU WIB by calculating the shortfall (target - actual revenue) and showing the achievement percentage, displaying top 10 products with largest shortfalls.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!
{valid_values_str}
Rules:
- Focus on identifying products with largest revenue shortfalls (difference between target and actual)
- Calculate revenue shortfall: SUM(target_mtd) - SUM(real_mtd) for each product
- Calculate achievement percentage: AVG(ach_mtd) for each product
- Use latest period (use subquery: SELECT MAX(period) FROM cfu_performance_data) unless specified
- Show product details at L3/L4 level (filter l5 = '-' to get L4 items)
- Include ALL divisions in the analysis (DMT, DWS, TELIN, TIF, TSAT)
- Filter for underachieving products only: ach_mtd < 100
- ORDER BY shortfall amount descending (largest shortfalls first)
- LIMIT to 10 results (top 10 underachievers)
- ALWAYS include `period` in the SELECT clause

Reference pattern (Products with largest revenue shortfalls for CFU WIB):
SELECT
    div AS unit_name,
    l3 AS product_category,
    l4 AS product_detail,
    period,
    SUM(real_mtd) AS actual_revenue,
    SUM(target_mtd) AS target_revenue,
    SUM(target_mtd) - SUM(real_mtd) AS revenue_shortfall, -- Difference between target and actual (shortfall)
    ROUND(AVG(ach_mtd), 2) AS achievement_pct
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 = 'REVENUE'
    AND l3 != '-' -- Exclude L2 aggregates to get actual products
    AND l4 != '-' -- Exclude L3 aggregates to get actual products
    AND l5 = '-' -- Get L4 items for detailed product analysis
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
    AND ach_mtd < 100 -- Only underachieving products
GROUP BY period, div, l3, l4
ORDER BY (SUM(target_mtd) - SUM(real_mtd)) DESC -- DESC for largest shortfalls
LIMIT 10;
'''

revenue_growth_comparison_prompt = f'''
Task: Show Month-over-Month (MoM) and Year-over-Year (YoY) revenue growth comparison for CFU WIB and its individual units, including identifying products that contribute to growth or decline.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!
{valid_values_str}
Rules:
- Show both MoM and YoY revenue growth for total CFU WIB and individual units
- Calculate MoM growth: (current - previous_month) / previous_month * 100
- Calculate YoY growth: (current - previous_year) / previous_year * 100
- For CFU WIB: Aggregate all divisions (DMT, DWS, TELIN, TIF, TSAT)
- For individual units: Show specific division data
- Include actual revenue values for context
- If there is a decline (negative growth), identify products that contributed to the decline
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
- ORDER BY unit name for consistent presentation
- ALWAYS include `period` in the SELECT clause

Reference pattern 1 (MoM and YoY growth for CFU WIB and units):
WITH cfu_wib_growth AS (
    SELECT
        'CFU WIB' AS unit_name,
        period,
        SUM(real_mtd) AS actual_revenue,
        SUM(prev_month) AS prev_month_revenue,
        SUM(real_mtd) - SUM(prev_month) AS mom_absolute_change,
        ROUND(AVG(mom), 2) AS mom_growth_pct,
        SUM(prev_year) AS prev_year_revenue,
        SUM(real_mtd) - SUM(prev_year) AS yoy_absolute_change,
        ROUND(AVG(yoy), 2) AS yoy_growth_pct
    FROM cfu_performance_data
    WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
        AND l2 = 'REVENUE'
        AND l3 = '-'
        AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
    GROUP BY period
),
unit_growth AS (
    SELECT
        div AS unit_name,
        period,
        SUM(real_mtd) AS actual_revenue,
        SUM(prev_month) AS prev_month_revenue,
        SUM(real_mtd) - SUM(prev_month) AS mom_absolute_change,
        ROUND(AVG(mom), 2) AS mom_growth_pct,
        SUM(prev_year) AS prev_year_revenue,
        SUM(real_mtd) - SUM(prev_year) AS yoy_absolute_change,
        ROUND(AVG(yoy), 2) AS yoy_growth_pct
    FROM cfu_performance_data
    WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
        AND l2 = 'REVENUE'
        AND l3 = '-'
        AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
    GROUP BY period, div
)
SELECT * FROM cfu_wib_growth
UNION ALL
SELECT * FROM unit_growth
ORDER BY unit_name;

Reference pattern 2 (Products contributing to decline if growth is negative):
SELECT
    div AS unit_name,
    l3 AS product_category,
    l4 AS product_detail,
    period,
    SUM(real_mtd) AS revenue_current,
    SUM(prev_year) AS revenue_previous_year,
    SUM(real_mtd) - SUM(prev_year) AS yoy_absolute_change,
    ROUND(AVG(yoy), 2) AS yoy_growth_pct
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 = 'REVENUE'
    AND l3 = '-' -- Get L2 aggregates
    AND l5 = '-' -- Get L4 items for detailed product analysis
    AND yoy < 0  -- Only products with negative YoY growth
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
GROUP BY period, div, l3, l4
ORDER BY (SUM(real_mtd) - SUM(prev_year)) ASC  -- ASC to get biggest decreases (most negative values)
LIMIT 10;
'''

revenue_surge_products_year_prompt = f'''
Task: Find products that experienced revenue surge (Month on Month / MOM) in a specific year compared to their previous months' average, identifying products with MOM > 10% above the 3-month average.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!
{valid_values_str}
Rules:
- Identify revenue surges by comparing current month MOM to 3-month historical average
- Calculate 3-month moving average of MOM for each product to establish baseline
- Identify products with current MOM > (3-month average + 10% threshold)
- Use specified year for analysis (extract year from period field: SUBSTR(period, 1, 4) = 'YYYY')
- Show product details at L3/L4 level (filter l5 = '-' to get L4 items)
- Include ALL units in the analysis (DMT, DWS, TELIN, TIF, TSAT)
- Calculate comparison between current MOM and historical average
- ORDER BY magnitude of surge (current MOM - average MOM) descending
- LIMIT to 10 results initially, with possibility for more if user requests
- ALWAYS include `period` in the SELECT clause

Reference pattern (Products with revenue surge in specific year compared to 3-month average):
-- Example for year 2024, adjust year as needed based on user input
WITH monthly_avg_mom AS (
    SELECT
        div,
        l3,
        l4,
        period,
        AVG(mom) OVER (
            PARTITION BY div, l3, l4
            ORDER BY period
            ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
        ) AS avg_prev_3_months_mom
    FROM cfu_performance_data
    WHERE SUBSTR(CAST(period AS TEXT), 1, 4) = '2024'  -- Replace with requested year
        AND l2 = 'REVENUE'
        AND l3 = '-' -- Get L2 aggregates
        AND l5 = '-' -- Get L4 items for detailed product analysis
        AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
),
surge_products AS (
    SELECT
        m.avg_prev_3_months_mom,
        p.div AS unit_name,
        p.l3 AS product_category,
        p.l4 AS product_detail,
        p.period,
        p.mom AS current_mom,
        SUM(p.real_mtd) AS revenue_current,
        SUM(p.prev_month) AS revenue_previous
    FROM cfu_performance_data p
    JOIN monthly_avg_mom m ON p.div = m.div AND p.l3 = m.l3 AND p.l4 = m.l4 AND p.period = m.period
    WHERE p.period = (SELECT MAX(period) FROM cfu_performance_data WHERE SUBSTR(CAST(period AS TEXT), 1, 4) = '2024') -- Most recent period in requested year
        AND p.l2 = 'REVENUE'
        AND p.mom > (m.avg_prev_3_months_mom + 10)  -- Current MoM is more than 10% higher than average of previous 3 months
        AND p.l3 = '-' -- Get L2 aggregates
        AND p.l5 = '-' -- Get L4 items for detailed product analysis
        AND p.div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
)
SELECT
    unit_name,
    product_category,
    product_detail,
    period,
    revenue_current,
    revenue_previous,
    current_mom AS mom_current,
    avg_prev_3_months_mom AS mom_3month_avg
FROM surge_products
ORDER BY (current_mom - avg_prev_3_months_mom) DESC; -- DESC to get biggest surges
'''
ebitda_proportion_analysis_prompt = f'''
Task: Calculate the proportion of EBITDA for a specific unit against total CFU WIB EBITDA.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Calculate percentage of specified unit's EBITDA against total CFU WIB EBITDA for the latest period.
- Calculate percentages by dividing unit EBITDA by total CFU WIB EBITDA and multiplying by 100.
- Use latest period from (SELECT MAX(period) FROM cfu_performance_data) unless specified.
- ALWAYS include both actual values and percentages in the results.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter l3 = '-'.

Reference pattern (Single Period Proportion):
SELECT
    div AS unit_name,
    period,
    SUM(real_mtd) AS unit_ebitda,
    (SELECT SUM(real_mtd) FROM cfu_performance_data WHERE period = (SELECT MAX(period) FROM cfu_performance_data) AND l2 = 'EBITDA' AND l3 = '-' AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')) AS total_cfu_wib_ebitda,
    ROUND(SUM(real_mtd) * 100.0 / (SELECT SUM(real_mtd) FROM cfu_performance_data WHERE period = (SELECT MAX(period) FROM cfu_performance_data) AND l2 = 'EBITDA' AND l3 = '-' AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS percentage_of_total
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN' -- Replace with specified unit
    AND l2 = 'EBITDA'
    AND l3 = '-' -- Get L2 aggregate
GROUP BY period, div;
'''

ebitda_proportion_trend_prompt = f'''
Task: Analyze the trend of EBITDA proportion for a specific unit against total CFU WIB EBITDA over time.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Handle the following specific queries:
  - "Bagaimana tren porsi EBITDA [unit] terhadap CFU WIB selama 3 tahun terakhir?" -> Show annual trend of the unit's EBITDA percentage against total CFU WIB EBITDA for the last 3 years.
  - "Bagaimana tren porsi EBITDA [unit] terhadap CFU WIB dalam tahun ini?" -> Show monthly trend of the unit's EBITDA percentage against total CFU WIB EBITDA for the current year.
- Calculate percentages by dividing unit EBITDA by total CFU WIB EBITDA and multiplying by 100.
- For 3-year annual trend: Convert period to year and aggregate by year.
- For current year monthly trend: Filter for current year and show monthly breakdowns.
- ALWAYS include both actual values and percentages in the results.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter l3 = '-'.

Reference pattern 1 (3-Year Annual Trend):
SELECT
    div AS unit_name,
    CAST(period AS TEXT) AS year, -- Extract year from period
    SUBSTR(CAST(period AS TEXT), 1, 4) AS year_only,
    SUM(real_mtd) AS unit_ebitda,
    (SELECT SUM(real_mtd) FROM cfu_performance_data c2 WHERE SUBSTR(CAST(c2.period AS TEXT), 1, 4) = SUBSTR(CAST(c1.period AS TEXT), 1, 4) AND c2.l2 = 'EBITDA' AND c2.l3 = '-' AND c2.div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')) AS total_yearly_cfu_wib_ebitda,
    ROUND(SUM(real_mtd) * 100.0 / (SELECT SUM(real_mtd) FROM cfu_performance_data c3 WHERE SUBSTR(CAST(c3.period AS TEXT), 1, 4) = SUBSTR(CAST(c1.period AS TEXT), 1, 4) AND c3.l2 = 'EBITDA' AND c3.l3 = '-' AND c3.div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS percentage_of_total
FROM cfu_performance_data c1
WHERE SUBSTR(CAST(period AS TEXT), 1, 4) IN (
    SELECT DISTINCT SUBSTR(CAST(period AS TEXT), 1, 4)
    FROM cfu_performance_data
    ORDER BY period DESC
    LIMIT 3
)
    AND div = 'TELIN' -- Replace with specified unit
    AND l2 = 'EBITDA'
    AND l3 = '-' -- Get L2 aggregate
GROUP BY SUBSTR(CAST(period AS TEXT), 1, 4), div
ORDER BY year_only DESC;

Reference pattern 2 (Current Year Monthly Trend):
SELECT
    div AS unit_name,
    period,
    SUBSTR(CAST(period AS TEXT), 5, 2) AS month,
    SUM(real_mtd) AS unit_ebitda,
    (SELECT SUM(real_mtd) FROM cfu_performance_data c2 WHERE c2.period = c1.period AND c2.l2 = 'EBITDA' AND c2.l3 = '-' AND c2.div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')) AS total_monthly_cfu_wib_ebitda,
    ROUND(SUM(real_mtd) * 100.0 / (SELECT SUM(real_mtd) FROM cfu_performance_data c3 WHERE c3.period = c1.period AND c3.l2 = 'EBITDA' AND c3.l3 = '-' AND c3.div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS percentage_of_total
FROM cfu_performance_data c1
WHERE SUBSTR(CAST(period AS TEXT), 1, 4) = (SELECT SUBSTR(CAST(MAX(period) AS TEXT), 1, 4) FROM cfu_performance_data) -- Current year
    AND div = 'TELIN' -- Replace with specified unit
    AND l2 = 'EBITDA'
    AND l3 = '-' -- Get L2 aggregate
GROUP BY period, div
ORDER BY period ASC;
'''

ebitda_mom_decline_check_prompt = f'''
Task: Check if there is a decline in EBITDA (Month on Month / MOM) for CFU WIB and identify contributing units.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Query total actual and MoM EBITDA for CFU WIB.
- Check units that contribute to the MoM decline (where MoM < 0).
- Use latest period from (SELECT MAX(period) FROM cfu_performance_data) unless specified.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter l3 = '-'.

Reference pattern:
SELECT
    div,
    period,
    l2,
    SUM(real_mtd) AS real_mtd,
    ROUND(AVG(mom), 2) AS mom
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 = 'EBITDA'
    AND l3 = '-'
    AND (div = 'CFU WIB' OR div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')) -- Check CFU WIB and all units
GROUP BY div, period, l2
ORDER BY mom ASC; -- Order by lowest MoM (biggest decline) first
'''

ebitda_mom_change_cause_prompt = f'''
Task: Analyze the cause of EBITDA Month on Month (MoM) change (Decline or Increase) by checking Revenue and COE.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Handle the following specific queries:
  - "Apa yang menyebabkan penurunan EBITDA secara Month on Month / MOM?" -> Check MoM Revenue and COE for each unit. If Revenue declined, show Revenue contributors. If COE increased, show COE contributors.
  - "Apa yang menyebabkan kenaikan EBITDA secara Month on Month / MOM?" -> Check MoM Revenue and COE for each unit. If Revenue increased, show Revenue contributors. If COE decreased, show COE contributors.
- Query MoM Revenue and COE for each unit.
- Calculate absolute difference for Revenue and COE changes.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter l3 = '-'.

Reference pattern:
SELECT
    div,
    period,
    l2,
    SUM(real_mtd) AS real_mtd,
    ROUND(AVG(mom), 2) AS mom,
    (SUM(real_mtd) - (SUM(real_mtd) / (1 + AVG(mom)/100.0))) AS absolute_change -- Estimate absolute change from MoM
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 IN ('REVENUE', 'COE')
    AND l3 = '-'
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
GROUP BY div, period, l2
ORDER BY div, l2;
'''

ebitda_proportion_analysis_prompt = f'''
Task: Generate a SQLite query to calculate the proportion (percentage) of a specific unit's EBITDA against the total CFU WIB EBITDA for the latest period.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd` or `real_ytd` as the actual EBITDA value depending on user request (default to MTD if not specified).
- METRIC FILTERING (CRITICAL):
    - MUST filter `l2 = 'EBITDA'` ONLY.
    - DO NOT include other metrics.
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a period (e.g., "Juli 2025", "July 2025", "202507"), YOU MUST EXTRACT IT as integer YYYYMM (e.g., 202507) and use `period = 202507`.
    - DO NOT use `MAX(period)` if a specific period is requested.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
- CALCULATION LOGIC:
  - Calculate the unit's EBITDA as a percentage of total CFU WIB EBITDA.
  - Formula: (Unit EBITDA / Total CFU WIB EBITDA) * 100.
  - Use SUM aggregation for both unit and total.
- Output should show: unit name, unit EBITDA, total CFU WIB EBITDA, and percentage.

Reference pattern (EBITDA proportion for specific unit):
SELECT
    div,
    period,
    l2,
    SUM(real_mtd) AS unit_ebitda,
    (SELECT SUM(real_mtd) 
     FROM cfu_performance_data 
     WHERE period = (SELECT MAX(period) FROM cfu_performance_data) 
       AND l2 = 'EBITDA' 
       AND l3 = '-') AS total_cfu_wib_ebitda,
    ROUND((SUM(real_mtd) * 100.0) / 
          (SELECT SUM(real_mtd) 
           FROM cfu_performance_data 
           WHERE period = (SELECT MAX(period) FROM cfu_performance_data) 
             AND l2 = 'EBITDA' 
             AND l3 = '-'), 2) AS proportion_percentage
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN' -- Replace with specific unit from user request
    AND l2 = 'EBITDA'
    AND l3 = '-'
GROUP BY div, period, l2;
'''

ebitda_proportion_trend_yearly_prompt = f'''
Task: Generate a SQLite query to show the trend of a specific unit's EBITDA proportion (percentage) against total CFU WIB EBITDA over the last 3 years (yearly basis).

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_ytd` for yearly analysis.
- METRIC FILTERING (CRITICAL):
    - MUST filter `l2 = 'EBITDA'` ONLY.
    - DO NOT include other metrics.
- PERIOD HANDLING (CRITICAL):
    - Query for the last 3 years of data (yearly basis).
    - For each year, use the LATEST available period (highest period) in that year.
    - Example: If data has 202301-202312, 202401-202412, 202501-202510, use 202312, 202412, and 202510.
    - This ensures we get complete data even if current year hasn't finished yet.
    - Extract year from period and get MAX(period) for each year.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
- CALCULATION LOGIC:
  - For each year, calculate: (Unit EBITDA YTD / Total CFU WIB EBITDA YTD) * 100.
  - Show trend over 3 years.
- Output should show: year, period used, unit EBITDA YTD, total CFU WIB EBITDA YTD, and percentage for each year.
- Order chronologically by year (oldest first).

Reference pattern (3-year EBITDA proportion trend for specific unit):
WITH latest_periods_per_year AS (
    SELECT 
        CAST(period / 100 AS INTEGER) AS year,
        MAX(period) AS latest_period
    FROM cfu_performance_data
    WHERE CAST(period / 100 AS INTEGER) >= (SELECT CAST(MAX(period) / 100 AS INTEGER) - 2 FROM cfu_performance_data)
    GROUP BY CAST(period / 100 AS INTEGER)
)
SELECT
    lp.year,
    lp.latest_period AS period,
    t1.div,
    t1.l2,
    SUM(t1.real_ytd) AS unit_ebitda_ytd,
    (SELECT SUM(real_ytd) 
     FROM cfu_performance_data 
     WHERE period = lp.latest_period
       AND l2 = 'EBITDA' 
       AND l3 = '-'
       AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')) AS total_cfu_wib_ebitda_ytd,
    ROUND((SUM(t1.real_ytd) * 100.0) / 
          (SELECT SUM(real_ytd) 
           FROM cfu_performance_data 
           WHERE period = lp.latest_period
             AND l2 = 'EBITDA' 
             AND l3 = '-'
             AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS proportion_percentage
FROM cfu_performance_data t1
JOIN latest_periods_per_year lp ON t1.period = lp.latest_period
WHERE t1.div = 'TELIN' -- Replace with specific unit from user request
    AND t1.l2 = 'EBITDA'
    AND t1.l3 = '-'
GROUP BY lp.year, lp.latest_period, t1.div, t1.l2
ORDER BY lp.year ASC;
'''

ebitda_proportion_trend_monthly_prompt = f'''
Task: Generate a SQLite query to show the trend of a specific unit's EBITDA proportion (percentage) against total CFU WIB EBITDA within the current year (monthly basis, from January to latest available period).

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd` for monthly analysis.
- METRIC FILTERING (CRITICAL):
    - MUST filter `l2 = 'EBITDA'` ONLY.
    - DO NOT include other metrics.
- PERIOD HANDLING (CRITICAL):
    - Query for the current year from January to the latest available period.
    - Determine current year from MAX(period) and filter all periods in that year.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
- CALCULATION LOGIC:
  - For each month, calculate: (Unit EBITDA MTD / Total CFU WIB EBITDA MTD) * 100.
  - Show monthly progression within the current year.
- Output should show: period, unit EBITDA MTD, total CFU WIB EBITDA MTD, and percentage for each month.
- Order chronologically by period (oldest first).

Reference pattern (Current year monthly EBITDA proportion trend for specific unit):
SELECT
    t1.period,
    t1.div,
    t1.l2,
    SUM(t1.real_mtd) AS unit_ebitda_mtd,
    (SELECT SUM(real_mtd) 
     FROM cfu_performance_data 
     WHERE period = t1.period
       AND l2 = 'EBITDA' 
       AND l3 = '-') AS total_cfu_wib_ebitda_mtd,
    ROUND((SUM(t1.real_mtd) * 100.0) / 
          (SELECT SUM(real_mtd) 
           FROM cfu_performance_data 
           WHERE period = t1.period
             AND l2 = 'EBITDA' 
             AND l3 = '-'), 2) AS proportion_percentage
FROM cfu_performance_data t1
WHERE CAST(t1.period / 100 AS INTEGER) = (SELECT CAST(MAX(period) / 100 AS INTEGER) FROM cfu_performance_data)
    AND t1.div = 'TELIN' -- Replace with specific unit from user request
    AND t1.l2 = 'EBITDA'
    AND t1.l3 = '-'
GROUP BY t1.period, t1.div, t1.l2
ORDER BY t1.period ASC;
'''

cfu_wib_ebitda_mom_decline_check_prompt = f'''
Task: Generate a SQLite query to check if there is a Month-over-Month (MoM) decline in total CFU WIB EBITDA for the latest period, and identify which units contributed to this decline.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd` and `mom` columns.
- METRIC FILTERING (CRITICAL):
    - MUST filter `l2 = 'EBITDA'` ONLY.
    - DO NOT include other metrics.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
- CALCULATION LOGIC:
  - First, check total CFU WIB EBITDA MoM growth.
  - If MoM is negative, it indicates a decline.
  - Then show each unit's EBITDA, MoM percentage, and absolute change.
  - Calculate absolute change: current month EBITDA - previous month EBITDA.
- CFU WIB HANDLING:
  - Query all 5 units (DMT, DWS, TELIN, TIF, TSAT) individually.
  - Also show total CFU WIB aggregate.
- Output should show: unit name, period, EBITDA MTD, MoM percentage, and absolute change.
- Highlight units with negative MoM contributing to overall decline.

Reference pattern (CFU WIB EBITDA MoM decline check):
SELECT
    div,
    period,
    l2,
    SUM(real_mtd) AS ebitda_mtd,
    ROUND(AVG(mom), 2) AS mom_percentage,
    (SUM(real_mtd) - (SUM(real_mtd) / (1 + AVG(mom)/100.0))) AS absolute_change
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 = 'EBITDA'
    AND l3 = '-'
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
GROUP BY div, period, l2
UNION ALL
SELECT
    'CFU WIB' AS div,
    period,
    l2,
    SUM(real_mtd) AS ebitda_mtd,
    ROUND(AVG(mom), 2) AS mom_percentage,
    (SUM(real_mtd) - (SUM(real_mtd) / (1 + AVG(mom)/100.0))) AS absolute_change
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 = 'EBITDA'
    AND l3 = '-'
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT') <- CFU WIB units
GROUP BY period, l2
ORDER BY div;
'''

ebitda_mom_decline_cause_prompt = f'''
Task: Generate a SQLite query to identify the cause of EBITDA Month-over-Month (MoM) decline by analyzing Revenue and COE changes for each unit.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd` and `mom` columns.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE', 'EBITDA')`.
    - Analyze Revenue and COE to determine EBITDA decline cause.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 level: Filter `l4 = '-'` to get breakdown by L3 categories.
- ANALYSIS LOGIC:
  - For each unit with EBITDA MoM decline:
    - If Revenue MoM is negative (declined), identify top L3 Revenue contributors to the decline.
    - If COE MoM is positive (increased), identify top L3 COE contributors to the increase.
  - Calculate absolute change for Revenue and COE.
  - EBITDA = Revenue - COE, so EBITDA decline can be caused by Revenue decline or COE increase.
- Output should show:
  - Unit name, metric (Revenue/COE), L3 category, MTD value, MoM percentage, absolute change.
  - Focus on negative contributors (Revenue decline or COE increase).
- Order by absolute change magnitude (largest impact first).

Reference pattern (EBITDA MoM decline cause analysis):
SELECT
    div,
    period,
    l2,
    l3,
    SUM(real_mtd) AS mtd_value,
    SUM(prev_month) AS prev_month_value,
    ROUND(AVG(mom), 2) AS mom_percentage,
    (SUM(real_mtd) - SUM(prev_month)) AS absolute_change
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 IN ('REVENUE', 'COE')
    AND l4 = '-' -- Get L3 level breakdown
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT') <- CFU WIB units
GROUP BY div, period, l2, l3
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_month)) < 0) -- Revenue drop
    OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_month)) > 0) -- Cost rise
ORDER BY div, (CASE WHEN l2 = 'COE' THEN -1 ELSE 1 END * (SUM(real_mtd) - SUM(prev_month))) ASC;
'''

ebitda_mom_increase_cause_prompt = f'''
Task: Generate a SQLite query to identify the cause of EBITDA Month-over-Month (MoM) increase by analyzing Revenue and COE changes for each unit.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd` and `mom` columns.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE', 'EBITDA')`.
    - Analyze Revenue and COE to determine EBITDA increase cause.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 level: Filter `l4 = '-'` to get breakdown by L3 categories.
- ANALYSIS LOGIC:
  - For each unit with EBITDA MoM increase:
    - If Revenue MoM is positive (increased), identify top L3 Revenue contributors to the increase.
    - If COE MoM is negative (decreased), identify top L3 COE contributors to the decrease.
  - Calculate absolute change for Revenue and COE.
  - EBITDA = Revenue - COE, so EBITDA increase can be caused by Revenue increase or COE decrease.
- Output should show:
  - Unit name, metric (Revenue/COE), L3 category, MTD value, MoM percentage, absolute change.
  - Focus on positive contributors (Revenue increase or COE decrease).
- Order by absolute change magnitude (largest positive impact first).

Reference pattern (EBITDA MoM increase cause analysis):
SELECT
    div,
    period,
    l2,
    l3,
    SUM(real_mtd) AS mtd_value,
    SUM(prev_month) AS prev_month_value,
    ROUND(AVG(mom), 2) AS mom_percentage,
    (SUM(real_mtd) - SUM(prev_month)) AS absolute_change
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 IN ('REVENUE', 'COE')
    AND l4 = '-' -- Get L3 level breakdown
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT') <- CFU WIB units
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_month)) > 0) -- Revenue rise
    OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_month)) < 0) -- Cost drop
ORDER BY div, (CASE WHEN l2 = 'COE' THEN -1 ELSE 1 END * (SUM(real_mtd) - SUM(prev_month))) DESC;
'''

ebitda_yoy_decline_cause_prompt = f'''
Task: Generate a SQLite query to identify the cause of EBITDA Year-over-Year (YoY) decline by analyzing Revenue and COE changes for each unit.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd`, `prev_year`, and `yoy` columns.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE', 'EBITDA')`.
    - Analyze Revenue and COE to determine EBITDA YoY decline cause.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 level: Filter `l4 = '-'` to get breakdown by L3 categories.
- ANALYSIS LOGIC:
  - For each unit with EBITDA YoY decline:
    - If Revenue YoY is negative (declined), identify top L3 Revenue contributors to the decline.
    - If COE YoY is positive (increased), identify top L3 COE contributors to the increase.
  - Calculate absolute change for Revenue and COE: current value - previous year value.
  - EBITDA = Revenue - COE, so EBITDA decline can be caused by Revenue decline or COE increase.
- Output should show:
  - Unit name, metric (Revenue/COE), L3 category, MTD value, previous year value, YoY percentage, absolute change.
  - Focus on negative contributors (Revenue decline or COE increase).
- Order by absolute change magnitude (largest impact first).

Reference pattern (EBITDA YoY decline cause analysis):
SELECT
    div,
    period,
    l2,
    l3,
    SUM(real_mtd) AS mtd_value,
    SUM(prev_year) AS prev_year_value,
    ROUND(AVG(yoy), 2) AS yoy_percentage,
    (SUM(real_mtd) - SUM(prev_year)) AS absolute_change
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 IN ('REVENUE', 'COE')
    AND l4 = '-' -- Get L3 level breakdown
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT') <- CFU WIB units
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_year)) < 0) -- Revenue drop
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_year)) < 0) -- Revenue drop
    OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_year)) > 0) -- Cost rise
ORDER BY div, (CASE WHEN l2 = 'COE' THEN -1 ELSE 1 END * (SUM(real_mtd) - SUM(prev_year))) ASC;
'''

ebitda_yoy_increase_cause_prompt = f'''
Task: Generate a SQLite query to identify the cause of EBITDA Year-over-Year (YoY) increase by analyzing Revenue and COE changes for each unit.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd`, `prev_year`, and `yoy` columns.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE', 'EBITDA')`.
    - Analyze Revenue and COE to determine EBITDA YoY increase cause.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 level: Filter `l4 = '-'` to get breakdown by L3 categories.
- ANALYSIS LOGIC:
  - For each unit with EBITDA YoY increase:
    - If Revenue YoY is positive (increased), identify top L3 Revenue contributors to the increase.
    - If COE YoY is negative (decreased), identify top L3 COE contributors to the decrease.
  - Calculate absolute change for Revenue and COE: current value - previous year value.
  - EBITDA = Revenue - COE, so EBITDA increase can be caused by Revenue increase or COE decrease.
- Output should show:
  - Unit name, metric (Revenue/COE), L3 category, MTD value, previous year value, YoY percentage, absolute change.
  - Focus on positive contributors (Revenue increase or COE decrease).
- Order by absolute change magnitude (largest positive impact first).

Reference pattern (EBITDA YoY increase cause analysis):
SELECT
    div,
    period,
    l2,
    l3,
    SUM(real_mtd) AS mtd_value,
    SUM(prev_year) AS prev_year_value,
    ROUND(AVG(yoy), 2) AS yoy_percentage,
    (SUM(real_mtd) - SUM(prev_year)) AS absolute_change
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 IN ('REVENUE', 'COE')
    AND l4 = '-' -- Get L3 level breakdown
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT') <- CFU WIB units
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_year)) > 0) -- Revenue rise
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_year)) > 0) -- Revenue rise
    OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_year)) < 0) -- Cost drop
ORDER BY div, (CASE WHEN l2 = 'COE' THEN -1 ELSE 1 END * (SUM(real_mtd) - SUM(prev_year))) DESC;
'''


unit_ebitda_mom_decline_cause_prompt = f'''
Task: Generate a SQLite query to identify the cause of EBITDA Month-over-Month (MoM) decline for a specific unit by analyzing Revenue and COE changes.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd`, `prev_month`, and `mom` columns.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE', 'EBITDA')`.
    - Analyze Revenue and COE to determine EBITDA MoM decline cause for the specified unit.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 level: Filter `l4 = '-'` to get breakdown by L3 categories.
- ANALYSIS LOGIC:
  - For the specified unit with EBITDA MoM decline:
    - If Revenue MoM is negative (declined), identify top L3 Revenue contributors to the decline.
    - If COE MoM is positive (increased), identify top L3 COE contributors to the increase.
  - Calculate absolute change for Revenue and COE.
  - EBITDA = Revenue - COE, so EBITDA decline can be caused by Revenue decline or COE increase.
- Output should show:
  - Unit name, metric (Revenue/COE), L3 category, MTD value, previous month value, MoM percentage, absolute change.
  - Focus on negative contributors (Revenue decline or COE increase).
- Order by absolute change magnitude (largest impact first).

Reference pattern (Unit-specific EBITDA MoM decline cause analysis):
SELECT
    div,
    period,
    l2,
    l3,
    SUM(real_mtd) AS mtd_value,
    SUM(prev_month) AS prev_month_value,
    ROUND(AVG(mom), 2) AS mom_percentage,
    (SUM(real_mtd) - SUM(prev_month)) AS absolute_change
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN' -- Replace with specific unit from user request
    AND l2 IN ('REVENUE', 'COE')
    AND l4 = '-' -- Get L3 level breakdown
GROUP BY div, period, l2, l3
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_month)) < 0) -- Revenue drop
    OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_month)) > 0) -- Cost rise
ORDER BY (CASE WHEN l2 = 'COE' THEN -1 ELSE 1 END * (SUM(real_mtd) - SUM(prev_month))) ASC;
'''

unit_ebitda_mom_increase_cause_prompt = f'''
Task: Generate a SQLite query to identify the cause of EBITDA Month-over-Month (MoM) increase for a specific unit by analyzing Revenue and COE changes.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd`, `prev_month`, and `mom` columns.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE', 'EBITDA')`.
    - Analyze Revenue and COE to determine EBITDA MoM increase cause for the specified unit.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 level: Filter `l4 = '-'` to get breakdown by L3 categories.
- ANALYSIS LOGIC:
  - For the specified unit with EBITDA MoM increase:
    - If Revenue MoM is positive (increased), identify top L3 Revenue contributors to the increase.
    - If COE MoM is negative (decreased), identify top L3 COE contributors to the decrease.
  - Calculate absolute change for Revenue and COE.
  - EBITDA = Revenue - COE, so EBITDA increase can be caused by Revenue increase or COE decrease.
- Output should show:
  - Unit name, metric (Revenue/COE), L3 category, MTD value, previous month value, MoM percentage, absolute change.
  - Focus on positive contributors (Revenue increase or COE decrease).
- Order by absolute change magnitude (largest positive impact first).

Reference pattern (Unit-specific EBITDA MoM increase cause analysis):
SELECT
    div,
    period,
    l2,
    l3,
    SUM(real_mtd) AS mtd_value,
    SUM(prev_month) AS prev_month_value,
    ROUND(AVG(mom), 2) AS mom_percentage,
    (SUM(real_mtd) - SUM(prev_month)) AS absolute_change
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN' -- Replace with specific unit from user request
    AND l2 IN ('REVENUE', 'COE')
    AND l4 = '-' -- Get L3 level breakdown
GROUP BY div, period, l2, l3
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_month)) > 0) -- Revenue rise
    OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_month)) < 0) -- Cost drop
ORDER BY (CASE WHEN l2 = 'COE' THEN -1 ELSE 1 END * (SUM(real_mtd) - SUM(prev_month))) DESC;
'''

unit_ebitda_margin_decline_cause_prompt = f'''
Task: Generate a comprehensive SQLite query to analyze EBITDA margin decline for a specific unit in a specific period, showing both overall margin comparison and detailed L3 breakdown of causes in a single result.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd`, `prev_month`, and `mom` columns.
- METRIC FILTERING (CRITICAL):
    - Query `l2 IN ('REVENUE', 'COE', 'EBITDA')`.
    - Calculate EBITDA margin: (EBITDA / Revenue) * 100.
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a period (e.g., "Juli 2025", "July 2025", "202507"), YOU MUST EXTRACT IT as integer YYYYMM (e.g., 202507) and use `period = 202507`.
    - DO NOT use `MAX(period)` if a specific period is requested.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'` for overall metrics.
  - L3 Breakdown: Filter `l4 = '-'` for detailed analysis.
- ANALYSIS LOGIC:
  - Calculate EBITDA margin for current and previous period.
  - Identify L3 categories causing margin decline:
    - Revenue decrease (reduces EBITDA).
    - COE increase (reduces EBITDA).
- UNIFIED OUTPUT:
  - Section indicator: 'SUMMARY' for aggregate metrics, 'BREAKDOWN' for L3 details.
  - Shows unit, period, metric type, category (if applicable).
  - Revenue/COE/EBITDA values (current & previous), margins, changes, and MoM percentages.
- Order by section (SUMMARY first, then BREAKDOWN by impact magnitude).

Reference pattern (Comprehensive EBITDA margin decline analysis):
-- Part 1: Overall margin summary at L2 aggregate level
WITH margin_summary AS (
    SELECT
        'SUMMARY' AS section,
        div AS unit,
        period AS current_period,
        'AGGREGATE' AS metric_type,
        '-' AS category,
        SUM(CASE WHEN l2 = 'REVENUE' THEN real_mtd ELSE 0 END) AS current_value,
        SUM(CASE WHEN l2 = 'REVENUE' THEN prev_month ELSE 0 END) AS previous_value,
        NULL AS mom_growth_pct,
        SUM(CASE WHEN l2 = 'REVENUE' THEN real_mtd ELSE 0 END) - 
        SUM(CASE WHEN l2 = 'REVENUE' THEN prev_month ELSE 0 END) AS absolute_change,
        ROUND((SUM(CASE WHEN l2 = 'EBITDA' THEN real_mtd ELSE 0 END) * 100.0) / 
              NULLIF(SUM(CASE WHEN l2 = 'REVENUE' THEN real_mtd ELSE 0 END), 0), 2) AS ebitda_margin_current_pct,
        ROUND((SUM(CASE WHEN l2 = 'EBITDA' THEN prev_month ELSE 0 END) * 100.0) / 
              NULLIF(SUM(CASE WHEN l2 = 'REVENUE' THEN prev_month ELSE 0 END), 0), 2) AS ebitda_margin_previous_pct
    FROM cfu_performance_data
    WHERE period = 202507 -- Replace with specific period from user request
        AND div = 'TELIN' -- Replace with specific unit from user request
        AND l2 IN ('REVENUE', 'COE', 'EBITDA')
        AND l3 = '-'
    GROUP BY div, period
),
-- Part 2: Detailed L3 breakdown showing root causes
l3_breakdown AS (
    SELECT
        'BREAKDOWN' AS section,
        div AS unit,
        period AS current_period,
        l2 AS metric_type,
        l3 AS category,
        SUM(real_mtd) AS current_value,
        SUM(prev_month) AS previous_value,
        ROUND(AVG(mom), 2) AS mom_growth_pct,
        (SUM(real_mtd) - SUM(prev_month)) AS absolute_change,
        NULL AS ebitda_margin_current_pct,
        NULL AS ebitda_margin_previous_pct
    FROM cfu_performance_data
    WHERE period = 202507 -- Replace with specific period from user request
        AND div = 'TELIN' -- Replace with specific unit from user request
        AND l2 IN ('REVENUE', 'COE')
        AND l4 = '-' -- Get L3 level breakdown
        AND l3 != '-' -- Exclude L2 aggregate
    GROUP BY div, period, l2, l3
    HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_month)) < 0) -- Revenue declined
        OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_month)) > 0) -- COE increased
)
-- Combine both parts into single result
SELECT * FROM (
    SELECT
        section,
        unit,
        current_period,
        metric_type,
        category,
        current_value,
        previous_value,
        mom_growth_pct,
        absolute_change,
        ebitda_margin_current_pct,
        ebitda_margin_previous_pct,
        ROUND(ebitda_margin_current_pct - ebitda_margin_previous_pct, 2) AS ebitda_margin_change_pct
    FROM margin_summary
    UNION ALL
    SELECT
        section,
        unit,
        current_period,
        metric_type,
        category,
        current_value,
        previous_value,
        mom_growth_pct,
        absolute_change,
        ebitda_margin_current_pct,
        ebitda_margin_previous_pct,
        NULL AS ebitda_margin_change_pct
    FROM l3_breakdown
) AS combined_result
ORDER BY section ASC, (CASE WHEN metric_type = 'COE' THEN -1 ELSE 1 END * absolute_change) ASC;
'''

ebitda_improvement_recommendations_prompt = f'''
Task: Generate a SQLite query to provide recommendations for improving or maintaining EBITDA by identifying underperforming revenue products and over-achieving COE categories.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd`, `target_mtd`, `ach_mtd`, and growth metrics (`mom`, `yoy`).
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE')`.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
    - L3 level: Filter `l4 = '-'` to get breakdown by L3 categories.
- ANALYSIS LOGIC:
  - **Revenue Improvement Opportunities**:
    - Identify products with achievement < 100% (underachieving).
    - Identify products with low growth (mom < 5% or yoy < 10%).
    - Focus on Connectivity, Platform, and Service streams (L3 categories).
  - **COE Cost Saving Opportunities**:
    - Identify COE categories with achievement > 100% (over-budget).
    - These indicate areas where cost control can be improved.
- Output should show:
  - **Part 1**: Underachieving revenue products with low growth (optimization opportunities).
  - **Part 2**: Over-budget COE categories (cost saving opportunities).
- Order by gap magnitude (largest opportunities first).

Reference pattern (Unified recommendations for Revenue optimization and Cost saving):
WITH revenue_opportunities AS (
    SELECT
        'REVENUE_OPTIMIZATION' AS recommendation_type,
        div,
        period,
        l2,
        l3,
        SUM(real_mtd) AS actual_value,
        SUM(target_mtd) AS target_value,
        ROUND(AVG(ach_mtd), 2) AS achievement_pct,
        SUM(target_mtd) - SUM(real_mtd) AS gap_or_overrun,
        ROUND(AVG(mom), 2) AS mom_growth_pct,
        ROUND(AVG(yoy), 2) AS yoy_growth_pct
    FROM cfu_performance_data
    WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
        AND l2 = 'REVENUE'
        AND l4 = '-' -- Get L3 level breakdown
        AND l3 IN ('Connectivity', 'Digital Platform', 'Digital Services', 'Managed Service', 'Digital Service') -- Focus on these streams
        AND ach_mtd < 100 -- Underachieving products
        AND (mom < 5 OR yoy < 10) -- Low growth products
        AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
    GROUP BY div, period, l2, l3
),
coe_savings AS (
    SELECT
        'COST_SAVING' AS recommendation_type,
        div,
        period,
        l2,
        l3,
        SUM(real_mtd) AS actual_value,
        SUM(target_mtd) AS target_value,
        ROUND(AVG(ach_mtd), 2) AS achievement_pct,
        SUM(target_mtd) - SUM(real_mtd) AS gap_or_overrun,
        NULL AS mom_growth_pct,
        NULL AS yoy_growth_pct
    FROM cfu_performance_data
    WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
        AND l2 = 'COE'
        AND l4 = '-' -- Get L3 level breakdown
        AND ach_mtd > 100 -- Over-budget COE categories
        AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
    GROUP BY div, period, l2, l3
)
SELECT * FROM revenue_opportunities
UNION ALL
SELECT * FROM coe_savings
ORDER BY recommendation_type DESC, gap_or_overrun DESC
LIMIT 20;
'''

ebitda_margin_trend_3months_prompt = f'''
Task: Generate a SQLite query to show the trend of EBITDA Margin over the last 3 months for CFU WIB or specific units.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd` for calculations.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'EBITDA')`.
- PERIOD HANDLING (CRITICAL):
    - Query for the last 3 months using a subquery to get the last 3 periods.
    - Use: `period >= (SELECT MIN(period) FROM (SELECT DISTINCT period FROM cfu_performance_data ORDER BY period DESC LIMIT 3))`.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
- CALCULATION LOGIC:
  - Calculate EBITDA Margin for each month: (EBITDA / Revenue) * 100.
  - Show monthly trend to track margin changes.
- CFU WIB HANDLING:
  - If user asks for CFU WIB, aggregate all divisions.
  - If user asks for specific unit, filter by that div.
- Output should show: period, revenue, EBITDA, and EBITDA margin percentage.
- Order chronologically by period (oldest first).

Reference pattern (EBITDA Margin trend for last 3 months):
WITH monthly_data AS (
    SELECT
        period,
        l2,
        SUM(real_mtd) AS value
    FROM cfu_performance_data
    WHERE period >= (SELECT MIN(period) FROM (SELECT DISTINCT period FROM cfu_performance_data ORDER BY period DESC LIMIT 3))
        AND l2 IN ('REVENUE', 'EBITDA')
        AND l3 = '-'
        AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT') -- For CFU WIB aggregate
    GROUP BY period, l2
)
SELECT
    period,
    SUM(CASE WHEN l2 = 'REVENUE' THEN value ELSE 0 END) AS revenue,
    SUM(CASE WHEN l2 = 'EBITDA' THEN value ELSE 0 END) AS ebitda,
    ROUND((SUM(CASE WHEN l2 = 'EBITDA' THEN value ELSE 0 END) * 100.0) / 
          NULLIF(SUM(CASE WHEN l2 = 'REVENUE' THEN value ELSE 0 END), 0), 2) AS ebitda_margin_pct
FROM monthly_data
GROUP BY period
ORDER BY period ASC;
'''

gross_profit_margin_analysis_prompt = f'''
Task: Generate a SQLite query to calculate Gross Profit Margin for CFU WIB by determining direct costs and computing (Revenue - Direct Cost) / Revenue * 100%.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd` for calculations.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE')`.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 level: Filter `l4 = '-'` to get COE breakdown.
- CALCULATION LOGIC:
  - **Direct Cost**: All COE **except** Marketing, Personnel, and G&A (General & Administration).
  - **Indirect Cost**: Marketing + Personnel + G&A.
  - **Gross Profit**: Revenue - Direct Cost.
  - **Gross Profit Margin**: (Gross Profit / Revenue) * 100.
- CFU WIB HANDLING:
  - Aggregate all divisions (DMT, DWS, TELIN, TIF, TSAT).
- Output should show: Revenue, Direct Cost, Indirect Cost, Gross Profit, and Gross Profit Margin percentage.

Reference pattern (Gross Profit Margin calculation for CFU WIB):
WITH revenue_data AS (
    SELECT
        period,
        SUM(real_mtd) AS total_revenue
    FROM cfu_performance_data
    WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
        AND l2 = 'REVENUE'
        AND l3 = '-'
        AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
    GROUP BY period
),
coe_breakdown AS (
    SELECT
        period,
        l3,
        SUM(real_mtd) AS coe_value
    FROM cfu_performance_data
    WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
        AND l2 = 'COE'
        AND l4 = '-' -- Get L3 level breakdown
        AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
    GROUP BY period, l3
),
cost_categories AS (
    SELECT
        period,
        SUM(CASE WHEN l3 NOT IN ('Marketing', 'Personel', 'Personnel', 'Personnel Cost', 'G&A', 'General & Administration', 'Administrasi dan Umum') 
                 THEN coe_value ELSE 0 END) AS direct_cost,
        SUM(CASE WHEN l3 IN ('Marketing', 'Personel', 'Personnel', 'Personnel Cost', 'G&A', 'General & Administration', 'Administrasi dan Umum') 
                 THEN coe_value ELSE 0 END) AS indirect_cost
    FROM coe_breakdown
    GROUP BY period
)
SELECT
    r.period,
    r.total_revenue,
    c.direct_cost,
    c.indirect_cost,
    r.total_revenue + c.direct_cost AS gross_profit,
    ROUND(((r.total_revenue + c.direct_cost) * 100.0) / NULLIF(r.total_revenue, 0), 2) AS gross_profit_margin_pct
FROM revenue_data r
JOIN cost_categories c ON r.period = c.period;
'''

net_income_proportion_analysis_prompt = f'''
Task: Generate a SQLite query to calculate the proportion (percentage) of a specific unit's NET INCOME against the total CFU WIB NET INCOME for the latest period.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd` or `real_ytd` as the actual NET INCOME value depending on user request (default to MTD if not specified).
- METRIC FILTERING (CRITICAL):
    - MUST filter `l2 = 'NET INCOME'` ONLY.
    - DO NOT include other metrics.
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a period (e.g., "Juli 2025", "July 2025", "202507"), YOU MUST EXTRACT IT as integer YYYYMM (e.g., 202507) and use `period = 202507`.
    - DO NOT use `MAX(period)` if a specific period is requested.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
- CALCULATION LOGIC:
  - Calculate the unit's NET INCOME as a percentage of total CFU WIB NET INCOME.
  - Formula: (Unit NET INCOME / Total CFU WIB NET INCOME) * 100.
  - Use SUM aggregation for both unit and total.
- Output should show: unit name, unit NET INCOME, total CFU WIB NET INCOME, and percentage.

Reference pattern (NET INCOME proportion for specific unit):
SELECT
    div,
    period,
    l2,
    SUM(real_mtd) AS unit_net_income,
    (SELECT SUM(real_mtd) 
     FROM cfu_performance_data 
     WHERE period = (SELECT MAX(period) FROM cfu_performance_data) 
       AND l2 = 'NET INCOME' 
       AND l3 = '-'
       AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')) AS total_cfu_wib_net_income,
    ROUND((SUM(real_mtd) * 100.0) / 
          (SELECT SUM(real_mtd) 
           FROM cfu_performance_data 
           WHERE period = (SELECT MAX(period) FROM cfu_performance_data) 
             AND l2 = 'NET INCOME' 
             AND l3 = '-'
             AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS proportion_percentage
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN' -- Replace with specific unit from user request
    AND l2 = 'NET INCOME'
    AND l3 = '-'
GROUP BY div, period, l2;
'''

net_income_proportion_trend_yearly_prompt = f'''
Task: Generate a SQLite query to show the trend of a specific unit's NET INCOME proportion (percentage) against total CFU WIB NET INCOME over the last 3 years (yearly basis).

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_ytd` for yearly analysis.
- METRIC FILTERING (CRITICAL):
    - MUST filter `l2 = 'NET INCOME'` ONLY.
    - DO NOT include other metrics.
- PERIOD HANDLING (CRITICAL):
    - Query for the last 3 years of data (yearly basis).
    - For each year, use the LATEST available period (highest period) in that year.
    - Example: If data has 202301-202312, 202401-202412, 202501-202510, use 202312, 202412, and 202510.
    - This ensures we get complete data even if current year hasn't finished yet.
    - Extract year from period and get MAX(period) for each year.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
- CALCULATION LOGIC:
  - For each year, calculate: (Unit NET INCOME YTD / Total CFU WIB NET INCOME YTD) * 100.
  - Show trend over 3 years.
- Output should show: year, period used, unit NET INCOME YTD, total CFU WIB NET INCOME YTD, and percentage for each year.
- Order chronologically by year (oldest first).

Reference pattern (3-year NET INCOME proportion trend for specific unit):
WITH latest_periods_per_year AS (
    SELECT 
        CAST(period / 100 AS INTEGER) AS year,
        MAX(period) AS latest_period
    FROM cfu_performance_data
    WHERE CAST(period / 100 AS INTEGER) >= (SELECT CAST(MAX(period) / 100 AS INTEGER) - 2 FROM cfu_performance_data)
    GROUP BY CAST(period / 100 AS INTEGER)
)
SELECT
    lp.year,
    lp.latest_period AS period,
    t1.div,
    t1.l2,
    SUM(t1.real_ytd) AS unit_net_income_ytd,
    (SELECT SUM(real_ytd) 
     FROM cfu_performance_data 
     WHERE period = lp.latest_period
       AND l2 = 'NET INCOME' 
       AND l3 = '-'
       AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')) AS total_cfu_wib_net_income_ytd,
    ROUND((SUM(t1.real_ytd) * 100.0) / 
          (SELECT SUM(real_ytd) 
           FROM cfu_performance_data 
           WHERE period = lp.latest_period
             AND l2 = 'NET INCOME' 
             AND l3 = '-'
             AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS proportion_percentage
FROM cfu_performance_data t1
JOIN latest_periods_per_year lp ON t1.period = lp.latest_period
WHERE t1.div = 'TELIN' -- Replace with specific unit from user request
    AND t1.l2 = 'NET INCOME'
    AND t1.l3 = '-'
GROUP BY lp.year, lp.latest_period, t1.div, t1.l2
ORDER BY lp.year ASC;
'''

net_income_proportion_trend_monthly_prompt = f'''
Task: Generate a SQLite query to show the trend of a specific unit's NET INCOME proportion (percentage) against total CFU WIB NET INCOME within the current year (monthly basis, from January to latest available period).

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd` for monthly analysis.
- METRIC FILTERING (CRITICAL):
    - MUST filter `l2 = 'NET INCOME'` ONLY.
    - DO NOT include other metrics.
- PERIOD HANDLING (CRITICAL):
    - Query for the current year from January to the latest available period.
    - Determine current year from MAX(period) and filter all periods in that year.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
- CALCULATION LOGIC:
  - For each month, calculate: (Unit NET INCOME MTD / Total CFU WIB NET INCOME MTD) * 100.
  - Show monthly progression within the current year.
- Output should show: period, unit NET INCOME MTD, total CFU WIB NET INCOME MTD, and percentage for each month.
- Order chronologically by period (oldest first).

Reference pattern (Current year monthly NET INCOME proportion trend for specific unit):
SELECT
    t1.period,
    t1.div,
    t1.l2,
    SUM(t1.real_mtd) AS unit_net_income_mtd,
    (SELECT SUM(real_mtd) 
     FROM cfu_performance_data 
     WHERE period = t1.period
       AND l2 = 'NET INCOME' 
       AND l3 = '-'
       AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')) AS total_cfu_wib_net_income_mtd,
    ROUND((SUM(t1.real_mtd) * 100.0) / 
          (SELECT SUM(real_mtd) 
           FROM cfu_performance_data 
           WHERE period = t1.period
             AND l2 = 'NET INCOME' 
             AND l3 = '-'
             AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')), 2) AS proportion_percentage
FROM cfu_performance_data t1
WHERE CAST(t1.period / 100 AS INTEGER) = (SELECT CAST(MAX(period) / 100 AS INTEGER) FROM cfu_performance_data)
    AND t1.div = 'TELIN' -- Replace with specific unit from user request
    AND t1.l2 = 'NET INCOME'
    AND t1.l3 = '-'
GROUP BY t1.period, t1.div, t1.l2
ORDER BY t1.period ASC;
'''

cfu_wib_net_income_mom_decline_check_prompt = f'''
Task: Generate a SQLite query to check if there is a Month-over-Month (MoM) decline in total CFU WIB NET INCOME for the latest period, and identify which units contributed to this decline.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd` and `prev_month` columns.
- METRIC FILTERING (CRITICAL):
    - MUST filter `l2 = 'NET INCOME'` ONLY.
    - DO NOT include other metrics.
- PERIOD HANDLING (CRITICAL):
    - If user specifies a period (e.g. "September 2025"), use that period (e.g. `period = 202509`).
    - ONLY if no period is specified, use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
- CALCULATION LOGIC:
  - First, check total CFU WIB NET INCOME MoM growth.
  - If MoM is negative, it indicates a decline.
  - Then show each unit's NET INCOME, MoM percentage, and absolute change.
  - Calculate absolute change: `SUM(real_mtd) - SUM(prev_month)`.
  - Calculate MoM percentage: `(SUM(real_mtd) - SUM(prev_month)) * 100.0 / SUM(prev_month)`.
- CFU WIB HANDLING:
  - Query all 5 units (DMT, DWS, TELIN, TIF, TSAT) individually.
  - Also show total CFU WIB aggregate.
- Output should show: unit name, period, NET INCOME MTD, MoM percentage, and absolute change.
- Highlight units with negative MoM contributing to overall decline.

Reference pattern (CFU WIB NET INCOME MoM decline check):
SELECT
    div,
    period,
    l2,
    SUM(real_mtd) AS net_income_mtd,
    PRINTF('%.2f%%', (SUM(real_mtd) - SUM(prev_month)) * 100.0 / NULLIF(SUM(prev_month), 0)) AS mom_percentage,
    (SUM(real_mtd) - SUM(prev_month)) AS absolute_change
FROM cfu_performance_data
WHERE period = 202509 -- Replace with specific period from user request (e.g. 202509), or use (SELECT MAX(period)...) if not specified
    AND l2 = 'NET INCOME'
    AND l3 = '-'
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
GROUP BY div, period, l2
UNION ALL
SELECT
    'CFU WIB' AS div,
    period,
    l2,
    SUM(real_mtd) AS net_income_mtd,
    PRINTF('%.2f%%', (SUM(real_mtd) - SUM(prev_month)) * 100.0 / NULLIF(SUM(prev_month), 0)) AS mom_percentage,
    (SUM(real_mtd) - SUM(prev_month)) AS absolute_change
FROM cfu_performance_data
WHERE period = 202509 -- Replace with specific period from user request (e.g. 202509), or use (SELECT MAX(period)...) if not specified
    AND l2 = 'NET INCOME'
    AND l3 = '-'
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
GROUP BY period, l2
ORDER BY div;
'''

net_income_mom_decline_cause_prompt = f'''
Task: Generate a SQLite query to identify the cause of NET INCOME Month-over-Month (MoM) decline by analyzing Revenue and COE changes for each unit.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd` and `mom` columns.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE', 'NET INCOME')`.
    - Analyze Revenue and COE to determine NET INCOME decline cause.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 level: Filter `l4 = '-'` to get breakdown by L3 categories.
- ANALYSIS LOGIC:
  - For each unit with NET INCOME MoM decline:
    - If Revenue MoM is negative (declined), identify top L3 Revenue contributors to the decline.
    - If COE MoM is positive (increased), identify top L3 COE contributors to the increase.
  - Calculate absolute change for Revenue and COE.
  - NET INCOME is affected by Revenue - COE, so decline can be caused by Revenue decline or COE increase.
- Output should show:
  - Unit name, metric (Revenue/COE), L3 category, MTD value, MoM percentage, absolute change.
  - Focus on negative contributors (Revenue decline or COE increase).
- Order by absolute change magnitude (largest impact first).

Reference pattern (NET INCOME MoM decline cause analysis):
SELECT
    div,
    period,
    l2,
    l3,
    SUM(real_mtd) AS mtd_value,
    SUM(prev_month) AS prev_month_value,
    ROUND(AVG(mom), 2) AS mom_percentage,
    (SUM(real_mtd) - SUM(prev_month)) AS absolute_change
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 IN ('REVENUE', 'COE')
    AND l4 = '-' -- Get L3 level breakdown
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
GROUP BY div, period, l2, l3
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_month)) < 0) -- Revenue drop
    OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_month)) > 0) -- Cost rise
ORDER BY div, (CASE WHEN l2 = 'COE' THEN -1 ELSE 1 END * (SUM(real_mtd) - SUM(prev_month))) ASC;
'''

net_income_mom_increase_cause_prompt = f'''
Task: Generate a SQLite query to identify the cause of NET INCOME Month-over-Month (MoM) increase by analyzing Revenue and COE changes for each unit.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd` and `mom` columns.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE', 'NET INCOME')`.
    - Analyze Revenue and COE to determine NET INCOME increase cause.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 level: Filter `l4 = '-'` to get breakdown by L3 categories.
- ANALYSIS LOGIC:
  - For each unit with NET INCOME MoM increase:
    - If Revenue MoM is positive (increased), identify top L3 Revenue contributors to the increase.
    - If COE MoM is negative (decreased), identify top L3 COE contributors to the decrease.
  - Calculate absolute change for Revenue and COE.
  - NET INCOME is affected by Revenue - COE, so increase can be caused by Revenue increase or COE decrease.
- Output should show:
  - Unit name, metric (Revenue/COE), L3 category, MTD value, MoM percentage, absolute change.
  - Focus on positive contributors (Revenue increase or COE decrease).
- Order by absolute change magnitude (largest positive impact first).

Reference pattern (NET INCOME MoM increase cause analysis):
SELECT
    div,
    period,
    l2,
    l3,
    SUM(real_mtd) AS mtd_value,
    SUM(prev_month) AS prev_month_value,
    ROUND(AVG(mom), 2) AS mom_percentage,
    (SUM(real_mtd) - SUM(prev_month)) AS absolute_change
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 IN ('REVENUE', 'COE')
    AND l4 = '-' -- Get L3 level breakdown
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
GROUP BY div, period, l2, l3
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_month)) > 0) -- Revenue rise
    OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_month)) < 0) -- Cost drop
ORDER BY div, (CASE WHEN l2 = 'COE' THEN -1 ELSE 1 END * (SUM(real_mtd) - SUM(prev_month))) DESC;
'''

net_income_yoy_decline_cause_prompt = f'''
Task: Generate a SQLite query to identify the cause of NET INCOME Year-over-Year (YoY) decline by analyzing Revenue and COE changes for each unit.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd`, `prev_year`, and `yoy` columns.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE', 'NET INCOME')`.
    - Analyze Revenue and COE to determine NET INCOME YoY decline cause.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 level: Filter `l4 = '-'` to get breakdown by L3 categories.
- ANALYSIS LOGIC:
  - For each unit with NET INCOME YoY decline:
    - If Revenue YoY is negative (declined), identify top L3 Revenue contributors to the decline.
    - If COE YoY is positive (increased), identify top L3 COE contributors to the increase.
  - Calculate absolute change for Revenue and COE: current value - previous year value.
  - NET INCOME is affected by Revenue - COE, so decline can be caused by Revenue decline or COE increase.
- Output should show:
  - Unit name, metric (Revenue/COE), L3 category, MTD value, previous year value, YoY percentage, absolute change.
  - Focus on negative contributors (Revenue decline or COE increase).
- Order by absolute change magnitude (largest impact first).

Reference pattern (NET INCOME YoY decline cause analysis):
SELECT
    div,
    period,
    l2,
    l3,
    SUM(real_mtd) AS mtd_value,
    SUM(prev_year) AS prev_year_value,
    ROUND(AVG(yoy), 2) AS yoy_percentage,
    (SUM(real_mtd) - SUM(prev_year)) AS absolute_change
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 IN ('REVENUE', 'COE')
    AND l4 = '-' -- Get L3 level breakdown
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_year)) < 0) -- Revenue drop
    OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_year)) > 0) -- Cost rise
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_year)) < 0) -- Revenue drop
    OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_year)) > 0) -- Cost rise
ORDER BY div, (CASE WHEN l2 = 'COE' THEN -1 ELSE 1 END * (SUM(real_mtd) - SUM(prev_year))) ASC;
'''

net_income_yoy_increase_cause_prompt = f'''
Task: Generate a SQLite query to identify the cause of NET INCOME Year-over-Year (YoY) increase by analyzing Revenue and COE changes for each unit.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd`, `prev_year`, and `yoy` columns.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE', 'NET INCOME')`.
    - Analyze Revenue and COE to determine NET INCOME YoY increase cause.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3 level: Filter `l4 = '-'` to get breakdown by L3 categories.
- ANALYSIS LOGIC:
  - For each unit with NET INCOME YoY increase:
    - If Revenue YoY is positive (increased), identify top L3 Revenue contributors to the increase.
    - If COE YoY is negative (decreased), identify top L3 COE contributors to the decrease.
  - Calculate absolute change for Revenue and COE: current value - previous year value.
  - NET INCOME is affected by Revenue - COE, so increase can be caused by Revenue increase or COE decrease.
- Output should show:
  - Unit name, metric (Revenue/COE), L3 category, MTD value, previous year value, YoY percentage, absolute change.
  - Focus on positive contributors (Revenue increase or COE decrease).
- Order by absolute change magnitude (largest positive impact first).

Reference pattern (NET INCOME YoY increase cause analysis):
SELECT
    div,
    period,
    l2,
    l3,
    SUM(real_mtd) AS mtd_value,
    SUM(prev_year) AS prev_year_value,
    ROUND(AVG(yoy), 2) AS yoy_percentage,
    (SUM(real_mtd) - SUM(prev_year)) AS absolute_change
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND l2 IN ('REVENUE', 'COE')
    AND l4 = '-' -- Get L3 level breakdown
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_year)) > 0) -- Revenue rise
    OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_year)) < 0) -- Cost drop
ORDER BY div, (CASE WHEN l2 = 'COE' THEN -1 ELSE 1 END * (SUM(real_mtd) - SUM(prev_year))) DESC; > 0 -- Positive impact on Net Income (Revenue rise or Cost drop)
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_year)) > 0) -- Revenue rise
    OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_year)) < 0) -- Cost drop
ORDER BY div, (CASE WHEN l2 = 'COE' THEN -1 ELSE 1 END * (SUM(real_mtd) - SUM(prev_year))) DESC;
'''

unit_net_income_mom_decline_cause_prompt = f'''
Task: Generate a SQLite query to identify the cause of NET INCOME Month-over-Month (MoM) decline for a specific unit by analyzing Revenue and COE changes at L3 level.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd`, `prev_month`, and `mom` columns.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE')`.
    - Analyze Revenue and COE to determine NET INCOME MoM decline cause for the specified unit.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L3 level: Filter `l4 = '-'` to get breakdown by L3 categories.
- ANALYSIS LOGIC:
  - For the specified unit with NET INCOME MoM decline:
    - If Revenue MoM is negative (declined), identify top L3 Revenue contributors to the decline.
    - If COE MoM is positive (increased), identify top L3 COE contributors to the increase.
  - Calculate absolute change for Revenue and COE: current month value - previous month value.
  - NET INCOME is affected by Revenue - COE, so decline can be caused by Revenue decline or COE increase.
- Output should show:
  - Metric (Revenue/COE), L3 category, MTD value, previous month value, MoM percentage, absolute change.
  - Focus on negative contributors (Revenue decline or COE increase).
- Order by absolute change magnitude (largest negative impact first).

Reference pattern (Unit-specific NET INCOME MoM decline cause analysis):
SELECT
    div,
    period,
    l2,
    l3,
    SUM(real_mtd) AS mtd_value,
    SUM(prev_month) AS prev_month_value,
    ROUND(AVG(mom), 2) AS mom_percentage,
    (SUM(real_mtd) - SUM(prev_month)) AS absolute_change
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN' -- Replace with specific unit from user request
    AND l2 IN ('REVENUE', 'COE')
    AND l4 = '-' -- Get L3 level breakdown
GROUP BY div, period, l2, l3
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_month)) < 0) -- Revenue drop
    OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_month)) > 0) -- Cost rise
ORDER BY (CASE WHEN l2 = 'COE' THEN -1 ELSE 1 END * (SUM(real_mtd) - SUM(prev_month))) ASC;
'''

unit_net_income_mom_increase_cause_prompt = f'''
Task: Generate a SQLite query to identify the cause of NET INCOME Month-over-Month (MoM) increase for a specific unit by analyzing Revenue and COE changes at L3 level.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd`, `prev_month`, and `mom` columns.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE')`.
    - Analyze Revenue and COE to determine NET INCOME MoM increase cause for the specified unit.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - L3 level: Filter `l4 = '-'` to get breakdown by L3 categories.
- ANALYSIS LOGIC:
  - For the specified unit with NET INCOME MoM increase:
    - If Revenue MoM is positive (increased), identify top L3 Revenue contributors to the increase.
    - If COE MoM is negative (decreased), identify top L3 COE contributors to the decrease.
  - Calculate absolute change for Revenue and COE: current month value - previous month value.
  - NET INCOME is affected by Revenue - COE, so increase can be caused by Revenue increase or COE decrease.
- Output should show:
  - Metric (Revenue/COE), L3 category, MTD value, previous month value, MoM percentage, absolute change.
  - Focus on positive contributors (Revenue increase or COE decrease).
- Order by absolute change magnitude (largest positive impact first).

Reference pattern (Unit-specific NET INCOME MoM increase cause analysis):
SELECT
    div,
    period,
    l2,
    l3,
    SUM(real_mtd) AS mtd_value,
    SUM(prev_month) AS prev_month_value,
    ROUND(AVG(mom), 2) AS mom_percentage,
    (SUM(real_mtd) - SUM(prev_month)) AS absolute_change
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN' -- Replace with specific unit from user request
    AND l2 IN ('REVENUE', 'COE')
    AND l4 = '-' -- Get L3 level breakdown
GROUP BY div, period, l2, l3
HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_month)) > 0) -- Revenue rise
    OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_month)) < 0) -- Cost drop
ORDER BY (CASE WHEN l2 = 'COE' THEN -1 ELSE 1 END * (SUM(real_mtd) - SUM(prev_month))) DESC;
'''

unit_net_income_margin_decline_cause_prompt = f'''
Task: Generate a comprehensive SQLite query to analyze NET INCOME margin decline for a specific unit in a specific period, showing both overall margin comparison and detailed L3 breakdown of causes in a single result.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd`, `prev_month`, and `mom` columns.
- METRIC FILTERING (CRITICAL):
    - Query `l2 IN ('REVENUE', 'COE', 'NET INCOME')`.
    - Calculate NET INCOME margin: (NET INCOME / Revenue) * 100.
- PERIOD HANDLING (CRITICAL):
    - IF user specifies a period (e.g., "Oktober 2025", "October 2025", "202510"), YOU MUST EXTRACT IT as integer YYYYMM (e.g., 202510) and use `period = 202510`.
    - DO NOT use `MAX(period)` if a specific period is requested.
    - ONLY use `period = (SELECT MAX(period) FROM cfu_performance_data)` if NO period is specified.
- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'` for overall metrics.
  - L3 Breakdown: Filter `l4 = '-'` for detailed analysis.
- ANALYSIS LOGIC:
  - Calculate NET INCOME margin for current and previous period.
  - Identify L3 categories causing margin decline:
    - Revenue decrease (reduces NET INCOME).
    - COE increase (reduces NET INCOME).
- UNIFIED OUTPUT:
  - Section indicator: 'SUMMARY' for aggregate metrics, 'BREAKDOWN' for L3 details.
  - Shows unit, period, metric type, category (if applicable).
  - Revenue/COE/NET INCOME values (current & previous), margins, changes, and MoM percentages.
- Order by section (SUMMARY first, then BREAKDOWN by impact magnitude).

Reference pattern (Comprehensive NET INCOME margin decline analysis):
-- Part 1: Overall margin summary at L2 aggregate level
WITH margin_summary AS (
    SELECT
        'SUMMARY' AS section,
        div AS unit,
        period AS current_period,
        'AGGREGATE' AS metric_type,
        '-' AS category,
        SUM(CASE WHEN l2 = 'REVENUE' THEN real_mtd ELSE 0 END) AS current_value,
        SUM(CASE WHEN l2 = 'REVENUE' THEN prev_month ELSE 0 END) AS previous_value,
        NULL AS mom_growth_pct,
        SUM(CASE WHEN l2 = 'REVENUE' THEN real_mtd ELSE 0 END) - 
        SUM(CASE WHEN l2 = 'REVENUE' THEN prev_month ELSE 0 END) AS absolute_change,
        ROUND((SUM(CASE WHEN l2 = 'NET INCOME' THEN real_mtd ELSE 0 END) * 100.0) / 
              NULLIF(SUM(CASE WHEN l2 = 'REVENUE' THEN real_mtd ELSE 0 END), 0), 2) AS net_income_margin_current_pct,
        ROUND((SUM(CASE WHEN l2 = 'NET INCOME' THEN prev_month ELSE 0 END) * 100.0) / 
              NULLIF(SUM(CASE WHEN l2 = 'REVENUE' THEN prev_month ELSE 0 END), 0), 2) AS net_income_margin_previous_pct
    FROM cfu_performance_data
    WHERE period = 202510 -- Replace with user-specified period
        AND div = 'TELIN' -- Replace with specific unit from user request
        AND l2 IN ('REVENUE', 'COE', 'NET INCOME')
        AND l3 = '-'
    GROUP BY div, period
),
-- Part 2: Detailed L3 breakdown showing root causes
l3_breakdown AS (
    SELECT
        'BREAKDOWN' AS section,
        div AS unit,
        period AS current_period,
        l2 AS metric_type,
        l3 AS category,
        SUM(real_mtd) AS current_value,
        SUM(prev_month) AS previous_value,
        ROUND(AVG(mom), 2) AS mom_growth_pct,
        (SUM(real_mtd) - SUM(prev_month)) AS absolute_change,
        NULL AS net_income_margin_current_pct,
        NULL AS net_income_margin_previous_pct
    FROM cfu_performance_data
    WHERE period = 202510 -- Replace with user-specified period
        AND div = 'TELIN' -- Replace with specific unit from user request
        AND l2 IN ('REVENUE', 'COE')
        AND l4 = '-' -- Get L3 level breakdown
        AND l3 != '-' -- Exclude L2 aggregate
    GROUP BY div, period, l2, l3
    HAVING (l2 = 'REVENUE' AND (SUM(real_mtd) - SUM(prev_month)) < 0) -- Revenue declined
        OR (l2 = 'COE' AND (SUM(real_mtd) - SUM(prev_month)) > 0) -- COE increased
)
-- Combine both parts into single result
SELECT * FROM (
    SELECT
        section,
        unit,
        current_period,
        metric_type,
        category,
        current_value,
        previous_value,
        mom_growth_pct,
        absolute_change,
        net_income_margin_current_pct,
        net_income_margin_previous_pct,
        ROUND(net_income_margin_current_pct - net_income_margin_previous_pct, 2) AS net_income_margin_change_pct
    FROM margin_summary
    UNION ALL
    SELECT
        section,
        unit,
        current_period,
        metric_type,
        category,
        current_value,
        previous_value,
        mom_growth_pct,
        absolute_change,
        net_income_margin_current_pct,
        net_income_margin_previous_pct,
        NULL AS net_income_margin_change_pct
    FROM l3_breakdown
) AS combined_result
ORDER BY section ASC, (CASE WHEN metric_type = 'COE' THEN -1 ELSE 1 END * absolute_change) ASC;
'''

net_income_improvement_recommendations_prompt = f'''
Task: Generate a SQLite query to provide recommendations for improving or maintaining NET INCOME by identifying underperforming revenue products and high-achieving COE items that need optimization.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

{valid_values_str}

Rules:
- COLUMN NAMES (CRITICAL):
    - DO NOT alias columns (e.g. `real_mtd` as `actual`). Keep original column names from the table.
    - Use `real_mtd`, `target_mtd`, `ach_mtd`, and `mom` columns.
- METRIC FILTERING (CRITICAL):
    - Query for `l2 IN ('REVENUE', 'COE')`.
    - Focus on Revenue products with low achievement or growth.
    - Focus on COE items with excessive achievement as cost-saving opportunities.
- PERIOD HANDLING (CRITICAL):
    - Use the latest available period: `period = (SELECT MAX(period) FROM cfu_performance_data)`.
- HIERARCHY LOGIC (Crucial):
  - For Revenue: Use L4 level (product level) filtered by `l5 = '-'`.
  - Prioritize products from Connectivity, Platform, and Service streams (L3).
  - For COE: Use L3 or L4 level to identify high-achieving cost categories.
- RECOMMENDATION LOGIC:
  - Revenue optimization:
    - Identify products with achievement < 100% (underachieving).
    - Identify products with low MoM growth (< 5%).
    - Prioritize Connectivity, Platform, and Service stream products.
  - COE optimization:
    - Identify COE categories with achievement > 100% (overspending).
    - These are candidates for cost-saving initiatives.
- Output should show two sections:
  1. Revenue products to maximize (underachieving or low growth).
  2. COE categories to optimize (overspending).
- Order by priority (worst performance/highest overspending first).

Reference pattern (Unified recommendations for Revenue optimization and Cost saving):
WITH revenue_opportunities AS (
    SELECT
        'REVENUE_OPTIMIZATION' AS recommendation_type,
        div,
        period,
        l2,
        l3,
        l4,
        SUM(real_mtd) AS actual_value,
        SUM(target_mtd) AS target_value,
        ROUND(AVG(ach_mtd), 2) AS achievement_pct,
        SUM(target_mtd) - SUM(real_mtd) AS gap_or_overrun,
        ROUND(AVG(mom), 2) AS mom_growth_pct
    FROM cfu_performance_data
    WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
        AND l2 = 'REVENUE'
        AND l5 = '-' -- Product level
        AND l3 IN ('Connectivity', 'Platform', 'Service') -- Focus on these streams
        AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
    GROUP BY div, period, l2, l3, l4
    HAVING ROUND(AVG(ach_mtd), 2) < 100 -- Underachieving products
        OR ROUND(AVG(mom), 2) < 5 -- Low growth products
),
coe_savings AS (
    SELECT
        'COST_SAVING' AS recommendation_type,
        div,
        period,
        l2,
        l3,
        '-' AS l4,
        SUM(real_mtd) AS actual_value,
        SUM(target_mtd) AS target_value,
        ROUND(AVG(ach_mtd), 2) AS achievement_pct,
        SUM(real_mtd) - SUM(target_mtd) AS gap_or_overrun,
        NULL AS mom_growth_pct
    FROM cfu_performance_data
    WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
        AND l2 = 'COE'
        AND l4 = '-' -- L3 level
        AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
    GROUP BY div, period, l2, l3
    HAVING ROUND(AVG(ach_mtd), 2) > 100 -- Overspending categories
)
SELECT * FROM revenue_opportunities
UNION ALL
SELECT * FROM coe_savings
ORDER BY recommendation_type DESC, gap_or_overrun DESC
LIMIT 20;
'''

