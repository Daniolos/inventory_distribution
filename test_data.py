#!/usr/bin/env python3
"""Generate test Excel file with defined scenarios for verification"""

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows

# Define test scenarios
scenarios = [
    {
        "name": "S1: Stock full, all stores empty",
        "description": "Stock=5, all 0 → distributes 1 to each (max 5 stores)",
        "Номенклатура": "Test Product A",
        "Характеристика": "Size M",
        "125004 EKT-PC-Гринвич": 0,
        "125005 EKT-PC-Мега": 0,
        "125006 KZN-PC-Мега": 0,
        "125007 MSK-PC-Гагаринский": 0,
        "125008 MSK-PC-РИО Ленинский": 0,
        "125009 NNV-PC-Фантастика": 0,
        "125011 SPB-PC-Мега 2 Парнас": 0,
        "125839 - MSK-PC-Outlet Белая Дача": 0,
        "129877 MSK-PC-Мега 1 Теплый Стан": 0,
        "130143 MSK-PCM-Мега 2 Химки": 0,
        "150002 MSK-DV-Капитолий": 0,
        "Сток": 5,
        "Фото склад": 0,
        "expected_script1": "125007=1, 125008=1, 129877=1, 130143=1, 150002=1 (priority order)",
        "expected_script2": "No change (no store >2)",
    },
    {
        "name": "S2: Stock full, some stores already have",
        "description": "Stock=3, 125007 and 125008 already have 1 → only distribute to empty",
        "Номенклатура": "Test Product B",
        "Характеристика": "Size L",
        "125004 EKT-PC-Гринвич": 0,
        "125005 EKT-PC-Мега": 0,
        "125006 KZN-PC-Мега": 0,
        "125007 MSK-PC-Гагаринский": 1,
        "125008 MSK-PC-РИО Ленинский": 1,
        "125009 NNV-PC-Фантастика": 0,
        "125011 SPB-PC-Мега 2 Парнас": 0,
        "125839 - MSK-PC-Outlet Белая Дача": 0,
        "129877 MSK-PC-Мега 1 Теплый Стан": 0,
        "130143 MSK-PCM-Мега 2 Химки": 0,
        "150002 MSK-DV-Капитолий": 0,
        "Сток": 3,
        "Фото склад": 0,
        "expected_script1": "129877=1, 130143=1, 150002=1 (skips 125007, 125008)",
        "expected_script2": "No change",
    },
    {
        "name": "S3: Stock empty",
        "description": "Stock=0 → nothing happens",
        "Номенклатура": "Test Product C",
        "Характеристика": "Size S",
        "125004 EKT-PC-Гринвич": 0,
        "125005 EKT-PC-Мега": 0,
        "125006 KZN-PC-Мега": 0,
        "125007 MSK-PC-Гагаринский": 0,
        "125008 MSK-PC-РИО Ленинский": 0,
        "125009 NNV-PC-Фантастика": 0,
        "125011 SPB-PC-Мега 2 Парнас": 0,
        "125839 - MSK-PC-Outlet Белая Дача": 0,
        "129877 MSK-PC-Мега 1 Теплый Стан": 0,
        "130143 MSK-PCM-Мега 2 Химки": 0,
        "150002 MSK-DV-Капитолий": 0,
        "Сток": 0,
        "Фото склад": 0,
        "expected_script1": "No distribution (Stock=0)",
        "expected_script2": "No change",
    },
    {
        "name": "S4: All stores full, Stock still has",
        "description": "Stock=3, all have 1 → Stock remains (nothing to distribute)",
        "Номенклатура": "Test Product D",
        "Характеристика": "Size XL",
        "125004 EKT-PC-Гринвич": 1,
        "125005 EKT-PC-Мега": 1,
        "125006 KZN-PC-Мега": 1,
        "125007 MSK-PC-Гагаринский": 1,
        "125008 MSK-PC-РИО Ленинский": 1,
        "125009 NNV-PC-Фантастика": 1,
        "125011 SPB-PC-Мега 2 Парнас": 1,
        "125839 - MSK-PC-Outlet Белая Дача": 1,
        "129877 MSK-PC-Мега 1 Теплый Стан": 1,
        "130143 MSK-PCM-Мега 2 Химки": 1,
        "150002 MSK-DV-Капитолий": 1,
        "Сток": 3,
        "Фото склад": 0,
        "expected_script1": "No distribution (all stores >0)",
        "expected_script2": "No change (none >2)",
    },
    {
        "name": "S5: One store has >2, others empty",
        "description": "125007=5, others=0 → distributes surplus (5-2=3) to empty",
        "Номенклатура": "Test Product E",
        "Характеристика": "Size M",
        "125004 EKT-PC-Гринвич": 0,
        "125005 EKT-PC-Мега": 0,
        "125006 KZN-PC-Мега": 0,
        "125007 MSK-PC-Гагаринский": 5,
        "125008 MSK-PC-РИО Ленинский": 0,
        "125009 NNV-PC-Фантастика": 0,
        "125011 SPB-PC-Мега 2 Парнас": 0,
        "125839 - MSK-PC-Outlet Белая Дача": 0,
        "129877 MSK-PC-Мега 1 Теплый Стан": 0,
        "130143 MSK-PCM-Мега 2 Химки": 0,
        "150002 MSK-DV-Капитолий": 0,
        "Сток": 0,
        "Фото склад": 0,
        "expected_script1": "No change (Stock=0)",
        "expected_script2": "125007→125008=1, 125007→129877=1, 125007→130143=1",
    },
    {
        "name": "S6: Multiple stores >2, takes from highest first",
        "description": "125007=4, 125008=6 → takes from 125008 first (highest)",
        "Номенклатура": "Test Product F",
        "Характеристика": "Size L",
        "125004 EKT-PC-Гринвич": 0,
        "125005 EKT-PC-Мега": 0,
        "125006 KZN-PC-Мега": 0,
        "125007 MSK-PC-Гагаринский": 4,
        "125008 MSK-PC-РИО Ленинский": 6,
        "125009 NNV-PC-Фантастика": 0,
        "125011 SPB-PC-Мега 2 Парнас": 0,
        "125839 - MSK-PC-Outlet Белая Дача": 0,
        "129877 MSK-PC-Мега 1 Теплый Стан": 0,
        "130143 MSK-PCM-Мега 2 Химки": 0,
        "150002 MSK-DV-Капитолий": 0,
        "Сток": 0,
        "Фото склад": 0,
        "expected_script1": "No change (Stock=0)",
        "expected_script2": "125008 distributes 4 (to 129877,130143,150002,125009), then 125007 distributes 2 (to 125011,125004)",
    },
    {
        "name": "S7: Surplus goes to Stock",
        "description": "125007=10, all others already have 1 → remainder to Stock",
        "Номенклатура": "Test Product G",
        "Характеристика": "Size S",
        "125004 EKT-PC-Гринвич": 1,
        "125005 EKT-PC-Мега": 1,
        "125006 KZN-PC-Мега": 1,
        "125007 MSK-PC-Гагаринский": 10,
        "125008 MSK-PC-РИО Ленинский": 1,
        "125009 NNV-PC-Фантастика": 1,
        "125011 SPB-PC-Мега 2 Парнас": 1,
        "125839 - MSK-PC-Outlet Белая Дача": 1,
        "129877 MSK-PC-Мега 1 Теплый Стан": 1,
        "130143 MSK-PCM-Мега 2 Химки": 1,
        "150002 MSK-DV-Капитолий": 1,
        "Сток": 0,
        "Фото склад": 0,
        "expected_script1": "No change (Stock=0, all >0)",
        "expected_script2": "125007→Сток=8 (surplus 10-2=8, no empty stores)",
    },
    {
        "name": "S8: Photo Stock Distribution",
        "description": "Photo Stock=3, Stock=0, all empty → distributes from Photo",
        "Номенклатура": "Test Product H",
        "Характеристика": "Size M",
        "125004 EKT-PC-Гринвич": 0,
        "125005 EKT-PC-Мега": 0,
        "125006 KZN-PC-Мега": 0,
        "125007 MSK-PC-Гагаринский": 0,
        "125008 MSK-PC-РИО Ленинский": 0,
        "125009 NNV-PC-Фантастика": 0,
        "125011 SPB-PC-Мега 2 Парнас": 0,
        "125839 - MSK-PC-Outlet Белая Дача": 0,
        "129877 MSK-PC-Мега 1 Теплый Стан": 0,
        "130143 MSK-PCM-Мега 2 Химки": 0,
        "150002 MSK-DV-Капитолий": 0,
        "Сток": 0,
        "Фото склад": 3,
        "expected_script1": "With 'photo': 125007=1, 125008=1, 129877=1",
        "expected_script2": "No change",
    },
]

def create_test_excel():
    wb = Workbook()
    
    # Sheet 1: Test Data (in format of real input file)
    ws_data = wb.active
    ws_data.title = "Test Input"
    
    # Header rows to match real file format
    ws_data['A1'] = ""
    ws_data['A2'] = "Параметры:"
    ws_data['C2'] = "Дата остатков: TEST"
    
    # Column headers (row 7 in real file, row 7 here)
    headers = [
        "Ид номенклатуры", "", "", "Ид характеристики", 
        "Номенклатура", "Характеристика", "", "Коллекция (сезон)",
        "Наименование_доп", "Штрихкод", "",
        "125004 EKT-PC-Гринвич", "125005 EKT-PC-Мега", "125006 KZN-PC-Мега",
        "125007 MSK-PC-Гагаринский", "125008 MSK-PC-РИО Ленинский",
        "125009 NNV-PC-Фантастика", "125011 SPB-PC-Мега 2 Парнас",
        "125839 - MSK-PC-Outlet Белая Дача", "129877 MSK-PC-Мега 1 Теплый Стан",
        "130143 MSK-PCM-Мега 2 Химки", "150002 MSK-DV-Капитолий",
        "Сток", "Фото склад"
    ]
    
    for col, header in enumerate(headers, 1):
        ws_data.cell(row=7, column=col, value=header)
        ws_data.cell(row=7, column=col).font = Font(bold=True)
    
    # Sub-header row
    for col in range(12, 25):
        ws_data.cell(row=8, column=col, value="Остаток на складе")
    
    # Data rows
    store_cols = [
        "125004 EKT-PC-Гринвич", "125005 EKT-PC-Мега", "125006 KZN-PC-Мега",
        "125007 MSK-PC-Гагаринский", "125008 MSK-PC-РИО Ленинский",
        "125009 NNV-PC-Фантастика", "125011 SPB-PC-Мега 2 Парнас",
        "125839 - MSK-PC-Outlet Белая Дача", "129877 MSK-PC-Мега 1 Теплый Стан",
        "130143 MSK-PCM-Мега 2 Химки", "150002 MSK-DV-Капитолий",
        "Сток", "Фото склад"
    ]
    
    for i, scenario in enumerate(scenarios):
        row = 9 + i
        ws_data.cell(row=row, column=1, value=1000 + i)  # Ид номенклатуры
        ws_data.cell(row=row, column=4, value=2000 + i)  # Ид характеристики
        ws_data.cell(row=row, column=5, value=scenario["Номенклатура"])
        ws_data.cell(row=row, column=6, value=scenario["Характеристика"])
        
        for j, store in enumerate(store_cols):
            val = scenario.get(store, 0)
            ws_data.cell(row=row, column=12 + j, value=val if val else None)
    
    # Sheet 2: Expected Results
    ws_expected = wb.create_sheet("Expected Results")
    ws_expected['A1'] = "Scenario"
    ws_expected['B1'] = "Description"
    ws_expected['C1'] = "Expected Script 1 (Stock→Stores)"
    ws_expected['D1'] = "Expected Script 2 (Balance)"
    
    for col in range(1, 5):
        ws_expected.cell(row=1, column=col).font = Font(bold=True)
        ws_expected.cell(row=1, column=col).fill = PatternFill("solid", fgColor="FFFF00")
    
    for i, scenario in enumerate(scenarios):
        row = 2 + i
        ws_expected.cell(row=row, column=1, value=scenario["name"])
        ws_expected.cell(row=row, column=2, value=scenario["description"])
        ws_expected.cell(row=row, column=3, value=scenario["expected_script1"])
        ws_expected.cell(row=row, column=4, value=scenario["expected_script2"])
    
    # Adjust column widths
    ws_expected.column_dimensions['A'].width = 40
    ws_expected.column_dimensions['B'].width = 50
    ws_expected.column_dimensions['C'].width = 50
    ws_expected.column_dimensions['D'].width = 60
    
    wb.save("test_scenarios.xlsx")
    print("Created: test_scenarios.xlsx")
    print(f"  - {len(scenarios)} test scenarios")
    print("  - Sheet 'Test Input': Input data matching real file format")
    print("  - Sheet 'Expected Results': Expected outcomes for verification")

if __name__ == "__main__":
    create_test_excel()
