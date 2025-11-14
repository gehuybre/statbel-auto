<<<<<<< HEAD
# Auto-Statbel

Automatisch downloaden en verwerken van Statbel statistieken op basis van de publicatiekalender.

## Overzicht

Dit project automatiseert het downloaden van Statbel statistieken door:
1. Jaarlijks de publicatiekalender op te halen van [statbel.fgov.be/nl/calendar](https://statbel.fgov.be/nl/calendar)
2. Dagelijks te controleren wanneer statistieken gepubliceerd worden
3. Automatisch de data te downloaden wanneer deze beschikbaar is
4. De gedownloade bestanden op te slaan voor verdere verwerking

## Structuur

```
auto-statbel/
├── direct-links.yaml          # Configuratie met statistieken en metadata
├── scripts/
│   ├── fetch_calendar.py      # Script om publicatiekalender op te halen
│   └── check_and_download.py  # Script om te controleren en te downloaden
├── .github/
│   └── workflows/
│       ├── fetch-calendar.yml      # GitHub Action: jaarlijks kalender ophalen
│       └── check-and-download.yml  # GitHub Action: dagelijks controleren en downloaden
└── data/
    ├── calendar/              # Opgeslagen publicatiekalenders (JSON)
    └── downloads/            # Gedownloade statistiek bestanden
```

## Configuratie

### direct-links.yaml

Elke statistiek heeft de volgende structuur:

```yaml
statistieken:
  - naam: Statbel, bouwvergunningen
    kalender_naam: Bouwvergunningen  # Naam zoals op publicatiekalender
    url: https://statbel.fgov.be/...
    url_pattern: null  # Optioneel: patroon voor dynamische URLs
    metadata:
      - veld: REFNIS
        beschrijving: Refnis-code
      # ... meer velden
    data_type: txt file with delimiter "|"
    publicatie_frequentie: monthly
    download_directory: data/bouwvergunningen
```

**Belangrijke velden:**
- `kalender_naam`: Exacte naam zoals deze voorkomt op de publicatiekalender (gebruikt voor matching)
- `url`: Directe link naar het bestand (kan statisch zijn of een patroon)
- `download_directory`: Waar de gedownloade bestanden worden opgeslagen

## Gebruik

### Lokaal testen

1. Installeer dependencies:
```bash
pip install -r requirements.txt
```

2. Haal de kalender op:
```bash
python scripts/fetch_calendar.py
```

3. Controleer en download statistieken:
```bash
python scripts/check_and_download.py
```

### GitHub Actions

De GitHub Actions worden automatisch uitgevoerd:

- **fetch-calendar.yml**: Op 1 januari van elk jaar om de nieuwe kalender op te halen
- **check-and-download.yml**: Dagelijks om 8:00 UTC om te controleren op nieuwe publicaties

Je kunt ze ook handmatig triggeren via de GitHub Actions tab.

## Toevoegen van nieuwe statistieken

1. Voeg een nieuwe entry toe aan `direct-links.yaml`
2. Zorg dat `kalender_naam` exact overeenkomt met de naam op de publicatiekalender
3. Geef de `url` op (of `url_pattern` als deze dynamisch is)
4. Voeg metadata toe met alle velden en beschrijvingen
5. Commit en push - de GitHub Actions zullen automatisch de nieuwe statistiek monitoren

## Werking

1. **Kalender ophalen**: Het `fetch_calendar.py` script scrapet de Statbel kalender pagina en slaat deze op als JSON
2. **Matching**: Het `check_and_download.py` script matcht statistieken uit de configuratie met entries in de kalender op basis van `kalender_naam`
3. **Download**: Wanneer een publicatiedatum bereikt is, wordt de data automatisch gedownload naar de opgegeven directory
4. **Deduplicatie**: Bestanden die al bestaan worden niet opnieuw gedownload

## Notities

- De kalender wordt jaarlijks opgehaald omdat Statbel elk jaar een nieuwe kalender publiceert
- De scripts controleren of een publicatiedatum vandaag of in het verleden is voordat ze downloaden
- Gedownloade bestanden worden opgeslagen met een timestamp in de bestandsnaam

## Licentie

CC BY 4.0 (zoals Statbel data)

=======
# statbel-auto
>>>>>>> ef027962d557dfd5131010c978e5c9bd5dbfa45a
