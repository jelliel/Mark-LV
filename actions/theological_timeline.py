# theological_timeline.py
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import re

def get_theo_vault_path() -> Path:
    """Get the path to the theo_vault directory."""
    return Path(__file__).resolve().parent.parent / "theo_vault"

def load_entities() -> Dict[str, Any]:
    """Load all entity JSON files from theo_vault/entities/."""
    entities_dir = get_theo_vault_path() / "entities"
    entities = {}
    if not entities_dir.exists():
        return entities
    for entity_file in entities_dir.glob("*.json"):
        try:
            with open(entity_file, 'r', encoding='utf-8') as f:
                entity_data = json.load(f)
                key = entity_data.get('name', entity_file.stem)
                entities[key] = entity_data
        except Exception as e:
            print(f"[Theological Timeline] Error loading {entity_file}: {e}")
    return entities

def extract_date_from_entity(entity_data: Dict[str, Any]) -> Optional[str]:
    """Extract a date or period from entity data."""
    # Look for period field
    if 'period' in entity_data and isinstance(entity_data['period'], str):
        return entity_data['period']

    # Look for key_positions with dates
    if 'key_positions' in entity_data and isinstance(entity_data['key_positions'], dict):
        for position, details in entity_data['key_positions'].items():
            if isinstance(details, dict) and 'date' in details:
                return details['date']
            elif isinstance(details, dict) and 'period' in details:
                return details['period']

    # Look for key_events with dates
    if 'key_events' in entity_data and isinstance(entity_data['key_events'], list):
        dates = []
        for event in entity_data['key_events']:
            if isinstance(event, dict) and 'date' in event:
                dates.append(event['date'])
        if dates:
            return ", ".join(dates)

    return None

def build_thematic_timeline(theme: str, entities: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Build a timeline showing how different entities relate to a theme over time.

    Args:
        theme: The theological theme to create a timeline for (e.g., "hadith_transmission")
        entities: Optional pre-loaded entities dict

    Returns:
        A dictionary representing the timeline with entities positioned chronologically
    """
    if entities is None:
        entities = load_entities()

    # Find entities related to the theme
    related_entities = []
    for entity_name, entity_data in entities.items():
        # Check if theme appears in key_positions
        key_positions = entity_data.get('key_positions', {})
        if isinstance(key_positions, dict):
            for position, details in key_positions.items():
                if isinstance(details, dict):
                    stance = details.get('stance', '')
                    if theme.lower() in stance.lower() or theme.lower() in position.lower():
                        related_entities.append((entity_name, entity_data, details))
                        break
                elif isinstance(details, str) and theme.lower() in details.lower():
                    related_entities.append((entity_name, entity_data, {'stance': details}))
                    break

        # Check if theme appears in general entity description
        if theme.lower() in json.dumps(entity_data, ensure_ascii=False).lower():
            # Add with minimal details if not already added via key_positions
            if not any(e[0] == entity_name for e in related_entities):
                related_entities.append((entity_name, entity_data, {}))

    # Extract dates and sort chronologically (simplified - in reality would need proper date parsing)
    timeline_entries = []
    for entity_name, entity_data, details in related_entities:
        date_str = extract_date_from_entity(entity_data)
        timeline_entries.append({
            "entity": entity_name,
            "entity_data": entity_data,
            "details": details,
            "date_str": date_str,
            "date_sort_key": _get_date_sort_key(date_str) if date_str else 9999  # Put undated at end
        })

    # Sort by date (undated items will go to the end)
    timeline_entries.sort(key=lambda x: x["date_sort_key"])

    # Format for output
    formatted_timeline = {
        "theme": theme,
        "generated_date": "2026-10-14",  # In real implementation, use current date
        "entries": []
    }

    for entry in timeline_entries:
        formatted_entry = {
            "entity": entry["entity"],
            "role": entry["entity_data"].get("role", "Unknown"),
            "date_or_period": entry["date_str"] or "Date non spécifiée",
            "position_on_theme": entry["details"].get("stance", "Position non spécifiée") if isinstance(entry["details"], dict) else str(entry["details"]),
            "key_sources": entry["entity_data"].get("key_positions", {}).get(list(entry["entity_data"].get("key_positions", {}).keys())[0] if entry["entity_data"].get("key_positions") else {}, {}).get("sources", []) if entry["entity_data"].get("key_positions") else []
        }
        formatted_timeline["entries"].append(formatted_entry)

    return formatted_timeline

def _get_date_sort_key(date_str: Optional[str]) -> int:
    """
    Convert a date string to a sortable key.
    Very simplified - in reality would need proper historical date parsing.
    Returns a large number for undatable entries.
    """
    if not date_str or date_str.strip() == "":
        return 9999

    # Try to extract a year (very basic)
    # Look for 4-digit numbers that could be years
    years = re.findall(r'\b(1[0-9]{3}|2[0-9]{3})\b', date_str)
    if years:
        try:
            # Use the first year found
            return int(years[0])
        except:
            return 9999

    # Handle Islamic dates (hijri) - very simplified
    if 'hégire' in date_str.lower() or 'ah' in date_str.lower():
        # Very rough conversion: subtract ~622 years and take first 4-digit number
        years = re.findall(r'\b(1[0-9]{3})\b', date_str)
        if years:
            try:
                return int(years[0]) - 622
            except:
                return 9999

    # Could not extract a usable date
    return 9999

def format_timeline_as_md(timeline: Dict[str, Any]) -> str:
    """Format the timeline as a markdown string."""
    lines = [
        f"# Chronologie thématique: {timeline['theme']}",
        f"*Généré le: {timeline['generated_date']}*\n"
    ]

    if not timeline['entries']:
        lines.append("Aucune entrée trouvée pour ce thème.")
        return "\n".join(lines)

    lines.append("| Entité | Rôle | Date/Période | Position sur le thème |")
    lines.append("|--------|------|--------------|-----------------------|")

    for entry in timeline['entries']:
        lines.append(f"| {entry['entity']} | {entry['role']} | {entry['date_or_period']} | {entry['position_on_theme']} |")

    return "\n".join(lines)

# For testing/demonstration
if __name__ == "__main__":
    # Example usage
    timeline = build_thematic_timeline("hadith_transmission")
    print(format_timeline_as_md(timeline))