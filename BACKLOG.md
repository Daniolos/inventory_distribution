# Inventory Distribution App - Backlog

## Status Legend
- [ ] Offen
- [x] Erledigt
- [~] In Bearbeitung

---

## Backlog Items

### 1. [x] Checkbox-ID Bug im Balance Inventory fixen
**Priorität:** Hoch | **Komplexität:** Niedrig

**Problem:** Bei "Generate Preview" im Balance Inventory Tab erscheint der Fehler:
```
Error loading file: There are multiple checkbox elements with the same auto-generated ID.
```

**Ursache:**
- `render_preview()` wird für beide Tabs aufgerufen
- Die Checkbox "Show only rows with transfers" hat keinen eindeutigen `key`
- Beide Tabs teilen denselben `st.session_state.preview_results`

**Lösung:**
- Separate session states: `preview_results_script1`, `preview_results_script2`
- `render_preview()` mit `prefix` Parameter für eindeutige Keys

**Dateien:** `app.py`

---

### 2. [x] Robustere Header-Erkennung
**Priorität:** Hoch | **Komplexität:** Mittel

**Problem:** Header ist fest auf Zeile 7 (`INPUT_HEADER_ROW = 6`) eingestellt. Excel-Dateien mit Header in anderen Zeilen funktionieren nicht korrekt.

**Lösung:**
- Automatische Header-Erkennung durch Suche nach "Номенклатура" in den ersten 20 Zeilen
- Fallback auf konfigurierte Zeile falls nicht gefunden
- Bessere Fehlermeldung wenn Header nicht gefunden

**Dateien:** `app.py`, `core/config.py`

---

### 3. [x] Zusätzliche Filter-Spalten hinzufügen
**Priorität:** Hoch | **Komplexität:** Mittel

**Anforderung:** Neue Spalten für Filterung verwenden:
- `Коллекция (сезон)` - Collection/Season
- `Наименование_доп` - Additional Name

**UI:** Multiselect-Filter im Hauptbereich direkt nach Datei-Upload

**Zweck:** Rows für Transfers eingrenzen, statt verschiedene Excel-Listen abzugeben

**Dateien:** `core/config.py`, `app.py`

---

### 4. [x] Stock → Stores: Mindestanzahl-Regel pro Produkt
**Priorität:** Hoch | **Komplexität:** Hoch

**Anforderung:** Neue Logik für Stock → Stores Transfers:
- **0-1 Größen im Store:** 3 weitere verschiedene Größen hinzufügen
- **2+ Größen im Store:** Normale Transfer-Logik (1 Stück pro Variante mit 0 Bestand)

**Regel bei unzureichendem Stock:** "Alles oder nichts"
- Nur transferieren wenn ≥3 verschiedene Größen im Stock verfügbar
- Sonst: Kein Transfer für dieses Produkt/Store-Kombination

**Voraussetzung:** Wir gehen davon aus, dass Produkte mindestens 4 Größen haben

**Dateien:** `core/distributor.py`

---

## Abgeschlossene Items

*(Hierher verschieben wenn erledigt)*

---

## Notizen

- Die App hat zwei Hauptfunktionen: "Stock → Stores" und "Balance Inventory"
- Beide verwenden aktuell dieselbe `render_preview()` Funktion
- Header-Row ist in `core/config.py` als `INPUT_HEADER_ROW = 6` (0-indexed = Zeile 7) definiert
