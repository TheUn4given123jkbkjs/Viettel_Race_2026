import sys
import sqlite3
sys.path.append('scratch')

from generate_train_data_v4 import CLINICAL_DRUG_MATRIX

conn = sqlite3.connect('db/medical_codes.db')
c = conn.cursor()

all_drugs = set()
for drugs in CLINICAL_DRUG_MATRIX.values():
    all_drugs.update(drugs)

missing = []
matched = []
for d in sorted(all_drugs):
    # Try exact match or case-insensitive LIKE
    c.execute('SELECT rxcui, name FROM rxnorm WHERE name LIKE ?', (f'%{d}%',))
    res = c.fetchall()
    if not res:
        missing.append(d)
    else:
        matched.append((d, res[0]))

print(f"Total unique drugs in matrix: {len(all_drugs)}")
print(f"Matched drugs: {len(matched)}")
print(f"Missing drugs: {len(missing)}")
print("\n--- MISSING DRUGS LIST ---")
for d in missing:
    print(f"  - {d}")

conn.close()
