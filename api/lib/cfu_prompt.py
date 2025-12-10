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
- Order by importance: REVENUE, COE, EBITDA, EBIT, EBT, NET INCOME.

Reference pattern 1 (Specific Metric - e.g. Revenue):
SELECT
    div AS unit_name,
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
GROUP BY div, l2, l3, l4;

Reference pattern 2 (Full Performance Summary):
SELECT
    div AS unit_name,
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
GROUP BY div, l2, l3, l4
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
    period,
    div AS unit_name,
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
    period,
    div AS unit_name,
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

Reference pattern (Underperforming products):
SELECT
    div AS unit_name,
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
GROUP BY div, l2, l3, l4
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

Reference pattern (Revenue success factors):
SELECT
    div AS unit_name,
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
GROUP BY div, l3, l4
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

Reference pattern (Revenue failure factors):
SELECT
    div AS unit_name,
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
GROUP BY div, l3, l4
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

Reference pattern (EBITDA success factors):
SELECT
    div AS unit_name,
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
GROUP BY div, l2, l3
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

Reference pattern (EBITDA failure factors):
SELECT
    div AS unit_name,
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
GROUP BY div, l2, l3
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

Reference pattern (Net Income success factors):
SELECT
    div AS unit_name,
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
GROUP BY div, l2, l3
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

Reference pattern (Net Income failure factors):
SELECT
    div AS unit_name,
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
GROUP BY div, l2, l3
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

Reference pattern (Negative growth products):
SELECT
    div AS unit_name,
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
GROUP BY div, l2, l3, l4
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

Reference pattern (EBITDA negative growth analysis):
SELECT
    div AS unit_name,
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
GROUP BY div, l2, l3
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

Reference pattern (External Revenue breakdown):
SELECT
    div AS unit_name,
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
GROUP BY div, l3, l4
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
    period,
    div AS unit_name,
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