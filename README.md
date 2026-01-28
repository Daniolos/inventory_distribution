# Inventory Distribution Scripts

Zwei Python-Skripte für die automatische Verteilung von Lagerbeständen auf Geschäfte.

## Voraussetzungen

- Python 3.8+
- pandas: `pip install pandas openpyxl`

## Skript 1: Stock → Geschäfte verteilen

Verteilt Bestände von **Сток** oder **Фото склад** auf Geschäfte die 0 haben.

### Verwendung

```bash
# Von Сток verteilen (Standard)
python script1_distribute_stock.py "Остатки + Сезон.xlsx" stock

# Von Фото склад verteilen
python script1_distribute_stock.py "Остатки + Сезон.xlsx" photo
```

### Logik
- Geht jede Zeile durch
- Für jedes Geschäft mit Bestand = 0: 1 Stück verteilen
- Folgt der Prioritätsreihenfolge in `config.py`
- Respektiert ausgeschlossene Geschäfte

---

## Skript 2: Bestände ausgleichen

Gleicht Bestände zwischen Geschäften aus.

### Verwendung

```bash
python balance_inventory.py "Остатки + Сезон.xlsx"
```

### Logik
- Findet Geschäfte mit > 2 Teilen (konfigurierbar)
- Nimmt vom Geschäft mit den meisten Teilen zuerst
- Verteilt auf Geschäfte mit 0 Bestand
- Rest geht zurück ins Stock

---

## Konfiguration (config.py)

```python
# Priorität der Geschäfte (oben = höchste Prio)
STORE_PRIORITY = [
    "125007 MSK-PC-Гагаринский",
    "125008 MSK-PC-РИО Ленинский",
    # ... weitere Geschäfte
]

# Ausgeschlossene Geschäfte
EXCLUDED_STORES = [
    # "125839 - MSK-PC-Outlet Белая Дача",  # Auskommentieren zum Ausschließen
]

# Schwellwert für Ausgleich (Skript 2)
BALANCE_THRESHOLD = 2  # Geschäfte mit > 2 Teilen werden ausgeglichen
```

---

## Output

Alle Output-Dateien werden im `output/` Ordner erstellt:

- Format: `{Sender}_to_{Empfänger}_{Timestamp}.xlsx`
- Beispiele:
  - `Сток_to_125007_20260128_143000.xlsx`
  - `125839_to_Сток_20260128_143000.xlsx`

### Output-Spalten

| Spalte | Gefüllt |
|--------|---------|
| Артикул | ❌ |
| Код номенклатуры | ❌ |
| Номенклатура | ✅ |
| Характеристика | ✅ |
| Назначение | ❌ |
| Серия | ❌ |
| Код упаковки | ❌ |
| Упаковка | ❌ |
| Количество | ✅ |

---

## Zukünftige Erweiterungen

- [ ] Proximity-basierte Verteilung (nahegelegene Geschäfte bevorzugen)
- [ ] GUI für einfachere Bedienung
- [ ] Automatische E-Mail-Benachrichtigung nach Ausführung
