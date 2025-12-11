# lib/cfu_prompt.py

monthly_performance_prompt = '''
Task: Generate a SQLite query to get performance data for a specific division and period. Filter metrics based on user request.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Valid Values Reference:
- DIV: ['DMT', 'DWS', 'TELIN', 'TIF', 'TSAT'] (Note: 'CFU WIB' is the aggregate of these 5. 'WINS' is NOT supported.)
- PERIOD: [202401, ..., 202507] (integers)
- L2 Key Metrics: ['REVENUE', 'COE', 'EBITDA', 'EBIT', 'EBT', 'NET INCOME']
- HIERARCHY REFERENCE (L2 -> L3 -> L4 -> L5 -> L6):
  L2 (Top Hierarchy): [COE, EBIT, EBITDA, EBT, NET INCOME, REVENUE]
  L3: [Connectivity, Tax, -, NCI, Non Operating Cost, Other Income (Expenses), Non Operating Rev & Cost, Other Income (Expenses)/Expense, Depreciation & Amortization, Operation & Maintenance, General & Administration, Interconnection, Direct Cost, Administrasi dan Umum, Karyawan, Marketing, Penyisihan Piutang, Indirect Cost, Digital Services, Legacy, Digital Platform, Managed Service, Office cost, Personel, Digital, G&A, Total Cost of Sales, O&M, Personnel, Digital Service]
  L4: [-, FOREX GAIN (LOSS), INTEREST EXPENSE, INTEREST INCOME, NET INCOME FROM SUBSIDIARIES, OTHER NON OPERATING REVENUE, Kerjasama, General, Domestik, Inter CFU, OM, OTHER NON OPERATING EXPENSE, General Cost, IT Cost, Marketing, Personnel Cost, Manage Service, IAT, NeuTRAFIX, Other Digital, MNO - L, MVNO - L, Managed Service, Wholesale Voice, MS Contract, O&M, MVNO - C, Network International, A2P SMS, CDN & Security, Data Center, Business Service Provider, CPaaS, Administrasi, Intra CFU, External, Cost of Sales Data, Lainnya, Cost of Sales Digital Business, Others Legacy, MNO - C, Cost of Sales Data Center, Cost of Sales MVNO, Cost of Sales Voice, Digital Business (IPX, WiFi Roaming), Cosf of Sales MNO, Project Cost, Reseller Cost, International, Cindera Mata, Data, New Produk, Value Added Service, Other Service, Hubbing, Interconnection, Transponder, Data Center & Content Platform, Other Platform, Multimedia, Network, New Account BODP, IT & Billing Support System, Other Platform, Service, & New Business, Digital Messaging, WSA & TSA-1, Wi-Fi Broadband, PD, Peralatan, Managed Service (CNOP), PD Dalam Negeri, New Products, Customer Education, PD Luar Negeri, Cost of Sales Managed Services, Go Presence]
  L5: [-, Beban Rapat Direksi, Outgoing Domestik, MNO, MVNO SMS, MVNO VAS, MVNO Voice, Agent Fee, PKSO, Digital Retail, MVNO Data, MVNO Discount, Managed Service, CDN Infrastructure, IPLC, IPTX, IPVPN, Other Data, Bank, IP Transit, Other Digital, ITKP, Colocation and Power, Sale of Equipment and Solution, A2P SMS, Business Service Provider, CDN & Security, CPaaS, IPX, NeuTRAFIX, MVNO Fee, Hubbing, Incoming, Outgoing, IP VPN, IPLC/IEPL, Outgoing International, Alat Tulis, Beban PD Dalam Negeri Direksi, Whitelabel FTTX, Metronexia, Premium, Call Center, Content Speedy, P2P International, Incoming International, Transit Domestic, Satellite, CDN, Anti virus, Others, SL Digital, Transit Domestik, WiFi Roaming, Calling Card, New Legacy Account (FMC), IaaS, SDWAN, Smart Device, Pend New Business, Game Online, ITFS, Signalling, Incoming Domestic, CNDC, A2P Domestic, A2P International, International Hub, Metro-E, Sarpen, Fixed Broadband Core Service (TSA-1), Network & Lastmile Service (WSA), Wi-Fi Broadband, Managed Service (CNOP), BPPU, Pencairan Piutang, Copy Dokumen, Bitstream, Outsourcing Umum, Vula, Buku/Dokumentasi, Materai dan Perangko, Pengiriman Dokumen, Outsourcing Operasi, PD Dalam Negeri, Rapat, Reseller, Outsourcing Technical & Management, Diklat & Customer Edu, Go Presence]

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- CFU WIB HANDLING (CRITICAL):
    - IF user says "CFU WIB" AND ("detail", "breakdown", "per unit", "per div") -> SELECT div AS unit_name ... GROUP BY div, l2, l3, l4. (Must show individual divisions).
    - IF user says "CFU WIB" ONLY -> SELECT 'CFU WIB' AS unit_name ... GROUP BY l2, l3, l4. (Must aggregate all divisions, do NOT group by div).
- METRIC FILTERING (CRITICAL):
    - IF user mentions specific metrics (e.g., "Revenue", "COE"), YOU MUST FILTER `l2` to ONLY those metrics.
    - Example: `AND l2 = 'REVENUE'` or `AND l2 IN ('REVENUE', 'COE')`.
    - DO NOT include other metrics even if the user says "performance" (e.g. "performance revenue" -> ONLY Revenue).
    - ONLY include all 6 metrics if user asks for "performance", "summary", or generic "data" WITHOUT specifying any metric name.
- IF user asks for "WINS", return a message that it is not supported.
- Use latest available period if not specified (use subquery: SELECT MAX(period) FROM cfu_performance_data).
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
    div AS unit_name,
    period,
    l2 AS metric_type,
    l3 AS category_l3,
    l4 AS category_l4,
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
    div AS unit_name,
    period,
    l2 AS metric_type,
    l3 AS category_l3,
    l4 AS category_l4,
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

trend_analysis_prompt = '''
Task: Generate a SQLite query to show trends for Revenue/COE/EBITDA/EBIT/EBT/NET INCOME over multiple periods.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- CFU WIB HANDLING (CRITICAL):
    - IF user says "CFU WIB" AND ("detail", "breakdown", "per unit", "per div") -> SELECT div AS unit_name ... GROUP BY period, div, l2, l3, l4.
    - IF user says "CFU WIB" ONLY -> SELECT 'CFU WIB' AS unit_name ... GROUP BY period, l2, l3, l4.
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
    div AS unit_name,
    period,
    l2 AS metric_type,
    l3 AS category_l3,
    l4 AS category_l4,
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

comparison_trend_prompt = '''
Task: Generate a SQLite query to compare actual, target, and prev year values over time periods.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- CFU WIB HANDLING (CRITICAL):
    - IF user says "CFU WIB" AND ("detail", "breakdown", "per unit", "per div") -> SELECT div AS unit_name ... GROUP BY period, div, l2, l3, l4.
    - IF user says "CFU WIB" ONLY -> SELECT 'CFU WIB' AS unit_name ... GROUP BY period, l2, l3, l4.
- Include actual, target, and previous year data.
- COLUMN NAMES (CRITICAL):
    - DO NOT alias `real_mtd` as `actual`. Keep it `real_mtd`.
    - DO NOT alias `target_mtd` as `target`. Keep it `target_mtd`.
    - DO NOT alias `prev_year` or `prev_month`. Keep original column names.
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
    div AS unit_name,
    period,
    l2 AS metric_type,
    l3 AS category_l3,
    l4 AS category_l4,
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

underperforming_products_prompt = '''
Task: Find products/categories with achievement < 100% for a specific division.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- IF user asks for "CFU WIB", do NOT filter by `div`.
- Filter for underperforming: ach_ytd < 100.
- Use latest period (use subquery: SELECT MAX(period) FROM cfu_performance_data) unless specified.
- Show detailed breakdown using L3/L4 levels (Filter l5 = '-' to get L4 items).
- Limit results to top underperformers.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (Underperforming products):
SELECT
    div AS unit_name,
    period,
    l2 AS main_category,
    l3 AS product_category,
    l4 AS product_detail,
    SUM(real_ytd) AS real_ytd,
    ROUND(AVG(ach_ytd), 2) AS achievement_ytd,
    ROUND(AVG(yoy), 2) AS growth_yoy
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN'
    AND ach_ytd < 100
    AND l5 = '-' -- Get L4 items
GROUP BY period, div, l2, l3, l4
ORDER BY achievement_ytd ASC
LIMIT 20;
'''

revenue_success_analysis_prompt = '''
Task: Find revenue products with achievement > 100% and largest positive gaps for a division.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Filter for: l2 = 'REVENUE' AND ach_ytd > 100.
- Calculate positive gap: actual - target.
- Order by largest gaps first.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (Revenue success factors):
SELECT
    div AS unit_name,
    period,
    l3 AS product_category,
    l4 AS product_detail,
    ROUND(AVG(ach_ytd), 2) AS achievement_ytd,
    SUM(real_ytd) AS real_ytd,
    ROUND(AVG(yoy), 2) AS growth_yoy
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN'
    AND l2 = 'REVENUE' AND ach_ytd > 100
    AND l5 = '-' -- Get L4 items
GROUP BY period, div, l3, l4
ORDER BY (SUM(real_ytd) - SUM(target_ytd)) DESC
LIMIT 15;
'''

revenue_failure_analysis_prompt = '''
Task: Find revenue products with achievement < 100% and largest negative gaps for a division.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Filter for: l2 = 'REVENUE' AND ach_ytd < 100.
- Calculate negative gap: target - actual (shortfall).
- Order by largest shortfalls first.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (Revenue failure factors):
SELECT
    div AS unit_name,
    period,
    l3 AS product_category,
    l4 AS product_detail,
    ROUND(AVG(ach_ytd), 2) AS achievement_ytd,
    SUM(real_ytd) AS real_ytd,
    ROUND(AVG(yoy), 2) AS growth_yoy
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN'
    AND l2 = 'REVENUE' AND ach_ytd < 100
    AND l5 = '-' -- Get L4 items
GROUP BY period, div, l3, l4
ORDER BY (SUM(target_ytd) - SUM(real_ytd)) DESC
LIMIT 15;
'''

ebitda_success_analysis_prompt = '''
Task: Analyze why EBITDA achieved target by examining Revenue success and COE underperformance.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Check Revenue products with achievement > 100%.
- Check COE categories with achievement < 100% (cost savings).
- EBITDA = Revenue - COE, so high revenue + low COE = good EBITDA.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (EBITDA success factors):
SELECT
    div AS unit_name,
    period,
    l2 AS component_type,
    l3 AS category,
    ROUND(AVG(ach_ytd), 2) AS achievement_ytd,
    SUM(real_ytd) - SUM(target_ytd) AS gap_mtd,
    CASE
        WHEN l2 = 'REVENUE' AND AVG(ach_ytd) > 100 THEN 'Revenue Driver'
        WHEN l2 = 'COE' AND AVG(ach_ytd) < 100 THEN 'Cost Savings'
        ELSE 'Other Factor'
    END AS ebitda_impact
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN'
    AND l2 IN ('REVENUE', 'COE')
    AND ((l2 = 'REVENUE' AND ach_ytd > 100)
         OR (l2 = 'COE' AND ach_ytd < 100))
    AND l4 = '-' -- Get L3 items
GROUP BY period, div, l2, l3
ORDER BY gap_mtd DESC
LIMIT 15;
'''

ebitda_failure_analysis_prompt = '''
Task: Analyze why EBITDA failed to achieve target by examining Revenue shortfalls and COE overruns.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Check Revenue products with achievement < 100% (revenue shortfall).
- Check COE categories with achievement > 100% (cost overrun).
- Focus on largest negative impacts.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (EBITDA failure factors):
SELECT
    div AS unit_name,
    period,
    l2 AS component_type,
    l3 AS category,
    ROUND(AVG(ach_ytd), 2) AS achievement_ytd,
    SUM(real_ytd) - SUM(target_ytd) AS negative_impact,
    CASE
        WHEN l2 = 'REVENUE' AND AVG(ach_ytd) < 100 THEN 'Revenue Shortfall'
        WHEN l2 = 'COE' AND AVG(ach_ytd) > 100 THEN 'Cost Overrun'
        ELSE 'Other Factor'
    END AS ebitda_drag
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN'
    AND l2 IN ('REVENUE', 'COE')
    AND ((l2 = 'REVENUE' AND ach_ytd < 100)
         OR (l2 = 'COE' AND ach_ytd > 100))
    AND l4 = '-' -- Get L3 items
GROUP BY period, div, l2, l3
ORDER BY negative_impact DESC
LIMIT 15;
'''

netincome_success_analysis_prompt = '''
Task: Analyze Net Income success by examining EBITDA and below-EBITDA factors.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Check EBITDA achievement.
- Look for Depreciation/Amortization underperformance (cost savings).
- Look for Other Income overperformance.
- Use L3 level for detailed analysis.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (Net Income success factors):
SELECT
    div AS unit_name,
    period,
    l2 AS metric_type,
    l3 AS component,
    ROUND(AVG(ach_ytd), 2) AS achievement_ytd,
    SUM(real_ytd) - SUM(target_ytd) AS contribution,
    CASE
        WHEN l2 = 'EBITDA' AND AVG(ach_mtd) > 100 THEN 'Core Business Success'
        WHEN l3 LIKE '%Depreciation%' AND AVG(ach_mtd) < 100 THEN 'Depreciation Savings'
        WHEN l3 LIKE '%Amortization%' AND AVG(ach_mtd) < 100 THEN 'Amortization Savings'
        WHEN l3 LIKE '%Other Income%' AND AVG(ach_mtd) > 100 THEN 'Other Income Boost'
        ELSE 'Other Factor'
    END AS netincome_driver
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN'
    AND (l2 = 'EBITDA' OR l3 LIKE '%Depreciation%' OR l3 LIKE '%Amortization%'
         OR l3 LIKE '%Other Income%')
    AND l4 = '-' -- Get L3 items
GROUP BY period, div, l2, l3
ORDER BY contribution DESC
LIMIT 15;
'''

netincome_failure_analysis_prompt = '''
Task: Analyze Net Income failure by examining EBITDA and below-EBITDA negative factors.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Check EBITDA underperformance.
- Look for Depreciation/Amortization overruns.
- Look for Other Income shortfalls.
- Focus on largest negative impacts.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (Net Income failure factors):
SELECT
    div AS unit_name,
    period,
    l2 AS metric_type,
    l3 AS component,
    ROUND(AVG(ach_ytd), 2) AS achievement_ytd,
    SUM(real_ytd) - SUM(target_ytd) AS negative_impact,
    CASE
        WHEN l2 = 'EBITDA' AND AVG(ach_mtd) < 100 THEN 'Core Business Issues'
        WHEN l3 LIKE '%Depreciation%' AND AVG(ach_mtd) > 100 THEN 'Higher Depreciation'
        WHEN l3 LIKE '%Amortization%' AND AVG(ach_mtd) > 100 THEN 'Higher Amortization'
        WHEN l3 LIKE '%Other Income%' AND AVG(ach_mtd) < 100 THEN 'Other Income Shortfall'
        ELSE 'Other Factor'
    END AS netincome_drag
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN'
    AND (l2 = 'EBITDA' OR l3 LIKE '%Depreciation%' OR l3 LIKE '%Amortization%'
         OR l3 LIKE '%Other Income%')
    AND l4 = '-' -- Get L3 items
GROUP BY period, div, l2, l3
ORDER BY negative_impact DESC
LIMIT 15;
'''

negative_growth_products_prompt = '''
Task: Find products with negative growth (MoM < 0%) for a specific division.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Filter for: mom < 0.
- Use latest period unless specified.
- Show product details with L3/L4 breakdown.
- Include YTD metrics for context.
- Order by worst growth first.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (Negative growth products):
SELECT
    div AS unit_name,
    period,
    l2 AS category,
    l3 AS product_category,
    l4 AS product_detail,
    ROUND(AVG(mom), 2) AS growth_mom_pct,
    ROUND(AVG(yoy), 2) AS growth_yoy_pct,
    SUM(real_mtd) AS actual_mtd,
    SUM(real_ytd) AS actual_ytd
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN'
    AND mom < 0
    AND l5 = '-' -- Get L4 items
GROUP BY period, div, l2, l3, l4
ORDER BY growth_mom_pct ASC
LIMIT 20;
'''

ebitda_negative_growth_prompt = '''
Task: Analyze why EBITDA has negative growth by checking Revenue and COE growth patterns.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Check Revenue products with negative growth (mom < 0).
- Check COE categories with positive growth (mom > 0) - increasing costs.
- Focus on significant contributors.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (EBITDA negative growth analysis):
SELECT
    div AS unit_name,
    period,
    l2 AS component_type,
    l3 AS category,
    ROUND(AVG(mom), 2) AS growth_mom_pct,
    SUM(real_mtd) AS actual_mtd,
    CASE
        WHEN l2 = 'REVENUE' AND AVG(mom) < 0 THEN 'Revenue Declining'
        WHEN l2 = 'COE' AND AVG(mom) > 0 THEN 'Costs Increasing'
        ELSE 'Other Factor'
    END AS ebitda_growth_impact
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
    AND div = 'TELIN'
    AND l2 IN ('REVENUE', 'COE')
    AND ((l2 = 'REVENUE' AND mom < 0) OR (l2 = 'COE' AND mom > 0))
    AND l4 = '-' -- Get L3 items
GROUP BY period, div, l2, l3
ORDER BY ABS(growth_mom_pct) DESC
LIMIT 15;
'''

external_revenue_prompt = '''
Task: Generate a SQLite query to calculate External Revenue performance (actual, achievement, growth) for a given division and period.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Focus on External Revenue only → check L3 or L4 containing "External".
- Show detailed breakdown by L3 and L4 to identify specific external revenue streams.
- Must include: actual MTD, actual YTD, achievement MTD, achievement YTD, growth MoM, growth YoY.
- Order by actual MTD descending.
- ALWAYS include `period` in the SELECT clause.

Reference pattern (External Revenue breakdown):
SELECT
    div AS unit_name,
    period,
    l3 AS category_l3,
    l4 AS category_l4,
    SUM(real_mtd) AS actual_mtd,
    SUM(real_ytd) AS actual_ytd,
    ROUND(AVG(ach_mtd), 2) AS achievement_mtd_pct,
    ROUND(AVG(ach_ytd), 2) AS achievement_ytd_pct,
    ROUND(AVG(mom), 2) AS growth_mom_pct,
    ROUND(AVG(yoy), 2) AS growth_yoy_pct
FROM cfu_performance_data
WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
  AND div = 'TELIN'
  AND (l3 LIKE '%External%' OR l4 LIKE '%External%')
  AND l5 = '-' -- Get L4 items
GROUP BY period, div, l3, l4
ORDER BY actual_mtd DESC;
'''

external_revenue_trend_prompt = '''
Task: Show External Revenue trend comparison (actual, target, prev year) over multiple periods.

CRITICAL USER MAPPING: When user says "unit", they mean "div" (division) in database!

Rules:
- ALWAYS translate user's "unit" to "div" in WHERE clause.
- Look for External revenue categories (L3 or L4).
- Group by period for trend analysis.
- Include actual, target, and previous year data.
- Order chronologically.

Reference pattern (External Revenue trend):
SELECT
    div AS unit_name,
    period,
    SUM(real_mtd) AS actual_mtd,
    SUM(target_mtd) AS target_mtd,
    SUM(prev_month) AS prev_year_mtd
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

- Determine which type of query based on user input and generate appropriate SQL:
  - For CFU WIB MoM decline check: Query total revenue for CFU WIB and identify declining units
  - For MoM revenue decrease by product: Query l2 = 'REVENUE' AND mom < 0, order by biggest absolute decrease
  - For MoM revenue increase by product: Query l2 = 'REVENUE' AND mom > 0, order by biggest absolute increase
  - For YoY revenue decrease by product: Query l2 = 'REVENUE' AND yoy < 0, order by biggest absolute decrease
  - For YoY revenue increase by product: Query l2 = 'REVENUE' AND yoy > 0, order by biggest absolute increase
  - For unit-specific MoM decline cause: Filter for specific unit, l2 = 'REVENUE' AND mom < 0, order by biggest absolute decrease

- CFU WIB HANDLING (CRITICAL):
  - For total CFU WIB: Include all divisions (DMT, DWS, TELIN, TIF, TSAT) in the aggregation
  - For specific units: Filter for that specific division

- HIERARCHY LOGIC (Crucial):
  - L2 Aggregate: Filter `l3 = '-'`.
  - L3/L4 detailed products: Filter `l5 = '-'` to get L4 items

- Always include both absolute change and percentage change in results
- Calculate absolute change as: real_mtd - prev_month (for MoM) or real_mtd - prev_year (for YoY)
- Calculate percentage change as: ((current - previous) / previous) * 100 (with safety check for division by zero)
- ORDER BY appropriate metric depending on query type:
  - For decrease analysis: ORDER BY (SUM(real_mtd) - SUM(prev_month)) ASC or (SUM(real_mtd) - SUM(prev_year)) ASC
  - For increase analysis: ORDER BY (SUM(real_mtd) - SUM(prev_month)) DESC or (SUM(real_mtd) - SUM(prev_year)) DESC
- LIMIT to 5-10 results initially (LIMIT 10), allow for more data to be displayed if user requests
- ALWAYS include `period` in the SELECT clause

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
        ROUND(AVG(mom), 2) AS mom_growth_pct
    FROM cfu_performance_data
    WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
        AND l2 = 'REVENUE'
        AND l3 = '-'
        AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
    GROUP BY period
),
unit_contributions AS (
    SELECT
        div AS unit_name,
        period,
        SUM(real_mtd) AS actual_revenue,
        SUM(prev_month) AS prev_month_revenue,
        SUM(real_mtd) - SUM(prev_month) AS absolute_change,
        ROUND(AVG(mom), 2) AS mom_growth_pct
    FROM cfu_performance_data
    WHERE period = (SELECT MAX(period) FROM cfu_performance_data)
        AND l2 = 'REVENUE'
        AND l3 = '-'
        AND div IN ('DMT', 'DWS', 'TELIN', 'TIF', 'TSAT')
        AND AVG(mom) < 0  -- Only return units with negative MoM growth (contribute to decline)
    GROUP BY period, div
)
SELECT * FROM cfu_wib_total
UNION ALL
SELECT * FROM unit_contributions
ORDER BY unit_name;

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
'''