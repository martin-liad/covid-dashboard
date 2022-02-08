import datetime as dt
import json
import os
import sys
import time

import jinja2
import requests

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

# Lewisham
metrics_cases = [
    'newCasesBySpecimenDateRollingSum',
    'newCasesBySpecimenDateChange',
    'newCasesBySpecimenDateChangePercentage',
    'newCasesBySpecimenDateDirection',
]
metrics_case_rates = [
    'newCasesBySpecimenDateRollingRate',
    'newCasesBySpecimenDateAgeDemographics',
]
metrics_vaccinations = [
    'cumVaccinationFirstDoseUptakeByVaccinationDatePercentage',
    'cumVaccinationSecondDoseUptakeByVaccinationDatePercentage',
    'cumVaccinationThirdInjectionUptakeByVaccinationDatePercentage',
    'cumPeopleVaccinatedFirstDoseByVaccinationDate',
    'cumPeopleVaccinatedSecondDoseByVaccinationDate',
    'cumPeopleVaccinatedThirdInjectionByVaccinationDate',
]
metrics = metrics_cases + metrics_case_rates + metrics_vaccinations
columns = ['date'] + metrics
format = 'json'
request_url = f'{api_endpoint}?format={format}&'\
               'filters=areaType=ltla;areaName=Lewisham&'\
               'structure=["' + '","'.join(columns) + '"]'

# London & England
metrics_regions = [
    'newCasesBySpecimenDateRollingRate',
]
regions_columns = ['date'] + metrics_regions
london_request_url =  f'{api_endpoint}?format={format}&'\
                       'filters=areaType=region;areaName=London&'\
                       'structure=["' + '","'.join(regions_columns) + '"]'
england_request_url =  f'{api_endpoint}?format={format}&'\
                        'filters=areaType=nation;areaName=England&'\
                        'structure=["' + '","'.join(regions_columns) + '"]'

# Runtime options

# Make an API request, or load cached data from a previous run?
USE_CACHE = False

for arg in sys.argv[1:]:
    if arg in ['-c', '--cached']:
        USE_CACHE = True
    else:
        raise RuntimeError(f'Unknown parameter: {arg}')

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
# offset: an optional offset, to get earlier records relative to the latest available one
# Returns a dict, or None.
def get_first_record_for(records, metrics, offset=0):
    idx = max([
        get_first_index_for(records, metric) 
            for metric in metrics
    ])
    if idx is None:
        return None
    return records[idx+offset]

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

if USE_CACHE:
    print("Skipping API request.")
else:
    for url, name in [
        (request_url, 'lewisham'), 
        (london_request_url, 'london'), 
        (england_request_url, 'england')]:

        response = requests.get(url, timeout=10)
        if response.status_code >= 400:
            raise RuntimeError(f"Request failed: { response.text }")

        # Write to local cache
        os.makedirs(data_dir, exist_ok=True)
        with open(f"{data_dir}/text-data-{name}.json", 'w') as f:
            json.dump(response.json(), f)
            print(response.text[:256] + '...')
        
        # Throttle our request rate
        time.sleep(1)

#
# Prepare the data
#

with open(f"{data_dir}/text-data-lewisham.json", 'r') as f:
    data = json.load(f)
    records = data['data']

with open(f"{data_dir}/text-data-london.json", 'r') as f:
    data = json.load(f)
    london_records = data['data']

with open(f"{data_dir}/text-data-england.json", 'r') as f:
    data = json.load(f)
    england_records = data['data']

ctx = {} # Template context dict
ctx['today'] = dt.datetime.now()

# 1. Cases
cases_record = get_first_record_for(records, metrics_cases)
if cases_record is None:
    raise RuntimeError('No case records found!')
cases_start_record = get_first_record_for(records, metrics_cases, offset=6)

ctx['cases'] = cases_record['newCasesBySpecimenDateRollingSum']
ctx['cases_start_date'] = parse_date(cases_start_record['date'])
ctx['cases_end_date'] = parse_date(cases_record['date'])

previous_cases_record = get_first_record_for(records, metrics_cases, offset=7)
previous_cases_start_record = get_first_record_for(records, metrics_cases, offset=7+6)

ctx['previous_cases'] = previous_cases_record['newCasesBySpecimenDateRollingSum']
ctx['previous_cases_start_date'] = parse_date(previous_cases_start_record['date'])
ctx['previous_cases_end_date'] = parse_date(previous_cases_record['date'])

ctx['cases_change'] = cases_record['newCasesBySpecimenDateChange']
ctx['cases_change_percent'] = cases_record['newCasesBySpecimenDateChangePercentage']
ctx['direction'] = cases_record['newCasesBySpecimenDateDirection']

# 2. Case rate
case_rates_record = get_first_record_for(records, metrics_case_rates)
london_record = get_first_record_for(london_records, metrics_regions)
england_record = get_first_record_for(england_records, metrics_regions)

ctx['case_rate'] = case_rates_record['newCasesBySpecimenDateRollingRate']

ctx['case_rate_london'] = london_record['newCasesBySpecimenDateRollingRate']
ctx['cases_london_end_date'] = parse_date(london_record['date'])
ctx['cases_london_start_date'] = ctx['cases_london_end_date'] - dt.timedelta(days=6)

ctx['case_rate_england'] = england_record['newCasesBySpecimenDateRollingRate']
ctx['cases_england_end_date'] = parse_date(england_record['date'])
ctx['cases_england_start_date'] = ctx['cases_england_end_date'] - dt.timedelta(days=6)

case_record_60s = get_age_group_metrics(
    case_rates_record['newCasesBySpecimenDateAgeDemographics'], 
    '60+')
if case_record_60s is None:
    raise RuntimeError('No case records found for this age group!')
ctx['case_rate_60s'] = case_record_60s['rollingRate']

# 3. Vaccinations
vaccinations_record = get_first_record_for(records, metrics_vaccinations)
if vaccinations_record is None:
    raise RuntimeError('No vaccination records found!')

ctx['vaccinations_date'] = parse_date(vaccinations_record['date'])
ctx['vaccinations_dose_1'] = vaccinations_record['cumVaccinationFirstDoseUptakeByVaccinationDatePercentage']
ctx['vaccinations_dose_2'] = vaccinations_record['cumVaccinationSecondDoseUptakeByVaccinationDatePercentage']
ctx['vaccinations_dose_3'] = vaccinations_record['cumVaccinationThirdInjectionUptakeByVaccinationDatePercentage']
ctx['vaccinations_dose_1_people'] = vaccinations_record['cumPeopleVaccinatedFirstDoseByVaccinationDate']
ctx['vaccinations_dose_2_people'] = vaccinations_record['cumPeopleVaccinatedSecondDoseByVaccinationDate']
ctx['vaccinations_dose_3_people'] = vaccinations_record['cumPeopleVaccinatedThirdInjectionByVaccinationDate']

#
# Generate the page
# 

# Jinja2 filters to format dates.
def format_date(date):
    if date is None:
        return None
    # Unfortunately, Python has no cross-platform strftime code for day-of-month 
    # without leading zeros -- so we need to mix and match our formatting.
    # return date.strftime('%d %B %Y')
    return date.strftime(f"{date.day} %B %Y")

def format_long_date(date):
    if date is None:
        return None
    # return date.strftime('%A, %d %B %Y')
    return date.strftime(f"%A, {date.day} %B %Y")

def format_long_datetime(date):
    if date is None:
        return None
    # return date.strftime('%A, %d %B %Y at %H:%M')
    return date.strftime(f"%A, {date.day} %B %Y at %H:%M")

# Jinja2 filter to apply thousands separator, no decimal places.
def format_thousands(value):
    if value is None:
        return None
    return '{:,}'.format(int(value))

# Jinja2 filter to apply thousands separator, with 1 decimal place.
def format_thousands_1f(value):
    if value is None:
        return None
    return '{:,.1f}'.format(float(value))

j2_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_dir),
    trim_blocks=True)

j2_env.filters['thousands'] = format_thousands
j2_env.filters['thousands_1f'] = format_thousands_1f
j2_env.filters['date'] = format_date
j2_env.filters['long_date'] = format_long_date
j2_env.filters['long_datetime'] = format_long_datetime

os.makedirs(f"{output_dir}/text", exist_ok=True)
with open(f"{output_dir}/text/index.html", 'w', encoding='utf-8') as f:
    f.write(j2_env.get_template('text.html.j2').render(ctx))
