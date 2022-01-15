import datetime as dt
import json
import os
import requests

import jinja2

#
# Settings
#

# Project settings

# project_dir = os.getcwd()
project_dir = os.path.dirname(os.path.realpath(__file__))

template_dir = f"{project_dir}/templates"

data_dir = f"{project_dir}/data"
output_dir = f"{project_dir}/output"

# Coronavirus API 
# https://coronavirus.data.gov.uk/details/developers-guide/main-api

api_endpoint = 'https://api.coronavirus.data.gov.uk/v1/data'
metrics_cases = [
    'newCasesBySpecimenDateRollingRate',
    'newCasesBySpecimenDateChangePercentage',
    'newCasesBySpecimenDateAgeDemographics',
]
metrics_vaccinations = [
    'cumVaccinationFirstDoseUptakeByPublishDatePercentage',
    'cumVaccinationSecondDoseUptakeByPublishDatePercentage',
    'cumVaccinationThirdInjectionUptakeByPublishDatePercentage',
]
metrics = metrics_cases + metrics_vaccinations
columns = ['date'] + metrics
format = 'json'
request_url = f'{api_endpoint}?format={format}&'\
               'filters=areaType=ltla;areaName=Lewisham&'\
               'structure=["' + '","'.join(columns) + '"]'

#
# Helpers
#

def parse_date(date_str, format='%Y-%m-%d'):
    return dt.datetime.strptime(date_str, format).date()

# Identify the index of the first record that includes the metric.
# records: a list of dated records (the 'data' section of a Gov.uk result)
# metric: the name of a Gov.uk metric
# Returns an index position, or None.
def get_first_index_for(records, metric):
    for idx, record in enumerate(records):
        if metric in record.keys():
            value = record[metric]
            if isinstance(value, list):
                if len(value)>0:
                    return idx
            else:
                if value!=None:
                    return idx
    return None

# Identify the first record that includes the full set of metrics.
# records: a list of dated records (the 'data' section of a Gov.uk result)
# metrics: a list with one or more names of Gov.uk metrics
# Returns a dict, or None.
def get_first_record_for(records, metrics):
    idx = max([
        get_first_index_for(records, metric) 
            for metric in metrics
    ])
    if idx is None:
        return None
    return records[idx]

# Identify the record for a particular age group.
# age_demographics: a list of age-group specific metrics
# age_group_label: the name for a particular age group, e.g. '00_59' (0-59 years old)
# Returns a dict, or None.
def get_age_group_metrics(age_demographics, age_group_label):
    for record in age_demographics:
        if ('age' in record) and (record['age']==age_group_label):
            return record
    return None

#
# Get the data
#

response = requests.get(request_url, timeout=10)

if response.status_code >= 400:
    raise RuntimeError(f'Request failed: { response.text }')

# Write to local cache
os.makedirs(data_dir, exist_ok=True)
with open(f"{data_dir}/text-page-data.json", 'w') as f:
    json.dump(response.json(), f)
    print(response.text[:256] + '...')

#
# Prepare the data
#

with open(f"{data_dir}/text-page-data.json", 'r') as f:
    result = json.load(f)
    records = result['data']

ctx = {} # Template context dict

# 1. Cases
cases_record = get_first_record_for(records, metrics_cases)
if cases_record is None:
    raise RuntimeError('No case records found!')

ctx['cases_date'] = parse_date(cases_record['date'])
ctx['cases_rate'] = cases_record['newCasesBySpecimenDateRollingRate']
ctx['cases_change'] = cases_record['newCasesBySpecimenDateChangePercentage']
case_record_60s = get_age_group_metrics(
    cases_record['newCasesBySpecimenDateAgeDemographics'], 
    '60+')
if case_record_60s is None:
    raise RuntimeError('No case records found for this age group!')
ctx['cases_rate_60s'] = case_record_60s['rollingRate']

# 2. Vaccinations
vaccinations_record = get_first_record_for(records, metrics_vaccinations)
if vaccinations_record is None:
    raise RuntimeError('No vaccination records found!')

ctx['vaccinations_date'] = parse_date(vaccinations_record['date'])
ctx['vaccinations_dose_1'] = vaccinations_record['cumVaccinationFirstDoseUptakeByPublishDatePercentage']
ctx['vaccinations_dose_2'] = vaccinations_record['cumVaccinationSecondDoseUptakeByPublishDatePercentage']
ctx['vaccinations_dose_3'] = vaccinations_record['cumVaccinationThirdInjectionUptakeByPublishDatePercentage']

#
# Generate the page
# 

# Jinja2 filter to format dates.
def format_date(date):
    return date.strftime('%A, %d %B %Y')

# Jinja2 filter to apply thousands separator, with 1 decimal place.
def format_thousands(value):
    return '{:,.1f}'.format(float(value))

j2_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_dir),
    trim_blocks=True)

j2_env.filters['thousands'] = format_thousands
j2_env.filters['date'] = format_date

os.makedirs(f"{output_dir}/text", exist_ok=True)
with open(f"{output_dir}/text/index.html", 'w') as f:
    f.write(j2_env.get_template('text.html').render(ctx))
