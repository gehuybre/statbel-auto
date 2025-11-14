#!/usr/bin/env python3
"""
Script om de Statbel publicatiekalender op te halen en op te slaan als JSON.
Dit script wordt jaarlijks uitgevoerd om de kalender voor het nieuwe jaar te verkrijgen.
"""

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from pathlib import Path
import re

CALENDAR_URL = "https://statbel.fgov.be/nl/calendar"
OUTPUT_DIR = Path("data/calendar")
OUTPUT_FILE = OUTPUT_DIR / f"calendar_{datetime.now().year}.json"


def parse_calendar_table(soup):
    """Parse de kalender tabel van de Statbel website."""
    calendar_entries = []
    
    # Zoek naar alle tabellen op de pagina
    tables = soup.find_all('table')
    
    for table in tables:
        rows = table.find_all('tr')
        
        # Skip header rows
        for row in rows:
            cells = row.find_all(['td', 'th'])
            
            # Skip header rows (meestal eerste rij)
            if len(cells) >= 2:
                datum_text = cells[0].get_text(strip=True)
                naam = cells[1].get_text(strip=True)
                periode = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                
                # Skip als dit een header is (geen datum)
                if not datum_text or not naam:
                    continue
                
                # Skip header rijen die geen datum bevatten
                if not re.search(r'\d{1,2}\s+\w+\s+\d{4}', datum_text):
                    continue
                
                if datum_text and naam:
                    try:
                        entry = {
                            "datum_text": datum_text,
                            "naam": naam,
                            "periode": periode
                        }
                        calendar_entries.append(entry)
                    except Exception as e:
                        print(f"Fout bij parsen van rij: {datum_text} - {naam}: {e}")
                        continue
    
    return calendar_entries


def fetch_calendar():
    """Haal de publicatiekalender op van Statbel."""
    print(f"Ophalen van publicatiekalender van {CALENDAR_URL}...")
    
    try:
        response = requests.get(CALENDAR_URL, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        entries = parse_calendar_table(soup)
        
        if not entries:
            print("Waarschuwing: Geen kalender entries gevonden. Mogelijk is de HTML structuur veranderd.")
            # Probeer alternatieve parsing methoden
            # Soms staan de entries in divs of andere elementen
        
        calendar_data = {
            "source_url": CALENDAR_URL,
            "fetched_at": datetime.now().isoformat(),
            "year": datetime.now().year,
            "entries": entries,
            "total_entries": len(entries)
        }
        
        # Sla op
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(calendar_data, f, ensure_ascii=False, indent=2)
        
        print(f"Kalender opgeslagen: {OUTPUT_FILE}")
        print(f"Totaal aantal entries: {len(entries)}")
        
        return calendar_data
        
    except requests.RequestException as e:
        print(f"Fout bij ophalen van kalender: {e}")
        raise
    except Exception as e:
        print(f"Onverwachte fout: {e}")
        raise


if __name__ == "__main__":
    fetch_calendar()

