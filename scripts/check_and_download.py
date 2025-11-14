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


def find_all_statistic_entries_in_calendar(statistic_name, calendar_data):
    """Zoek alle entries voor een statistiek in de kalender."""
    if not calendar_data or 'entries' not in calendar_data:
        return []
    
    statistic_name_lower = statistic_name.lower().strip()
    entries = []
    
    for entry in calendar_data['entries']:
        entry_naam = entry.get('naam', '').lower().strip()
        # Exacte match of fuzzy match
        if (entry_naam == statistic_name_lower or 
            statistic_name_lower in entry_naam or 
            entry_naam in statistic_name_lower):
            datum = parse_datum_text(entry.get('datum_text', ''))
            if datum:  # Alleen entries met geldige datum
                entries.append({
                    'datum': datum,
                    'periode': entry.get('periode', ''),
                    'entry': entry
                })
    
    return sorted(entries, key=lambda x: x['datum'], reverse=True)  # Nieuwste eerst


def parse_periode(periode_str):
    """Parse periode string (bijv. 'm-2025-08', 'y-2024', 't-2025-03') naar vergelijkbare waarde."""
    if not periode_str:
        return None
    
    # Format: prefix-jaar-nummer (m-2025-08, y-2024, t-2025-03)
    pattern = r'([mytq])-(\d{4})(?:-(\d{1,2}))?'
    match = re.match(pattern, periode_str.lower())
    
    if match:
        prefix = match.group(1)
        jaar = int(match.group(2))
        nummer = int(match.group(3)) if match.group(3) else 0
        
        # Maak een vergelijkbare waarde: jaar * 1000 + nummer * 10 + prefix waarde
        prefix_value = {'y': 4, 't': 3, 'q': 2, 'm': 1}.get(prefix, 0)
        return jaar * 10000 + nummer * 100 + prefix_value
    
    return None


def get_latest_downloaded_version(stat, download_dir):
    """Bepaal de laatst gedownloade versie voor een statistiek."""
    download_path = Path(download_dir)
    
    if not download_path.exists():
        return None, None
    
    # Zoek alle bestanden voor deze statistiek (zip, csv, txt)
    stat_name_lower = stat.get('naam', '').replace(' ', '_').lower()
    patterns = [
        f"{stat_name_lower}_*.zip",
        f"{stat_name_lower}_*.csv",
        f"{stat_name_lower}_*.txt"
    ]
    
    latest_periode = None
    latest_file = None
    
    for pattern in patterns:
        for file_path in download_path.glob(pattern):
            # Extract datum uit bestandsnaam: statbel_bouwvergunningen_20251201.zip
            filename = file_path.stem
            # Zoek datum patroon: YYYYMMDD
            date_match = re.search(r'(\d{8})$', filename)
            
            if date_match:
                date_str = date_match.group(1)
                try:
                    file_date = datetime.strptime(date_str, '%Y%m%d')
                    # Gebruik de datum als proxy voor periode
                    # Voor maandelijkse data: YYYYMM
                    periode_value = int(date_str[:6])  # YYYYMM
                    
                    if latest_periode is None or periode_value > latest_periode:
                        latest_periode = periode_value
                        latest_file = file_path
                except ValueError:
                    continue
    
    return latest_file, latest_periode


def get_latest_available_version(entries, today):
    """Bepaal de nieuwste beschikbare versie volgens de kalender."""
    available_entries = []
    
    for entry in entries:
        datum = entry['datum']
        periode = entry.get('periode', '')
        
        # Alleen entries die vandaag of in het verleden zijn gepubliceerd
        if datum <= today:
            periode_value = parse_periode(periode)
            if periode_value:
                available_entries.append({
                    'datum': datum,
                    'periode': periode,
                    'periode_value': periode_value,
                    'entry': entry['entry']
                })
    
    if not available_entries:
        return None
    
    # Sorteer op periode waarde (hoogste = nieuwste)
    return max(available_entries, key=lambda x: x['periode_value'])


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
    
    today = datetime.now()
    logger.info(f"Controleren statistieken op {today.date()}")
    
    # Voor elke statistiek in config
    for stat in config['statistieken']:
        kalender_naam = stat.get('kalender_naam')
        stat_naam = stat.get('naam', 'Unknown')
        
        if not kalender_naam:
            logger.warning(f"Geen kalender_naam voor statistiek: {stat_naam}")
            continue
        
        logger.info(f"\n=== Controleren: {stat_naam} ===")
        
        # Vind alle entries voor deze statistiek in de kalender
        calendar_entries = find_all_statistic_entries_in_calendar(kalender_naam, calendar_data)
        
        if not calendar_entries:
            logger.warning(f"Geen kalender entries gevonden voor: {kalender_naam}")
            continue
        
        logger.info(f"Gevonden {len(calendar_entries)} kalender entries voor {kalender_naam}")
        
        # Bepaal nieuwste beschikbare versie volgens kalender
        latest_available = get_latest_available_version(calendar_entries, today)
        
        if not latest_available:
            logger.info(f"Geen beschikbare versies voor {kalender_naam} (alle publicaties zijn in de toekomst)")
            continue
        
        logger.info(f"Nieuwste beschikbare versie volgens kalender: periode {latest_available['periode']}, datum {latest_available['datum'].date()}")
        
        # Bepaal laatst gedownloade versie
        download_dir = Path(stat.get('download_directory', 'data/downloads'))
        latest_downloaded_file, latest_downloaded_periode = get_latest_downloaded_version(stat, download_dir)
        
        if latest_downloaded_file:
            logger.info(f"Laatst gedownloade versie: {latest_downloaded_file.name}")
        else:
            logger.info(f"Geen gedownloade versies gevonden voor {kalender_naam}")
        
        # Vergelijk periodes
        available_periode_value = latest_available['periode_value']
        downloaded_periode_value = latest_downloaded_periode if latest_downloaded_periode else 0
        
        # Voor nu gebruiken we de datum als proxy (YYYYMM)
        available_date_value = int(latest_available['datum'].strftime('%Y%m'))
        
        if latest_downloaded_file:
            # Extract datum uit bestandsnaam
            filename = latest_downloaded_file.stem
            date_match = re.search(r'(\d{8})$', filename)
            if date_match:
                downloaded_date_value = int(date_match.group(1)[:6])  # YYYYMM
            else:
                downloaded_date_value = 0
        else:
            downloaded_date_value = 0
        
        # Check of we up-to-date zijn
        if downloaded_date_value >= available_date_value:
            logger.info(f"✓ Up-to-date: gedownloade versie ({downloaded_date_value}) >= beschikbare versie ({available_date_value})")
            continue
        
        logger.info(f"✗ Niet up-to-date: gedownloade versie ({downloaded_date_value}) < beschikbare versie ({available_date_value})")
        logger.info(f"Downloaden nieuwe versie...")
        
        # Download de nieuwste versie
        calendar_entry = latest_available['entry']
        datum = latest_available['datum']
        
        # Bepaal URL (statisch of via patroon)
        url = stat.get('url')
        url_pattern = stat.get('url_pattern')
        
        if url_pattern:
            url = construct_url(url_pattern, calendar_entry)
            if not url:
                logger.warning(f"Kon URL niet construeren voor {kalender_naam} met patroon {url_pattern}")
                continue
        
        if not url:
            logger.warning(f"Geen URL gevonden voor {kalender_naam}")
            continue
        
        # Maak bestandsnaam
        filename = f"{stat.get('naam', 'unknown').replace(' ', '_').lower()}_{datum.strftime('%Y%m%d')}"
        
        # Bepaal extensie van URL
        parsed_url = urlparse(url)
        ext = Path(parsed_url.path).suffix or '.zip'
        
        output_path = download_dir / f"{filename}{ext}"
        
        # Download alleen als bestand nog niet bestaat
        if not output_path.exists():
            success = download_file(url, output_path)
            if success:
                logger.info(f"✓ Succesvol gedownload: {output_path}")
            else:
                logger.error(f"✗ Download mislukt voor {kalender_naam}")
        else:
            logger.info(f"Bestand bestaat al: {output_path}")


if __name__ == "__main__":
    check_and_download_statistics()

