import os
import json
import sqlite3
import requests
import time
import sys
from pathlib import Path

# Fix encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
MAPPED_JSON_PATH = BASE_DIR / "db" / "rxnorm_mapped.json"
DB_PATH = BASE_DIR / "db" / "medical_codes.db"

MISSING_DRUGS = [
    'Alprazolam', 'Apixaban', 'Bevacizumab', 'Bisoprolol', 'Buspirone', 'Calcitriol',
    'Calcium Carbonate', 'Capecitabine', 'Carvedilol', 'Celecoxib', 'Citicoline',
    'Clopidogrel', 'Daclatasvir', 'Dapagliflozin', 'Deflazacort', 'Dextrose 5%',
    'Domperidone', 'Donepezil', 'Empagliflozin', 'Enoxaparin', 'Entacapone', 'Entecavir',
    'Eperisone', 'Erlotinib', 'Erythropoietin', 'Escitalopram', 'Esomeprazole', 'Ezetimibe',
    'Febuxostat', 'Fluticasone', 'Formoterol', 'Fosfomycin', 'Galantamine', 'Gaviscon',
    'Glucagon', 'Glucosamine', 'Hyaluronic acid', 'Hydroxychloroquine', 'Hydroxyzine',
    'Hyoscine', 'IVIG', 'Imiglucerase', 'Insulin Aspart', 'Insulin Glargine', 'Insulin Lispro',
    'Kayexalate', 'Ketorolac', 'Lamotrigine', 'Ledipasvir', 'Leflunomide', 'Lenvatinib',
    'Letrozole', 'Levetiracetam', 'Levodopa/Carbidopa', 'Losartan', 'Lugol', 'Melatonin',
    'Memantine', 'Methimazole', 'Miglustat', 'Mirtazapine', 'Montelukast', 'ORS', 'Orlistat',
    'Oxaliplatin', 'Paclitaxel', 'Paracetamol', 'Peginterferon alfa-2a', 'Perindopril',
    'Pramipexole', 'Pregabalin', 'Rabeprazole', 'Rasagiline', 'Rebamipide', 'Rifampicin',
    'Ringer Lactate', 'Rivaroxaban', 'Rivastigmine', 'Rosuvastatin', 'Sacubitril/Valsartan',
    'Salbutamol', 'Sapropterin', 'Sertraline', 'Sitagliptin', 'Sofosbuvir', 'Sorafenib',
    'Sulfasalazine', 'Tamsulosin', 'Telmisartan', 'Theophylline', 'Thiocolchicoside',
    'Tiotropium', 'Tramadol', 'Trastuzumab', 'Trazodone', 'Trihexyphenidyl', 'Ursodeoxycholic acid',
    'Valproate', 'Vitamin K', 'Zolpidem'
]

# Hardcoded synonyms and specific combinations to prevent empty matches
MANUAL_RESOLUTIONS = {
    "paracetamol": "161",
    "salbutamol": "435",
    "valproate": "11118",
    "rifampicin": "9384",
    "ringer lactate": "315",
    "ors": "256",
    "levodopa/carbidopa": "35206",
    "sacubitril/valsartan": "1656328",
    "gaviscon": "224905",
    "lugol": "312211"
}

def get_rxcui_from_api(drug_name):
    drug_name_clean = drug_name.strip()
    
    # Check manual resolutions first
    if drug_name_clean.lower() in MANUAL_RESOLUTIONS:
        return MANUAL_RESOLUTIONS[drug_name_clean.lower()]
        
    # 1. Direct query
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={drug_name_clean}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            rxnorm_id_list = data.get("idGroup", {}).get("rxnormId", [])
            if rxnorm_id_list:
                return rxnorm_id_list[0]
    except Exception:
        pass
        
    # 2. Try substitution of '/' with ' and '
    if "/" in drug_name_clean:
        name_alt = drug_name_clean.replace("/", " and ").strip()
        url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={name_alt}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                rxnorm_id_list = data.get("idGroup", {}).get("rxnormId", [])
                if rxnorm_id_list:
                    return rxnorm_id_list[0]
        except Exception:
            pass
            
    # 3. Approximate Term Match
    url_approx = f"https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term={drug_name_clean}&maxEntries=1"
    try:
        response = requests.get(url_approx, timeout=10)
        if response.status_code == 200:
            data = response.json()
            candidates = data.get("approximateGroup", {}).get("candidate", [])
            if candidates:
                return candidates[0].get("rxcui")
    except Exception:
        pass
        
    return None

def main():
    if not MAPPED_JSON_PATH.exists():
        print(f"Error: {MAPPED_JSON_PATH} not found.")
        sys.exit(1)
        
    # Read existing mapped json
    with open(MAPPED_JSON_PATH, "r", encoding="utf-8") as f:
        existing_data = json.load(f)
        
    existing_names = {item["original_name"].strip().lower() for item in existing_data}
    
    print(f"Loaded {len(existing_data)} existing drug entries from rxnorm_mapped.json.")
    print(f"We have {len(MISSING_DRUGS)} missing drugs to resolve.")
    
    new_entries = []
    resolved_count = 0
    
    for idx, drug in enumerate(MISSING_DRUGS):
        drug_lower = drug.strip().lower()
        if drug_lower in existing_names:
            print(f"[{idx+1}/{len(MISSING_DRUGS)}] '{drug}' already in mapped database.")
            continue
            
        print(f"[{idx+1}/{len(MISSING_DRUGS)}] Resolving: '{drug}'... ", end="", flush=True)
        rxcui = get_rxcui_from_api(drug)
        if rxcui:
            new_entries.append({
                "original_name": drug,
                "rxcui": rxcui
            })
            existing_names.add(drug_lower)
            resolved_count += 1
            print(f"Success! RxCUI: {rxcui}")
        else:
            print("Failed.")
            
        time.sleep(0.05)
        
    if new_entries:
        # Append new entries
        existing_data.extend(new_entries)
        with open(MAPPED_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        print(f"\nSuccessfully appended {resolved_count} resolved drugs to rxnorm_mapped.json.")
        
        # Now trigger rebuilding of the SQLite database
        print("\nRebuilding SQLite Database...")
        sys.path.append(str(BASE_DIR / "scratch"))
        import build_database
        
        # Rebuild rxnorm table
        success = build_database.build_rxnorm(str(DB_PATH))
        if success:
            print("SQLite database rxnorm table rebuilt successfully!")
            build_database.verify_database(str(DB_PATH))
        else:
            print("Failed to rebuild SQLite database.")
    else:
        print("\nNo new drugs were added.")

if __name__ == "__main__":
    main()
