# lib/cfu_prompt.py

monthly_performance_prompt = '''
Task: Generate a SQLite query to get comprehensive performance data (Revenue, COE, EBITDA, Net Income) with achievement and growth for a specific division and period.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Valid Values Reference:
- DIV: ['CFU WIB', 'DMT', 'DWS', 'TELIN', 'TIF', 'TSAT', 'WINS']
- PERIOD: [202501, 202502, 202503, 202504, 202505, 202506, 202507] (integers)
- L2 Key Metrics: ['REVENUE', 'COE', 'EBITDA', 'NET INCOME']

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause
- Use latest available period if not specified (202507)
- Always filter: week_1_0_5___fm = 'FM'
- Include both MTD and YTD for comprehensive view
- Focus on L2 level for main performance metrics
- Order by importance: REVENUE, COE, EBITDA, NET INCOME

Reference pattern (Performance summary for specific division):
SELECT
    div AS unit_name,
    l2 AS metric_type,
    SUM(month_to_date_actual) AS actual_mtd,
    SUM(year_to_date_actual) AS actual_ytd,
    ROUND(AVG(month_to_date_ach), 2) AS achievement_pct,
    ROUND(AVG(gmom), 2) AS growth_mom_pct
FROM cfu_performance_data
WHERE period = 202507 AND week_1_0_5___fm = 'FM' AND div = 'CFU WIB'
    AND l2 IN ('REVENUE', 'COE', 'EBITDA', 'NET INCOME')
GROUP BY div, l2
ORDER BY CASE l2 
    WHEN 'REVENUE' THEN 1 
    WHEN 'COE' THEN 2 
    WHEN 'EBITDA' THEN 3 
    WHEN 'NET INCOME' THEN 4 
    ELSE 5 END;
'''

trend_analysis_prompt = '''
Task: Generate a SQLite query to show trends for Revenue/COE/EBITDA/NET INCOME over multiple periods.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause
- For period ranges, use BETWEEN with integer periods
- Group by period and division for trend analysis
- Include actual values for trend visualization
- Order chronologically by period

Reference pattern (Monthly trend for specific division):
SELECT
    period,
    div AS unit_name,
    l2 AS metric_type,
    SUM(month_to_date_actual) AS actual_mtd
FROM cfu_performance_data
WHERE period BETWEEN 202501 AND 202507 AND week_1_0_5___fm = 'FM'
    AND div = 'CFU WIB' AND l2 IN ('REVENUE', 'COE', 'EBITDA', 'NET INCOME')
GROUP BY period, div, l2
ORDER BY period ASC, CASE l2 
    WHEN 'REVENUE' THEN 1 WHEN 'COE' THEN 2 
    WHEN 'EBITDA' THEN 3 WHEN 'NET INCOME' THEN 4 ELSE 5 END;
'''

comparison_trend_prompt = '''
Task: Generate a SQLite query to compare actual, target, and prev year values over time periods.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause
- Include actual, target, and previous year data
- Group by period for time series comparison
- Use month_to_date columns for MTD analysis

Reference pattern (Comparison trend for division):
SELECT
    period,
    div AS unit_name,
    l2 AS metric_type,
    SUM(month_to_date_actual) AS actual_mtd,
    SUM(month_to_date_target) AS target_mtd,
    SUM(month_to_date_prev_month) AS prev_year_mtd
FROM cfu_performance_data
WHERE period BETWEEN 202501 AND 202507 AND week_1_0_5___fm = 'FM'
    AND div = 'CFU WIB' AND l2 IN ('REVENUE', 'COE', 'EBITDA', 'NET INCOME')
GROUP BY period, div, l2
ORDER BY period ASC;
'''

underperforming_products_prompt = '''
Task: Find products/categories with achievement < 100% for a specific division.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause
- Filter for underperforming: month_to_date_ach < 100
- Use latest period (202507) unless specified
- Show detailed breakdown using L3/L4 levels
- Limit results to top underperformers

Reference pattern (Underperforming products):
SELECT
    div AS unit_name,
    l2 AS main_category,
    l3 AS product_category, 
    l4 AS product_detail,
    ROUND(AVG(month_to_date_ach), 2) AS achievement_pct,
    SUM(month_to_date_target) - SUM(month_to_date_actual) AS shortfall_mtd
FROM cfu_performance_data
WHERE period = 202507 AND week_1_0_5___fm = 'FM' AND div = 'CFU WIB'
    AND month_to_date_ach < 100 
GROUP BY div, l2, l3, l4
ORDER BY achievement_pct ASC
LIMIT 20;
'''

revenue_success_analysis_prompt = '''
Task: Find revenue products with achievement > 100% and largest positive gaps for a division.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause
- Filter for: l2 = 'REVENUE' AND month_to_date_ach > 100
- Calculate positive gap: actual - target
- Order by largest gaps first
- Limit to significant contributors

Reference pattern (Revenue success factors):
SELECT
    div AS unit_name,
    l3 AS product_category,
    l4 AS product_detail,
    ROUND(AVG(month_to_date_ach), 2) AS achievement_pct,
    SUM(month_to_date_actual) - SUM(month_to_date_target) AS surplus_mtd,
    SUM(month_to_date_actual) AS actual_mtd
FROM cfu_performance_data  
WHERE period = 202507 AND week_1_0_5___fm = 'FM' AND div = 'CFU WIB'
    AND l2 = 'REVENUE' AND month_to_date_ach > 100
GROUP BY div, l3, l4
ORDER BY surplus_mtd DESC
LIMIT 15;
'''

revenue_failure_analysis_prompt = '''
Task: Find revenue products with achievement < 100% and largest negative gaps for a division.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause  
- Filter for: l2 = 'REVENUE' AND month_to_date_ach < 100
- Calculate negative gap: target - actual (shortfall)
- Order by largest shortfalls first

Reference pattern (Revenue failure factors):
SELECT
    div AS unit_name,
    l3 AS product_category,
    l4 AS product_detail,
    ROUND(AVG(month_to_date_ach), 2) AS achievement_pct,
    SUM(month_to_date_target) - SUM(month_to_date_actual) AS shortfall_mtd,
    SUM(month_to_date_actual) AS actual_mtd
FROM cfu_performance_data
WHERE period = 202507 AND week_1_0_5___fm = 'FM' AND div = 'CFU WIB'
    AND l2 = 'REVENUE' AND month_to_date_ach < 100
GROUP BY div, l3, l4
ORDER BY shortfall_mtd DESC
LIMIT 15;
'''

ebitda_success_analysis_prompt = '''
Task: Analyze why EBITDA achieved target by examining Revenue success and COE underperformance.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause
- Check Revenue products with achievement > 100%
- Check COE categories with achievement < 100% (cost savings)
- EBITDA = Revenue - COE, so high revenue + low COE = good EBITDA

Reference pattern (EBITDA success factors):
SELECT
    div AS unit_name,
    l2 AS component_type,
    l3 AS category,
    ROUND(AVG(month_to_date_ach), 2) AS achievement_pct,
    SUM(month_to_date_actual) - SUM(month_to_date_target) AS gap_mtd,
    CASE 
        WHEN l2 = 'REVENUE' AND AVG(month_to_date_ach) > 100 THEN 'Revenue Driver'
        WHEN l2 = 'COE' AND AVG(month_to_date_ach) < 100 THEN 'Cost Savings'
        ELSE 'Other Factor'
    END AS ebitda_impact
FROM cfu_performance_data
WHERE period = 202507 AND week_1_0_5___fm = 'FM' AND div = 'CFU WIB'
    AND l2 IN ('REVENUE', 'COE')
    AND ((l2 = 'REVENUE' AND month_to_date_ach > 100) 
         OR (l2 = 'COE' AND month_to_date_ach < 100))
GROUP BY div, l2, l3
ORDER BY gap_mtd DESC
LIMIT 15;
'''

ebitda_failure_analysis_prompt = '''
Task: Analyze why EBITDA failed to achieve target by examining Revenue shortfalls and COE overruns.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause
- Check Revenue products with achievement < 100% (revenue shortfall)
- Check COE categories with achievement > 100% (cost overrun)
- Focus on largest negative impacts

Reference pattern (EBITDA failure factors):
SELECT
    div AS unit_name,
    l2 AS component_type,
    l3 AS category,
    ROUND(AVG(month_to_date_ach), 2) AS achievement_pct,
    SUM(month_to_date_target) - SUM(month_to_date_actual) AS negative_impact,
    CASE 
        WHEN l2 = 'REVENUE' AND AVG(month_to_date_ach) < 100 THEN 'Revenue Shortfall'
        WHEN l2 = 'COE' AND AVG(month_to_date_ach) > 100 THEN 'Cost Overrun'
        ELSE 'Other Factor'
    END AS ebitda_drag
FROM cfu_performance_data
WHERE period = 202507 AND week_1_0_5___fm = 'FM' AND div = 'CFU WIB'
    AND l2 IN ('REVENUE', 'COE')
    AND ((l2 = 'REVENUE' AND month_to_date_ach < 100) 
         OR (l2 = 'COE' AND month_to_date_ach > 100))
GROUP BY div, l2, l3
ORDER BY negative_impact DESC
LIMIT 15;
'''

netincome_success_analysis_prompt = '''
Task: Analyze Net Income success by examining EBITDA and below-EBITDA factors.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause
- Check EBITDA achievement
- Look for Depreciation/Amortization underperformance (cost savings)
- Look for Other Income overperformance
- Use L3 level for detailed analysis

Reference pattern (Net Income success factors):
SELECT
    div AS unit_name,
    l2 AS metric_type,
    l3 AS component,
    ROUND(AVG(month_to_date_ach), 2) AS achievement_pct,
    SUM(month_to_date_actual) - SUM(month_to_date_target) AS contribution,
    CASE 
        WHEN l2 = 'EBITDA' AND AVG(month_to_date_ach) > 100 THEN 'Core Business Success'
        WHEN l3 LIKE '%Depreciation%' AND AVG(month_to_date_ach) < 100 THEN 'Depreciation Savings'
        WHEN l3 LIKE '%Amortization%' AND AVG(month_to_date_ach) < 100 THEN 'Amortization Savings'
        WHEN l3 LIKE '%Other Income%' AND AVG(month_to_date_ach) > 100 THEN 'Other Income Boost'
        ELSE 'Other Factor'
    END AS netincome_driver
FROM cfu_performance_data
WHERE period = 202507 AND week_1_0_5___fm = 'FM' AND div = 'CFU WIB'
    AND (l2 = 'EBITDA' OR l3 LIKE '%Depreciation%' OR l3 LIKE '%Amortization%' 
         OR l3 LIKE '%Other Income%')
GROUP BY div, l2, l3
ORDER BY contribution DESC
LIMIT 15;
'''

netincome_failure_analysis_prompt = '''
Task: Analyze Net Income failure by examining EBITDA and below-EBITDA negative factors.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause
- Check EBITDA underperformance
- Look for Depreciation/Amortization overruns
- Look for Other Income shortfalls
- Focus on largest negative impacts

Reference pattern (Net Income failure factors):
SELECT
    div AS unit_name,
    l2 AS metric_type,
    l3 AS component,
    ROUND(AVG(month_to_date_ach), 2) AS achievement_pct,
    SUM(month_to_date_target) - SUM(month_to_date_actual) AS negative_impact,
    CASE 
        WHEN l2 = 'EBITDA' AND AVG(month_to_date_ach) < 100 THEN 'Core Business Issues'
        WHEN l3 LIKE '%Depreciation%' AND AVG(month_to_date_ach) > 100 THEN 'Higher Depreciation'
        WHEN l3 LIKE '%Amortization%' AND AVG(month_to_date_ach) > 100 THEN 'Higher Amortization'
        WHEN l3 LIKE '%Other Income%' AND AVG(month_to_date_ach) < 100 THEN 'Other Income Shortfall'
        ELSE 'Other Factor'
    END AS netincome_drag
FROM cfu_performance_data
WHERE period = 202507 AND week_1_0_5___fm = 'FM' AND div = 'CFU WIB'
    AND (l2 = 'EBITDA' OR l3 LIKE '%Depreciation%' OR l3 LIKE '%Amortization%' 
         OR l3 LIKE '%Other Income%')
GROUP BY div, l2, l3
ORDER BY negative_impact DESC
LIMIT 15;
'''

negative_growth_products_prompt = '''
Task: Find products with negative growth (GMOM < 0%) for a specific division.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause
- Filter for: gmom < 0
- Use latest period unless specified
- Show product details with L3/L4 breakdown
- Order by worst growth first

Reference pattern (Negative growth products):
SELECT
    div AS unit_name,
    l2 AS category,
    l3 AS product_category,
    l4 AS product_detail,
    ROUND(AVG(gmom), 2) AS growth_mom_pct,
    SUM(month_to_date_actual) AS actual_mtd
FROM cfu_performance_data
WHERE period = 202507 AND week_1_0_5___fm = 'FM' AND div = 'CFU WIB'
    AND gmom < 0
GROUP BY div, l2, l3, l4
ORDER BY growth_mom_pct ASC
LIMIT 20;
'''

ebitda_negative_growth_prompt = '''
Task: Analyze why EBITDA has negative growth by checking Revenue and COE growth patterns.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause
- Check Revenue products with negative growth (gmom < 0)
- Check COE categories with positive growth (gmom > 0) - increasing costs
- Focus on significant contributors

Reference pattern (EBITDA negative growth analysis):
SELECT
    div AS unit_name,
    l2 AS component_type,
    l3 AS category,
    ROUND(AVG(gmom), 2) AS growth_mom_pct,
    SUM(month_to_date_actual) AS actual_mtd,
    CASE 
        WHEN l2 = 'REVENUE' AND AVG(gmom) < 0 THEN 'Revenue Declining'
        WHEN l2 = 'COE' AND AVG(gmom) > 0 THEN 'Costs Increasing'
        ELSE 'Other Factor'
    END AS ebitda_growth_impact
FROM cfu_performance_data
WHERE period = 202507 AND week_1_0_5___fm = 'FM' AND div = 'CFU WIB'
    AND l2 IN ('REVENUE', 'COE')
    AND ((l2 = 'REVENUE' AND gmom < 0) OR (l2 = 'COE' AND gmom > 0))
GROUP BY div, l2, l3
ORDER BY ABS(growth_mom_pct) DESC
LIMIT 15;
'''

external_revenue_prompt = '''
Task: Generate a SQLite query to calculate External Revenue performance (actual, achievement, growth) for a given division and period.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause
- Focus on External Revenue only → check L4, L5, or L6 containing "External"
- Aggregate at division-level (do not break down into subcategories like CNDC/CDN unless explicitly asked)
- Must include: actual MTD, actual YTD, achievement MTD, achievement YTD, growth MoM, growth YoY
- IMPORTANT: 
    * MTD = (actual of current month) - (actual of previous month)
    * If current month is January, then YTD = MTD
- Always filter week_1_0_5___fm = 'FM'

Reference pattern (External Revenue main summary):
WITH current_month AS (
    SELECT
        div,
        SUM(month_to_date_actual) AS actual_mtd,
        SUM(year_to_date_actual) AS actual_ytd,
        ROUND(AVG(month_to_date_ach), 2) AS achievement_mtd_pct,
        ROUND(AVG(year_to_date_ach), 2) AS achievement_ytd_pct,
        ROUND(AVG(gmom), 2) AS growth_mom_pct,
        ROUND(AVG(gyoy), 2) AS growth_yoy_pct
    FROM cfu_performance_data
    WHERE period = {period} 
      AND week_1_0_5___fm = 'FM'
      AND div = '{division}'
      AND (l0 LIKE '%REVENUE%' OR l2 = 'REVENUE')
      AND (l4 LIKE '%External%' OR l5 LIKE '%External%' OR l6 LIKE '%External%')
    GROUP BY div
),
prev_month AS (
    SELECT
        div,
        SUM(month_to_date_actual) AS prev_actual_mtd
    FROM cfu_performance_data
    WHERE period = {prev_period}
      AND week_1_0_5___fm = 'FM'
      AND div = '{division}'
      AND (l0 LIKE '%REVENUE%' OR l2 = 'REVENUE')
      AND (l4 LIKE '%External%' OR l5 LIKE '%External%' OR l6 LIKE '%External%')
    GROUP BY div
)
SELECT
    c.div AS unit_name,
    (c.actual_mtd - IFNULL(p.prev_actual_mtd, 0)) AS actual_mtd,
    c.actual_ytd,
    c.achievement_mtd_pct,
    c.achievement_ytd_pct,
    c.growth_mom_pct,
    c.growth_yoy_pct
FROM current_month c
LEFT JOIN prev_month p ON c.div = p.div;
'''

external_revenue_trend_prompt = '''
Task: Show External Revenue trend comparison (actual, target, prev year) over multiple periods.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause
- Look for External revenue categories
- Group by period for trend analysis
- Include actual, target, and previous year data
- Order chronologically

Reference pattern (External Revenue trend):
SELECT
    period,
    div AS unit_name,
    SUM(month_to_date_actual) AS actual_mtd,
    SUM(month_to_date_target) AS target_mtd,
    SUM(month_to_date_prev_month) AS prev_year_mtd
FROM cfu_performance_data
WHERE period BETWEEN 202501 AND 202507 AND week_1_0_5___fm = 'FM' 
    AND div = 'CFU WIB'
    AND (l0 LIKE '%REVENUE%' OR l2 = 'REVENUE')
    AND (l4 LIKE '%External%' OR l5 LIKE '%External%' OR l6 LIKE '%External%')
GROUP BY period, div
ORDER BY period ASC;
'''