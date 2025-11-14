#!/usr/bin/env python3
"""
Script om te controleren wanneer statistieken gepubliceerd worden volgens de kalender
en deze automatisch te downloaden.
"""

import json
import yaml
from pathlib import Path
import requests
from datetime import datetime, timedelta
import re
from urllib.parse import urlparse
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CONFIG_FILE = Path("direct-links.yaml")
CALENDAR_DIR = Path("data/calendar")
DOWNLOAD_BASE_DIR = Path("data/downloads")


def load_config():
    """Laad de YAML configuratie."""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_calendar(year=None):
    """Laad de kalender voor een specifiek jaar."""
    if year is None:
        year = datetime.now().year
    
    calendar_file = CALENDAR_DIR / f"calendar_{year}.json"
    
    if not calendar_file.exists():
        logger.warning(f"Kalender voor {year} niet gevonden: {calendar_file}")
        return None
    
    with open(calendar_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_datum_text(datum_text):
    """Parse Nederlandse datum tekst naar datetime object."""
    # Nederlandse maandnamen
    maanden = {
        'januari': 1, 'februari': 2, 'maart': 3, 'april': 4,
        'mei': 5, 'juni': 6, 'juli': 7, 'augustus': 8,
        'september': 9, 'oktober': 10, 'november': 11, 'december': 12
    }
    
    # Zoek patroon: "1 december 2025" of "1 dec 2025"
    pattern = r'(\d{1,2})\s+(\w+)\s+(\d{4})'
    match = re.search(pattern, datum_text.lower())
    
    if match:
        dag = int(match.group(1))
        maand_naam = match.group(2)
        jaar = int(match.group(3))
        
        # Vind maandnummer
        for naam, nummer in maanden.items():
            if naam.startswith(maand_naam):
                return datetime(jaar, nummer, dag)
    
    return None


def find_upcoming_publications(calendar_data, days_ahead=7):
    """Vind aankomende publicaties binnen X dagen."""
    if not calendar_data or 'entries' not in calendar_data:
        return []
    
    today = datetime.now()
    cutoff_date = today + timedelta(days=days_ahead)
    
    upcoming = []
    
    for entry in calendar_data['entries']:
        datum = parse_datum_text(entry.get('datum_text', ''))
        
        if datum and today <= datum <= cutoff_date:
            upcoming.append({
                'datum': datum,
                'naam': entry.get('naam', ''),
                'periode': entry.get('periode', ''),
                'entry': entry
            })
    
    return sorted(upcoming, key=lambda x: x['datum'])


def find_statistic_in_calendar(statistic_name, calendar_data):
    """Zoek een statistiek in de kalender op basis van kalender_naam."""
    if not calendar_data or 'entries' not in calendar_data:
        return None
    
    statistic_name_lower = statistic_name.lower().strip()
    
    # Exacte match
    for entry in calendar_data['entries']:
        entry_naam = entry.get('naam', '').lower().strip()
        if entry_naam == statistic_name_lower:
            return entry
    
    # Fuzzy match (bevat)
    for entry in calendar_data['entries']:
        entry_naam = entry.get('naam', '').lower().strip()
        if statistic_name_lower in entry_naam or entry_naam in statistic_name_lower:
            logger.info(f"Fuzzy match gevonden: '{statistic_name}' -> '{entry.get('naam')}'")
            return entry
    
    return None


def construct_url(url_pattern, calendar_entry):
    """Construeer URL op basis van patroon en kalender entry."""
    if not url_pattern:
        return None
    
    # Voor nu simpel: vervang placeholders
    # Kan uitgebreid worden met meer complexe patronen
    url = url_pattern
    
    # Vervang {periode} met periode uit kalender entry
    if '{periode}' in url and calendar_entry:
        periode = calendar_entry.get('periode', '')
        url = url.replace('{periode}', periode)
    
    # Vervang {datum} met datum
    if '{datum}' in url and calendar_entry:
        datum = parse_datum_text(calendar_entry.get('datum_text', ''))
        if datum:
            url = url.replace('{datum}', datum.strftime('%Y%m%d'))
    
    return url


def download_file(url, output_path):
    """Download een bestand van een URL."""
    try:
        logger.info(f"Downloaden van {url} naar {output_path}")
        
        response = requests.get(url, timeout=60, stream=True)
        response.raise_for_status()
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Download voltooid: {output_path}")
        return True
        
    except requests.RequestException as e:
        logger.error(f"Fout bij downloaden van {url}: {e}")
        return False


def check_and_download_statistics():
    """Hoofdfunctie: controleer kalender en download statistieken."""
    # Laad configuratie
    config = load_config()
    if not config or 'statistieken' not in config:
        logger.error("Geen statistieken gevonden in configuratie")
        return
    
    # Laad kalender voor huidig jaar
    calendar_data = load_calendar()
    if not calendar_data:
        logger.error("Kon kalender niet laden")
        return
    
    # Vind aankomende publicaties
    upcoming = find_upcoming_publications(calendar_data, days_ahead=7)
    logger.info(f"Gevonden {len(upcoming)} aankomende publicaties")
    
    # Voor elke statistiek in config
    for stat in config['statistieken']:
        kalender_naam = stat.get('kalender_naam')
        if not kalender_naam:
            logger.warning(f"Geen kalender_naam voor statistiek: {stat.get('naam')}")
            continue
        
        # Zoek in kalender
        calendar_entry = find_statistic_in_calendar(kalender_naam, calendar_data)
        
        if calendar_entry:
            datum = parse_datum_text(calendar_entry.get('datum_text', ''))
            today = datetime.now()
            
            # Check of publicatie vandaag of in het verleden is
            if datum and datum <= today:
                logger.info(f"Publicatie gevonden voor {kalender_naam} op {datum.date()}")
                
                # Bepaal URL (statisch of via patroon)
                url = stat.get('url')
                url_pattern = stat.get('url_pattern')
                
                if url_pattern:
                    url = construct_url(url_pattern, calendar_entry)
                    if not url:
                        logger.warning(f"Kon URL niet construeren voor {kalender_naam} met patroon {url_pattern}")
                        continue
                
                if url:
                    download_dir = Path(stat.get('download_directory', 'data/downloads'))
                    filename = f"{stat.get('naam', 'unknown').replace(' ', '_').lower()}_{datum.strftime('%Y%m%d')}"
                    
                    # Bepaal extensie van URL
                    parsed_url = urlparse(url)
                    ext = Path(parsed_url.path).suffix or '.zip'
                    
                    output_path = download_dir / f"{filename}{ext}"
                    
                    # Download alleen als bestand nog niet bestaat
                    if not output_path.exists():
                        success = download_file(url, output_path)
                        if success:
                            logger.info(f"Succesvol gedownload: {output_path}")
                        else:
                            logger.error(f"Download mislukt voor {kalender_naam}")
                    else:
                        logger.info(f"Bestand bestaat al: {output_path}")
                else:
                    logger.warning(f"Geen URL gevonden voor {kalender_naam}")
            else:
                logger.info(f"Publicatie voor {kalender_naam} is nog niet beschikbaar (datum: {datum})")
        else:
            logger.debug(f"Geen kalender entry gevonden voor {kalender_naam}")


if __name__ == "__main__":
    check_and_download_statistics()

