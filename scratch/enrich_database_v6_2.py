import os
import json
import sqlite3
import sys
from pathlib import Path

# Fix encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
MAPPED_JSON_PATH = BASE_DIR / "db" / "rxnorm_mapped.json"
DB_PATH = BASE_DIR / "db" / "medical_codes.db"

ADDITIONAL_RESOLUTIONS = {
    "Gabapentin": "4719",
    "Prednisone": "8683",
    "Naproxen": "7258",
    "Indomethacin": "5856",
    "Plavix": "32968",
    "PTU": "2951",
    "L-thyroxine": "10582"
}

def main():
    if not MAPPED_JSON_PATH.exists():
        print(f"Error: {MAPPED_JSON_PATH} not found.")
        sys.exit(1)
        
    with open(MAPPED_JSON_PATH, "r", encoding="utf-8") as f:
        existing_data = json.load(f)
        
    existing_names = {item["original_name"].strip().lower() for item in existing_data}
    
    new_entries = []
    for name, rxcui in ADDITIONAL_RESOLUTIONS.items():
        if name.strip().lower() not in existing_names:
            new_entries.append({
                "original_name": name,
                "rxcui": rxcui
            })
            existing_names.add(name.strip().lower())
            print(f"Adding extra drug: '{name}' -> RxCUI {rxcui}")
            
    if new_entries:
        existing_data.extend(new_entries)
        with open(MAPPED_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        print("Successfully updated rxnorm_mapped.json.")
        
        # Rebuild SQLite Database
        print("Rebuilding SQLite Database...")
        sys.path.append(str(BASE_DIR / "scratch"))
        import build_database
        success = build_database.build_rxnorm(str(DB_PATH))
        if success:
            print("SQLite database rxnorm table rebuilt successfully!")
        else:
            print("Failed to rebuild database.")
    else:
        print("All extra drugs are already in the database.")

if __name__ == "__main__":
    main()
