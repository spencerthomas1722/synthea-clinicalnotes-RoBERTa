import json


# read the patient's history json
def get_patient_info(json_name):
    with open(json_name, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

