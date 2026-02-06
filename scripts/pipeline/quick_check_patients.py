#!/usr/bin/env python3
"""Script rapide pour vérifier quels patients ont leurs fichiers FASTQ."""

import json
import subprocess
from pathlib import Path

bucket = "genomic-cancer-pipeline-input-dev-622994489865"

patients_file = Path("data/patients_list.json")
with open(patients_file) as f:
    patients = json.load(f)

found = []
for i, patient in enumerate(patients[:60]):
    patient_id = patient.get("patient_id", "")
    r1_path = f"s3://{bucket}/patients/{patient_id}/R1.fastq.gz"
    
    try:
        result = subprocess.run(
            ["aws", "s3", "ls", r1_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            found.append(patient_id)
            print(f"✅ {patient_id} ({len(found)} trouvés)")
    except:
        pass
    
    if i % 10 == 0 and i > 0:
        print(f"Vérifié {i} patients, {len(found)} trouvés...")

print(f"\nTotal: {len(found)} patients avec FASTQ")
