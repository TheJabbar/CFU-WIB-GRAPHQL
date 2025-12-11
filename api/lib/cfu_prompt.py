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

top_contributing_segments_prompt = '''
Task: Find the business segments/divisions that contribute the most to Revenue, COE, EBITDA, and Net Income for CFU WIB by analyzing actual values and their percentages against the total.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

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

revenue_proportion_analysis_prompt = '''
Task: Calculate the proportion of revenue for a specific unit against total CFU WIB revenue and analyze trends over time.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

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

revenue_growth_analysis_prompt = '''
Task: Perform comprehensive revenue growth analysis covering MoM and YoY revenue analysis for CFU WIB and all individual units, including checking for declines and increases in revenue by product.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- Handle the following types of queries:
  1. "Apakah terjadi penurunan revenue secara Month on Month / MOM di CFU WIB?" - Check if there is MoM revenue decline in total CFU WIB and identify units that contribute to the decline
  2. "Produk apa saja yang mengalami penurunan Revenue secara Month on Month / MOM?" - Find products with MoM revenue decrease across all units and calculate absolute revenue decrease
  3. "Produk apa saja yang mengalami kenaikan Revenue secara Month on Month / MOM?" - Find products with MoM revenue increase across all units and calculate absolute revenue increase
  4. "Produk apa saja yang mengalami penurunan Revenue secara Year on Year / YoY?" - Find products with YoY revenue decrease across all units and calculate absolute revenue decrease
  5. "Produk apa saja yang mengalami kenaikan Revenue secara Year on Year / YoY?" - Find products with YoY revenue increase across all units and calculate absolute revenue increase
  6. "Apa penyebab terjadinya penurunan Revenue MOM untuk [unit]?" - Identify reasons for MoM revenue decline for specific unit
  7. "Dari seluruh CFU WIB, produk apa yang paling berkontribusi terhadap revenue CFU WIB?" - Find top 10 products with highest revenue contribution to total CFU WIB with revenue and percentage of total
  8. "Dari seluruh CFU WIB, produk apa yang paling berkontribusi terhadap ketidaktercapaian revenue CFU WIB?" - Find products with largest gaps between target and actual revenue (underachievement), showing shortfall and achievement percentage
  9. "Bagaimana pertumbuhan pendapatan / revenue dibandingkan periode sebelumnya?" - Show MoM and YoY revenue growth for CFU WIB and units, including products that contribute to decline
  10. "Apakah ada produk yang mengalami lonjakan Revenue secara MoM pada tahun [tahun]?" - Find products with revenue surge (MoM > 10% above average) in specified year compared to 3-month average

- Determine which type of query based on user input and generate appropriate SQL:
  - For CFU WIB MoM decline check: Query total revenue for CFU WIB and identify declining units
  - For MoM revenue decrease by product: Query l2 = 'REVENUE' AND mom < 0, order by biggest absolute decrease
  - For MoM revenue increase by product: Query l2 = 'REVENUE' AND mom > 0, order by biggest absolute increase
  - For YoY revenue decrease by product: Query l2 = 'REVENUE' AND yoy < 0, order by biggest absolute decrease
  - For YoY revenue increase by product: Query l2 = 'REVENUE' AND yoy > 0, order by biggest absolute increase
  - For unit-specific MoM decline cause: Filter for specific unit, l2 = 'REVENUE' AND mom < 0, order by biggest absolute decrease
  - For top revenue contributors: Query l2 = 'REVENUE', sum real_mtd, order by revenue DESC, calculate percentage of total
  - For underachievement analysis: Query l2 = 'REVENUE', calculate (target - actual) as shortfall, order by largest shortfall
  - For growth analysis: Query for MoM/YoY growth for CFU WIB and units, including contributor products for decline
  - For revenue surge in specific year: Query MoM values for specific year, compare with 3-month average to identify surges

- CFU WIB HANDLING (CRITICAL):
  - For total CFU WIB: Include all divisions (DMT, DWS, TELIN, TIF, TSAT) in the aggregation
  - For specific units: Filter for that specific division

- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3/L4 detailed products: Filter `l5 = '-'` to get L4 items

- Always include both absolute change and percentage change in results where appropriate
- Calculate absolute change as: real_mtd - prev_month (for MoM) or real_mtd - prev_year (for YoY)
- Calculate percentage change as: ((current - previous) / previous) * 100 (with safety check for division by zero)
- Calculate percentage of total as: (individual_value / total_value) * 100
- ORDER BY appropriate metric depending on query type:
  - For decrease analysis: ORDER BY (SUM(real_mtd) - SUM(prev_month)) ASC or (SUM(real_mtd) - SUM(prev_year)) ASC
  - For increase analysis: ORDER BY (SUM(real_mtd) - SUM(prev_month)) DESC or (SUM(real_mtd) - SUM(prev_year)) DESC
  - For top contributors: ORDER BY revenue DESC
  - For underachievement: ORDER BY (target - actual) DESC
- LIMIT to 5-10 results initially (LIMIT 10), except for top contributors (LIMIT 10), allow for more data to be displayed if user requests
- ALWAYS include `period` in the SELECT clause where appropriate

Reference patterns based on query type:

1. CFU WIB MoM decline check:
-- Query to get actual and MoM revenue data for total CFU WIB, and identify units that contribute to MoM decline
WITH cfu_wib_total AS (
    SELECT
        'CFU WIB' AS unit_name,
        period,
        SUM(real_mtd) AS actual_revenue,
        SUM(prev_month) AS prev_month_revenue,
        SUM(real_mtd) - SUM(prev_month) AS absolute_change,
        ROUND(AVG(mom), 2) AS mom_growth_pct,
        CASE WHEN AVG(mom) < 0 THEN 1 ELSE 0 END AS has_decline
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
    actual_revenue,
    prev_month_revenue,
    absolute_change,
    mom_growth_pct,
    CASE
        WHEN has_decline = 1 THEN 'Decline'
        ELSE 'Growth'
    END AS mom_status
FROM cfu_wib_total;

-- Identify units that contribute to the MoM decline (only if CFU WIB has negative MoM growth)
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
    AND EXISTS (SELECT 1 FROM cfu_wib_total WHERE has_decline = 1)  -- Only if total CFU WIB has decline
    AND AVG(mom) < 0  -- Only return units with negative MoM growth (contribute to decline)
GROUP BY period, div
ORDER BY mom_growth_pct ASC;

2. Products with biggest MoM revenue decrease:
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

3. Products with biggest MoM revenue increase:
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

4. Products with biggest YoY revenue decrease:
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

5. Products with biggest YoY revenue increase:
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

6. Root cause analysis for specific unit MoM revenue decline:
SELECT
    div AS unit_name,
    l3 AS product_category,
    l4 AS product_detail,
    period,
    SUM(real_mtd) AS revenue_current,
    SUM(prev_month) AS revenue_previous_month,
    SUM(real_mtd) - SUM(prev_month) AS absolute_difference,
    ROUND(((SUM(real_mtd) - SUM(prev_month)) / CASE WHEN SUM(prev_month) = 0 THEN 1 ELSE ABS(SUM(prev_month)) END) * 100, 2) AS percentage_change,
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

7. Products with highest revenue contribution to CFU WIB:
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
    AND l3 = '-' -- Get L2 aggregates for revenue
    AND l5 = '-' -- Get L4 items for detailed product analysis
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
GROUP BY period, div, l3, l4
ORDER BY product_revenue DESC
LIMIT 10;

8. Products contributing most to underachievement (largest revenue shortfalls):
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
    AND l3 = '-' -- Get L2 aggregates
    AND l5 = '-' -- Get L4 items for detailed product analysis
    AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
    AND ach_mtd < 100 -- Only underachieving products
GROUP BY period, div, l3, l4
ORDER BY (SUM(target_mtd) - SUM(real_mtd)) DESC -- DESC for largest shortfalls
LIMIT 10;

9. MoM and YoY growth analysis for CFU WIB and units, including contributor products for decline:
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

-- If YoY growth is negative, identify products that contributed to the decline
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

10. Products with revenue surge (MoM > 10% above average) in a specific year:
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

cfu_wib_mom_revenue_decline_check_prompt = '''
Task: Check if there is a revenue decline (Month on Month / MOM) in CFU WIB by performing query to extract total actual and MoM revenue for CFU WIB and check units that contribute to the MoM decline.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

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

mom_revenue_decrease_products_prompt = '''
Task: Find products that experienced revenue decline (Month on Month / MOM) across all units and calculate absolute revenue decrease (current revenue - previous month revenue), then display top 5-10 products with biggest absolute decrease in order.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

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

mom_revenue_increase_products_prompt = '''
Task: Find products that experienced revenue increase (Month on Month / MOM) across all units and calculate absolute revenue increase (current revenue - previous month revenue), then display top 5-10 products with biggest absolute increase in order.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

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

yoy_revenue_decrease_products_prompt = '''
Task: Find products that experienced revenue decline (Year on Year / YoY) across all units and calculate absolute revenue decrease (current revenue - previous year revenue same period), then display top 5-10 products with biggest absolute decrease in order.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

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

yoy_revenue_increase_products_prompt = '''
Task: Find products that experienced revenue increase (Year on Year / YoY) across all units and calculate absolute revenue increase (current revenue - previous year revenue same period), then display top 5-10 products with biggest absolute increase in order.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

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

unit_revenue_mom_decline_cause_prompt = '''
Task: Find the cause for MoM revenue decline for a specific unit by querying for revenue products with negative MoM growth and displaying top 5-10 products with the biggest differences (decrease) with their percentages.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

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

top_revenue_contributing_products_prompt = '''
Task: Find products that contribute the most to revenue for CFU WIB by analyzing actual values and their percentages against the total, displaying top 10 products with highest revenue contribution.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

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

revenue_underachievement_products_prompt = '''
Task: Find products that contribute most to revenue underachievement for CFU WIB by calculating the shortfall (target - actual revenue) and showing the achievement percentage, displaying top 10 products with largest shortfalls.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

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
    AND ach_mtd < 100 -- Only underachieving products
GROUP BY period, div, l3, l4
ORDER BY (SUM(target_mtd) - SUM(real_mtd)) DESC -- DESC for largest shortfalls
LIMIT 10;
'''

revenue_growth_comparison_prompt = '''
Task: Show Month-over-Month (MoM) and Year-over-Year (YoY) revenue growth comparison for CFU WIB and its individual units, including identifying products that contribute to growth or decline.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

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

revenue_surge_products_year_prompt = '''
Task: Find products that experienced revenue surge (Month on Month / MOM) in a specific year compared to their previous months' average, identifying products with MOM > 10% above the 3-month average.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

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