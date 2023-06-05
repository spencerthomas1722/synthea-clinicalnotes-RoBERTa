import datetime
import math


# find the difference between two dates and express it in natural language
def date_delta(date1, date2):
    if not isinstance(date1, datetime.date):
        date1 = datetime.date.fromisoformat(date1[:10])
    if not isinstance(date2, datetime.date):
        date2 = datetime.date.fromisoformat(date2[:10])
    delta = date2 - date1 if date2 > date1 else date1 - date2
    delta = delta.days
    if delta > 365:
        years = math.floor(delta/365)
        days = delta % 365
        if 90 < days and days < 270:
            years = years + .5
        return "1 year" if years == 1 else f"{years} years"
    elif delta > 30:
        return "1 month" if math.ceil(delta/30) == 1 else f"{math.ceil(delta/30)} months"
    elif delta > 12:
        return "1 week" if math.ceil(delta/7) == 1 else f"{math.ceil(delta/7)} weeks"
    else:
        return "1 day" if delta == 1 else f"{delta} days"


# filter encounters on or after a patient's first cancer diagnosis.
# option to filter out encounters with vague reasons, like "encounter for symptom",
# because these stated reasons tend not to be useful in prompts.
# also option to only include encounters that have observations (labs, imaging, vitals...) associated with them.
def filter_encounters(pt_info, filter_out_vague_reasons=True, with_observations=False):
    out_encounters = []
    if 'first_cancer_diagnosis' in pt_info:
        for encounter in pt_info['encounters']:
            if filter_out_vague_reasons and encounter['reason'] in ['Encounter for problem', 'Encounter for symptom', 'General examination of patient (procedure)']:
                continue
            elif encounter['datetime']['start'] >= pt_info['first_cancer_diagnosis']:  # get encounters on or after diagnosis date
                if with_observations:  # if we only want encounters that have observations attached
                    if len(encounter['observations']) > 0:
                        out_encounters.append(encounter)
                else:
                    out_encounters.append(encounter)
    else:
        print(f"{pt_info['patient']['name_string']} shows no cancer diagnosis --- check their conditions and amend the 'cancer_terms' list as necessary.")
    return out_encounters


# get conditions and medications that the patient is diagnosed with/taking at a given date
def get_current_items(dct, encounter_date, include_historic=False):
    current = []
    historic = []
    for cond in dct:
        try:
            if isinstance(cond['datetime'], str):
                cond_date = cond['datetime']
            elif isinstance(cond['datetime'], dict):
                cond_date = cond['datetime']['recorded'][:10] if 'recorded' in cond['datetime'] else cond['datetime']['start'][:10]
        except KeyError as e:
            print(e, cond)
            continue
        if cond_date <= encounter_date:
            if 'end' in cond['datetime']:
                try:
                    if cond['datetime']['end'][:10] <= encounter_date and include_historic:
                        historic.append(cond['name'])
                    else:
                        current.append(cond['name'])
                except KeyError as e:
                    print(e, cond)
                    continue
            else:
                current.append(cond['name'])
    return current, historic


# given a set of lab observations, express it in natural language
def labs_section(observations):
    labs = ['Labs:']
    for observation in observations:
        if observation['category'] == 'survey':  # 'value' = dct of form {'question': {'value': 'answer'}}
            try:
                for question in observation['value'].keys():
                    labs.append(f"{question}: {observation['value'][question]['value']}")
            except KeyError:
                labs = labs  # TODO add to follow-up
        else:
            try:
                labs.append(f"{observation['name']}: {observation['value']['value']} {observation['value']['unit']}\n")
            except KeyError:
                labs = labs
    return labs if len(labs) > 1 else []


# given the patient's gender and a grammatical case, return the appropriate pronoun.
def pronoun(gender, case='nominative'):
    if gender.lower().startswith('m'):
        if case == 'accusative':
            return 'Him'
        elif case == 'possessive':
            return 'His'
        elif case == 'reflexive':
            return 'Himself'
        return 'He'
    elif gender.lower().startswith('f'):
        if case == 'accusative':
            return 'Her'
        elif case == 'possessive':
            return 'Her'
        elif case == 'reflexive':
            return 'Herself'
        return 'She'
    else:
        print('We\'ve got a nonbinary patient!')
        if case == 'accusative':
            return 'Them'
        elif case == 'possessive':
            return 'Their'
        elif case == 'reflexive':
            return 'Themself'
        return 'They'
    

# write the patient's allergies as they would appear in a clinical note.
def allergies_section(pt_info):
    out_lines = ['Allergies:']
    for allergy in pt_info['history']['allergies']:
        if 'reactions' in allergy:
            reaction_strings = [f"{reaction['reaction'].split('(')[0]} ({reaction['severity']})" for reaction in allergy['reactions']]
            out_lines.append(f"{allergy['name']} - {', '.join(reaction_strings)}")
        else:
            out_lines.append(f"{allergy['name']} - Reaction unknown")


# add basic social history if the relevant observations are included in the patient's file.
def sdoh_section(pt_info, sdoh_observations):
    sdoh_str = 'Social History:\n'
    # marital status
    sdoh_str += 'Marital status: ' + pt_info['patient']['marital_status'] + '\n' if 'marital_status' in pt_info['patient'] else 'Marital status: Unknown\n'
    # highest education level
    if 'education' in sdoh_observations and len(sdoh_observations['education']) > 0:
        sdoh_str += 'Highest education level: ' + sdoh_observations['education'][-1] + '\n'
    else:
        sdoh_str += 'Highest education level: Unknown\n'
    # employment status
    if 'employment' in sdoh_observations and len(sdoh_observations['employment']) > 0:
        sdoh_str += 'Employment status: ' + sdoh_observations['employment'][-1] + '\n'
    else:
        sdoh_str += 'Employment status: Unknown\n'
    # stresses
    if 'other' in sdoh_observations and len(sdoh_observations['other']) > 0:
        sdoh_str += 'Other SDOH: ' + ', '.join(sdoh_observations['other']) + '\n'
    else:
        sdoh_str += 'Other SDOH: Unknown\n'


# given vital signs, write them as they would appear in a clinical note.
def vitals_section(observations):
    out_lines = ['Vitals:']
    for observation in observations:
        if observation['name'] == 'Blood Pressure':
            out_lines.append(f"Blood pressure: {observation['value']['Systolic Blood Pressure']['value']}/{observation['value']['Diastolic Blood Pressure']['value']}")
        else:
            try:
                out_lines.append(f"{observation['name']}: {observation['value']['value']} {observation['value']['unit']}")
            except KeyError as e:
                print(e)
                print(observation)
    return out_lines


# given a data type, generate the appropriate section for a clinical note.
observation_types = {'vital-signs': vitals_section,
                     'exam': lambda observations: 
                        ['Exam:'] + [f"{observation['name']}: {observation['value']['value']}" for observation in observations],
                    'social-history': lambda observations: 
                        ['Social history:'] + [f"{observation['name']}: {observation['value']['value']}" for observation in observations],
                    'imaging': lambda observations: 
                        ['Imaging:'] + [f"{observation['name']} {observation['value']['value']} {observation['value']['unit']}" for observation in observations],
                    'laboratory': labs_section,
                    'sdoh': sdoh_section
}

# translate between FHIR vocab and section labels.
fhir_to_section_category = {'vital-signs': 'vital-signs', 'imaging': 'imaging', 'laboratory': 'laboratory', 'social-history': 'social history', 'sdoh': 'social history', 'exam': 'exam', 'survey': 'exam'}
