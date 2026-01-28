# Inventory Distribution App - Anforderungen für Claude Code

## Projektübersicht

Es existieren bereits zwei funktionierende Python-Skripte für Lagerbestandsverteilung. Diese sollen jetzt in eine benutzerfreundliche Web-App überführt werden, die von Non-Techies bedient werden kann.

---

## Existierender Code

### Dateien im Projekt

```
inventory_distribution/
├── config.py                    # Konfiguration (Prioritäten, Ausschlüsse)
├── distribute_stock.py  # Stock → Geschäfte verteilen
├── balance_inventory.py # Bestände ausgleichen
├── test_scenarios.xlsx          # Test-Datei mit 8 Szenarien
├── test_data.py                 # Generator für Test-Datei
└── README.md
```

### Script 1: Stock → Geschäfte (`distribute_stock.py`)

**Funktion:** Verteilt Bestände von "Сток" (Stock) oder "Фото склад" (Photo Stock) auf Geschäfte.

**Logik:**
- Geht jede Zeile im Input-Excel durch
- Für jedes Geschäft mit Bestand = 0: Verteilt 1 Stück
- Folgt der Prioritätsreihenfolge aus `config.py`
- Überspringt ausgeschlossene Geschäfte
- Verteilt maximal so viele Stücke wie im Stock vorhanden

**Parameter:**
- `source`: "stock" (Сток) oder "photo" (Фото склад)

### Script 2: Bestände ausgleichen (`balance_inventory.py`)

**Funktion:** Gleicht Bestände zwischen Geschäften aus.

**Logik:**
- Findet Geschäfte mit Bestand > BALANCE_THRESHOLD (Standard: 2)
- Nimmt zuerst vom Geschäft mit dem höchsten Bestand
- Verteilt Überschuss auf Geschäfte mit Bestand = 0 (Prioritätsreihenfolge)
- Wenn alle Geschäfte Bestand haben: Rest geht zu Stock

### Konfiguration (`config.py`)

```python
STORE_PRIORITY = [
    "125007 MSK-PC-Гагаринский",      # Höchste Priorität
    "125008 MSK-PC-РИО Ленинский",
    "129877 MSK-PC-Мега 1 Теплый Стан",
    "130143 MSK-PCM-Мега 2 Химки",
    "150002 MSK-DV-Капитолий",
    "125009 NNV-PC-Фантастика",
    "125011 SPB-PC-Мега 2 Парнас",
    "125004 EKT-PC-Гринвич",
    "125005 EKT-PC-Мега",
    "125006 KZN-PC-Мега",
    "125839 - MSK-PC-Outlet Белая Дача",  # Niedrigste Priorität
]

EXCLUDED_STORES = []  # Geschäfte die nichts bekommen

BALANCE_THRESHOLD = 2  # Geschäfte mit > 2 Teilen werden ausgeglichen
```

### Input-Format (Excel)

- Header in Zeile 7 (0-indexed: row 6)
- Spalten für Produktidentifikation: `Номенклатура`, `Характеристика`
- Spalten für Geschäfte: z.B. `125007 MSK-PC-Гагаринский`
- Spalten für Lager: `Сток`, `Фото склад`
- Werte: Integer (Anzahl) oder leer (= 0)

### Output-Format (Excel)

Separate Dateien pro Sender-Empfänger-Kombination:
- Filename: `{Sender}_to_{Empfänger}_{Timestamp}.xlsx`
- Spalten: `Артикул`, `Код номенклатуры`, `Номенклатура`, `Характеристика`, `Назначение`, `Серия`, `Код упаковки`, `Упаковка`, `Количество`
- Nur `Номенклатура`, `Характеристика`, `Количество` werden gefüllt

---

## Anforderungen an die Streamlit App

### 1. Grundlegende UI-Elemente

#### File Upload
- Drag & Drop Zone für Excel-Datei (.xlsx)
- Anzeige des Dateinamens und der Zeilenanzahl nach Upload
- Validierung: Prüfen ob erwartete Spalten vorhanden sind

#### Skript-Auswahl
- Radio Buttons oder Tabs:
  - "Script 1: Stock → Geschäfte verteilen"
  - "Script 2: Bestände ausgleichen"

#### Script 1 spezifische Optionen
- Dropdown/Radio: Quelle auswählen
  - "Сток (Stock)"
  - "Фото склад (Photo Stock)"

#### Script 2 spezifische Optionen
- Number Input: Balance Threshold (Standard: 2)

### 2. Konfiguration (für beide Skripte)

#### Prioritäts-Editor
- Sortierbare Liste aller Geschäfte
- Drag & Drop zum Umsortieren ODER Auf/Ab-Buttons
- Aktuelle Priorität als nummerierte Liste anzeigen

#### Ausschluss-Editor
- Checkboxen für jedes Geschäft
- Ausgewählte Geschäfte werden von der Verteilung ausgeschlossen

### 3. Vorschau / Zwischenschritt-Anzeige (WICHTIG!)

**Vor der Ausführung:** 
- Button "Vorschau generieren"
- Zeigt pro Input-Zeile die geplanten Zuweisungen an

**Darstellung:**
```
Zeile 1: Test Produkt A / Size M
  └─ Сток → 125007: 1 Stück
  └─ Сток → 125008: 1 Stück
  └─ Сток → 129877: 1 Stück

Zeile 2: Test Produkt B / Size L
  └─ Сток → 129877: 1 Stück
  └─ Сток → 130143: 1 Stück

Zeile 3: Test Produkt C / Size S
  └─ (keine Verteilung - Stock = 0)
```

**Features:**
- Expandable/Collapsible pro Zeile (bei vielen Zeilen)
- Filter: Nur Zeilen mit Zuweisungen anzeigen
- Suchfeld: Nach Produktname filtern
- Zusammenfassung oben: "X Zeilen, Y Zuweisungen total"

### 4. Ausführung und Download

#### Ausführen-Button
- "Transfers generieren"
- Progress Bar während der Verarbeitung
- Erfolgsmeldung mit Zusammenfassung

#### Download-Bereich
- Liste aller generierten Dateien
- "Alle als ZIP herunterladen" Button
- Einzelne Dateien zum Download anklickbar
- Anzeige: Dateiname + Anzahl Einträge

### 5. Zusätzliche Features

#### Validierung & Fehlerbehandlung
- Warnung bei unbekannten Spalten im Input
- Fehleranzeige wenn Geschäft aus Config nicht im Input existiert
- Info wenn keine Verteilungen möglich sind

#### Session State
- Konfiguration bleibt erhalten während der Session
- Option: Konfiguration als JSON exportieren/importieren

#### Help/Dokumentation
- Sidebar oder Expander mit Erklärung der Logik
- Tooltip bei den Konfigurationsoptionen

---

## Technische Anforderungen

### Deployment

**Ziel: Streamlit Community Cloud**
- Kostenloses Hosting
- Deployment direkt aus GitHub
- Keine Server-Konfiguration nötig

**Repository-Struktur:**
```
inventory-distribution-app/
├── app.py                  # Streamlit Hauptanwendung
├── core/
│   ├── __init__.py
│   ├── distributor.py      # Script 1 Logik (refactored)
│   ├── balancer.py         # Script 2 Logik (refactored)
│   └── config.py           # Default-Konfiguration
├── requirements.txt        # Dependencies
├── .streamlit/
│   └── config.toml         # Streamlit Config (Theme etc.)
└── README.md
```

### Dependencies

```
streamlit>=1.28.0
pandas>=2.0.0
openpyxl>=3.1.0
```

### Code-Refactoring

Die bestehende Logik aus `distribute_stock.py` und `balance_inventory.py` sollte in Klassen/Funktionen refactored werden die:
- Input DataFrame direkt akzeptieren (nicht Dateipfad)
- Konfiguration als Parameter akzeptieren (nicht aus config.py importieren)
- Zwischenschritte als Datenstruktur zurückgeben (für Vorschau)
- Output als Liste von DataFrames zurückgeben (nicht direkt speichern)

**Beispiel Interface:**

```python
class StockDistributor:
    def __init__(self, config: DistributionConfig):
        self.config = config
    
    def preview(self, df: pd.DataFrame) -> list[TransferPreview]:
        """Generiert Vorschau der Zuweisungen ohne auszuführen"""
        pass
    
    def execute(self, df: pd.DataFrame) -> list[TransferResult]:
        """Führt Verteilung aus und gibt Ergebnisse zurück"""
        pass

@dataclass
class TransferPreview:
    row_index: int
    product_name: str
    variant: str
    transfers: list[Transfer]  # [(sender, receiver, qty), ...]

@dataclass
class TransferResult:
    sender: str
    receiver: str
    filename: str
    data: pd.DataFrame
```

---

## Nice-to-Have (später)

Diese Features sind optional und können in späteren Iterationen hinzugefügt werden:

1. **Proximity-basierte Verteilung**
   - Nahegelegene Geschäfte bevorzugen
   - Distanz-Matrix zwischen Geschäften definieren

2. **History/Audit Log**
   - Protokoll der ausgeführten Verteilungen
   - Wer hat wann was verteilt

3. **Automatische Erkennung**
   - Input-Format automatisch erkennen
   - Spalten-Mapping UI wenn Format abweicht

4. **Multi-Language Support**
   - Deutsch/Russisch/Englisch UI

---

## Testdaten

Die Datei `test_scenarios.xlsx` enthält 8 vordefinierte Testszenarien die alle Edge Cases abdecken:

| # | Szenario | Erwartetes Ergebnis |
|---|----------|---------------------|
| S1 | Stock=5, alle Geschäfte leer | 5 Geschäfte bekommen je 1 |
| S2 | Stock=3, manche haben schon | Nur leere bekommen |
| S3 | Stock=0 | Keine Verteilung |
| S4 | Alle haben schon 1 | Keine Verteilung |
| S5 | Ein Geschäft hat >2 | Überschuss wird verteilt |
| S6 | Mehrere >2 | Höchster Bestand zuerst |
| S7 | Überschuss, alle voll | Rest geht zu Stock |
| S8 | Фото склад statt Сток | Funktioniert mit photo flag |

Diese Szenarien sollten auch in der App testbar sein (z.B. "Test mit Beispieldaten" Button).

---

## Zusammenfassung Prioritäten

1. **Must Have:**
   - File Upload + Validierung
   - Skript-Auswahl (Script 1 / Script 2)
   - Konfiguration (Prioritäten, Ausschlüsse, Threshold)
   - Vorschau der Zuweisungen pro Zeile
   - Download der generierten Dateien

2. **Should Have:**
   - Progress Bar
   - Filter/Suche in der Vorschau
   - Config Export/Import

3. **Nice to Have:**
   - Proximity-basierte Verteilung
   - Multi-Language