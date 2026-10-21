# theological_cross_reference.py
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple

def get_theo_vault_path() -> Path:
    """Get the path to the theo_vault directory."""
    # This file is in actions/, theo_vault is at parent/theo_vault
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
                # Use the filename stem as key, or the 'name' field if present
                key = entity_data.get('name', entity_file.stem)
                entities[key] = entity_data
        except Exception as e:
            print(f"[Theological Cross-Reference] Error loading {entity_file}: {e}")
    return entities

def load_concepts() -> Dict[str, Any]:
    """Load all concept markdown files with YAML frontmatter from theo_vault/concepts/."""
    concepts_dir = get_theo_vault_path() / "concepts"
    concepts = {}
    if not concepts_dir.exists():
        return concepts
    for concept_file in concepts_dir.glob("*.md"):
        try:
            with open(concept_file, 'r', encoding='utf-8') as f:
                content = f.read()
            # Simple YAML frontmatter extraction (between --- lines)
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    # Very basic YAML parsing for our needs
                    concept_data = {}
                    for line in frontmatter.split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip()
                            value = value.strip()
                            # Try to convert value if it looks like a list
                            if value.startswith('[') and value.endswith(']'):
                                try:
                                    value = json.loads(value)
                                except:
                                    pass  # Keep as string if not valid JSON
                            concept_data[key] = value
                    # The rest is the concept body
                    concept_data['body'] = parts[2].strip()
                    key = concept_data.get('name', concept_file.stem)
                    concepts[key] = concept_data
        except Exception as e:
            print(f"[Theological Cross-Reference] Error loading {concept_file}: {e}")
    return concepts

def find_entity_mentions(text: str, entities: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """Find which entities are mentioned in the given text."""
    mentioned = []
    text_lower = text.lower()
    for entity_name, entity_data in entities.items():
        # Check primary name
        if entity_name.lower() in text_lower:
            mentioned.append((entity_name, entity_data))
            continue
        # Check aliases if present
        aliases = entity_data.get('aliases', [])
        for alias in aliases:
            if alias.lower() in text_lower:
                mentioned.append((entity_name, entity_data))
                break
    return mentioned

def find_concept_mentions(text: str, concepts: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """Find which concepts are mentioned in the given text."""
    mentioned = []
    text_lower = text.lower()
    for concept_name, concept_data in concepts.items():
        # Check concept name
        if concept_name.lower() in text_lower:
            mentioned.append((concept_name, concept_data))
            continue
        # Check related_concepts if present
        related = concept_data.get('related_concepts', [])
        for related_concept in related:
            if isinstance(related_concept, str) and related_concept.lower() in text_lower:
                mentioned.append((concept_name, concept_data))
                break
            elif isinstance(related_concept, dict) and 'name' in related_concept:
                if related_concept['name'].lower() in text_lower:
                    mentioned.append((concept_name, concept_data))
                    break
    return mentioned

def cross_reference_source(source_text: str) -> Dict[str, Any]:
    """
    Perform cross-reference analysis on a source text.
    Returns entities and concepts found, plus potential connections.
    """
    entities = load_entities()
    concepts = load_concepts()

    mentioned_entities = find_entity_mentions(source_text, entities)
    mentioned_concepts = find_concept_mentions(source_text, concepts)

    # Build connection map
    connections = {
        "entities_mentioned": [{"name": name, "data": data} for name, data in mentioned_entities],
        "concepts_mentioned": [{"name": name, "data": data} for name, data in mentioned_concepts],
        "potential_links": []
    }

    # For each mentioned entity, see what concepts they are associated with
    for entity_name, entity_data in mentioned_entities:
        # Look for concepts that mention this entity (would need reverse index, simplify: check if entity name in concept data)
        for concept_name, concept_data in mentioned_concepts:
            # Simple check: does concept data contain entity name?
            concept_str = json.dumps(concept_data, ensure_ascii=False).lower()
            if entity_name.lower() in concept_str:
                connections["potential_links"].append({
                    "entity": entity_name,
                    "concept": concept_name,
                    "type": "entity_in_concept"
                })

    return connections

def get_related_entities(concept_name: str, concepts: Dict[str, Any] = None) -> List[str]:
    """Get entities related to a given concept."""
    if concepts is None:
        concepts = load_concepts()
    concept_data = concepts.get(concept_name)
    if not concept_data:
        return []
    # This would ideally come from a pre-built map, but we'll do a simple search
    related = []
    for ent_name, ent_data in load_entities().items():
        # Check if concept appears in entity's key_positions or related fields
        ent_str = json.dumps(ent_data, ensure_ascii=False).lower()
        if concept_name.lower() in ent_str:
            related.append(ent_name)
    return related

def get_related_concepts(entity_name: str, entities: Dict[str, Any] = None) -> List[str]:
    """Get concepts related to a given entity."""
    if entities is None:
        entities = load_entities()
    entity_data = entities.get(entity_name)
    if not entity_data:
        return []
    related = []
    for conc_name, conc_data in load_concepts().items():
        conc_str = json.dumps(conc_data, ensure_ascii=False).lower()
        if entity_name.lower() in conc_str:
            related.append(conc_name)
    return related

# For testing/demonstration
if __name__ == "__main__":
    # Example usage
    test_text = """
    Umar ibn al-Khattab interdisait initialement l'écriture des hadiths, préférant la transmission orale.
    Selon le document 'Omar et la sunna', il aurait ordonné de brûler les recueils de hadiths.
    Abdullah ibn Abbas, quant à lui, avait une position plus nuancée.
    """
    result = cross_reference_source(test_text)
    print(json.dumps(result, indent=2, ensure_ascii=False))