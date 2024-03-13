# -*- coding: utf-8 -*-
# Required Libraries.
import csv
import json
import logging
import os
import sys
import time
import datetime
import traceback
import requests

# TODO Documentation
# TODO Installation PIP Requirements
# TODO Mission Control

# POD-hour calculation as per doc
# https://docs.dynatrace.com/docs/shortlink/dps-containers#billing-granularity-for-pod-hour-consumption

# GiBHour calculation  
# https://docs.dynatrace.com/docs/manage/subscriptions-and-licensing/dynatrace-platform-subscription/host-monitoring#gib-hour-calculation-for-containers-and-application-only-monitoring


# Read Configuration and assign the variables
config = json.load(open('config.json'))

min_memory = 0.25
MANAGED_DNS = "managed.internal.dynatrace"

LOG_FILE = config['log_file']
LOG_DIR = config['log_dir']
REPORT_DIR = config['report_dir']

TENANT_URL = config['tenant_url']
API_TOKEN = config['api_token']

ssoCSRFCookie = config['mission_control']['ssoCSRFCookie']
JSESSIONID = config['mission_control']['JSESSIONID']

unit=config['query']['unit']
resolution=config['query']['resolution']
from_timeframe=config['query']['from']
#
# Query to fetch the avg size of K8s PGIs and the ammount of datapoints with a 
# 15m resolution 
query_body="""/api/v2/metrics/query?metricSelector=
builtin:tech.generic.mem.workingSetSize:parents:filter(
and(
in("dt.entity.process_group_instance",entitySelector("type(PROCESS_GROUP_INSTANCE),
toRelationships.runsOnProcessGroupInstance(type(SERVICE),agentTechnologyType.exists())")),
or(
in("dt.entity.host",entitySelector("type(HOST),softwareTechnologies(KUBERNETES)")),
in("dt.entity.host",entitySelector("type(HOST),paasVendorType(KUBERNETES)")),
in("dt.entity.host",entitySelector("type(HOST),paasVendorType(OPENSHIFT)")))
)):splitBy("dt.entity.process_group_instance"):count:fold(sum):sort(value(sum,ascending)),
builtin:tech.generic.mem.workingSetSize:parents:filter(
and(
in("dt.entity.process_group_instance",entitySelector("type(PROCESS_GROUP_INSTANCE),
toRelationships.runsOnProcessGroupInstance(type(SERVICE),agentTechnologyType.exists())")),
or(
in("dt.entity.host",entitySelector("type(HOST),softwareTechnologies(KUBERNETES)")),
in("dt.entity.host",entitySelector("type(HOST),paasVendorType(KUBERNETES)")),
in("dt.entity.host",entitySelector("type(HOST),paasVendorType(OPENSHIFT)")))
)):splitBy("dt.entity.process_group_instance"):avg:fold(avg):sort(value(avg,ascending))
"""
q_to_unit=":toUnit(Byte," + unit + ")"
q_resolution="&resolution="+ resolution
q_from="&from=" + from_timeframe

# Put the parametrized Query together
query = query_body + q_to_unit + q_resolution + q_from

class EmptyResponse:
    """Set an empty response with code"""
    status_code = 500
    reason = 'Unkown'
    content = 'Empty'

   
# Sample class with init method
class PGI:
    # init method or constructor
    def __init__(self, id, count, memory):
        self.id = id
        self.count = count
        self.memory = memory
        self.memory_rounded = 0
        self.memory_total = 0

    def get_memory_total(self):
        return self.memory_total
    
    # Sample Method
    def set_memory(self, memory):
        self.memory = memory

        if memory < min_memory:
            self.memory_rounded = min_memory
        else:
            # floor division
            dividend = memory // min_memory
            self.memory_rounded = dividend * min_memory

            # If we have remainders we increase to next round up
            if (memory % min_memory) > 0:
                self.memory_rounded = self.memory_rounded + min_memory

        # We divide the memory and multiply by the amount ot timeslots was found to calculate the Gib-hour
        if resolution == "1h":
            self.memory_total = self.memory_rounded * self.count
        elif resolution == "15m":
            self.memory_total = (self.memory_rounded / 4) * self.count
        elif resolution == "1d":
            self.memory_total = self.memory_rounded * self.count * 24
        else:
            logging.error("Resolution not expected for calulating total memory %s", resolution)
            self.memory_total = (self.memory_rounded / 4) * self.count


        logging.debug("%s", self)

    def get_list_values(self):
        """Returns the list of values"""
        return [self.id, self.count ,self.memory,self.memory_rounded,self.memory_total]
    
    def get_list_header(self):
        """Returns the headers as strings"""
        return ["PGI", "Count" ,"Memory AVG","Memory Rounded","Memory Total"]
    
    def __str__(self):
        return f"{self.id}, count({self.count}), mem({self.memory}), rounded({self.memory_rounded}), total({self.memory_total})"


def check_create_dir(dir_name):
    """Verify if dir exists, if not create one"""
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

# Logging configuration
# Create log directory at initialization
check_create_dir(LOG_DIR)

check_create_dir(REPORT_DIR)

# Initialize logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename=LOG_DIR + '/' + LOG_FILE,
                    level=logging.INFO)

# Add logging also to the console of the running program
logging.getLogger().addHandler(logging.StreamHandler())

def get_header_json():
    """Header builder as json"""
    return {'content-type': 'application/json'}

def get_header():
    """"Header builder"""
    return {'content-type': 'application/json', "Authorization": "Api-Token " + API_TOKEN }

def get_header_managed():
    """"Header builder for MC"""
    return {'content-type': 'application/json', "Authorization": "Api-Token " + API_TOKEN , 
            "Cookie": "ssoCSRFCookie= " + ssoCSRFCookie + ";JSESSIONID=" + JSESSIONID }

def verify_request():
    """Verify request"""
    return True

def get_now_as_string():
    ts = time.time()
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d_%H-%M-%S')

def do_get(endpoint):
    """Function get http request"""
    if MANAGED_DNS in TENANT_URL:
        logging.info("Querying a Managed server, you need to be inside Dynatrace internal network")
        logging.info("Using MC Cookies from config file")
        logging.info("Node:%s", TENANT_URL)
        endpoint = endpoint + "&Api-Token " + API_TOKEN
        response = requests.get(TENANT_URL + endpoint, headers=get_header_managed(), verify=verify_request(), timeout=120)
    else:
        response = requests.get(TENANT_URL + endpoint, headers=get_header(), verify=verify_request(), timeout=10)       
    logging.debug("GET Reponse content: %s - %s ", str(response.content), endpoint)
    return response

def validate_set_action_status(response, action, defaultvalue=''):
    """Validate response"""
    result = defaultvalue
    action_status = True

    if 200 <= response.status_code <= 300:
        # If not default value, then set the reason
        if not defaultvalue:
            result = response.reason

        action_status = True
    else:
        result = str(response.status_code)
        logging.warning(action + ':\t code:' + result +
                        ' reason:' + response.reason + ' Content:' + str(response.content))
        action_status = False

    logging.info(action + ':\t' + result)
    logging.debug(action + ':\t' + result + 'Content:' + str(response.content))
    return action_status

def estimate_costs():
    """Function to estimate the costs"""
    logging.info("Fetching all PGI datapoints from %s in %s intervals and their AVG Memory from the API...", from_timeframe, resolution)
    response = do_get(query)
    
    # Validate response
    if not validate_set_action_status(response, 'Query [builtin:tech.generic.mem.workingSetSize] status'):
        return

    json_payload = json.loads(response.text)
    totalCount = json_payload['totalCount']
    nextPageKey = json_payload['nextPageKey']
    response_resolution = json_payload['resolution']
    dataPointCountRatio = json_payload['result'][0]['dataPointCountRatio']
    dimensionCountRatio = json_payload['result'][0]['dimensionCountRatio']
    
    try:
        warnings = json_payload['warnings']
        logging.error("Warnings in the response:%s",warnings)
    except KeyError:
        logging.debug("No warnings in the response")
    
    logging.info("Total Count:%s, response_resolution:%s, dataPointCountRatio:%s, dimensionCountRatio:%s, nextPageKey:%s",totalCount,response_resolution, dataPointCountRatio, dimensionCountRatio, nextPageKey)
    
    if resolution != response_resolution:
        logging.warning("The response resolution of %s does not match the requested resolution %s", response_resolution, resolution)

    # TODO Do we need to calculate ratios?
    # TODO Get Names in the payload

    total_memory = 0

    # Add the PGIs with the count
    pgis = {}
    for line in json_payload['result'][0]['data']:
        pgi_id = line['dimensions'][0]
        count = line['values'][0]
        pgis[pgi_id]= PGI(pgi_id, count, 0);
    
    # Add and calculate the Memory
    for line in json_payload['result'][1]['data']:
        pgi_id = line['dimensions'][0]
        mem = line['values'][0]
        pgi = pgis[pgi_id]
        pgi.set_memory(mem)
        total_memory = total_memory + pgi.get_memory_total()

    logging.info("Total Memory is %s GiB-hour for %s pod instances", total_memory, len(pgis))

    write_report(pgis, total_memory)
    
    return 

def write_report(pgis, total_memory):

    filename = get_now_as_string() + "_k8s_estimation_costs_report_.csv"
    logging.info("Writing a report in %s file", filename)

    # Get the header of the first PGI Object in the dictionary
    header = list(pgis.values())[0].get_list_header()
    rows = []
    for pgi in pgis.values():
        rows.append(pgi.get_list_values())

    delimiter = ["______", "______" ,"______","______", "______"]
    summary = [len(pgis), " " ,"","", total_memory]
 
    # writing to csv file
    with open(REPORT_DIR + "/" + filename, 'w') as csvfile:
        # creating a csv writer object
        csvwriter = csv.writer(csvfile)
        # writing the fields
        csvwriter.writerow(header)
        # writing the data rows
        csvwriter.writerows(rows)
        # delimiter
        csvwriter.writerow(delimiter)
        # write the summary
        csvwriter.writerow(summary)

    return

def main():
    try:
        printUsage = False

        logging.info("=================================================")
        logging.info("Starting Dynatrace Kubernetes License Estimation\n")
        logging.info("=================================================")
        logging.info("")
        logging.info("Fetching all pod instances that have run in Kubernetes or ")
        logging.info("Openshift environments for the timeframe of %s" , from_timeframe)
        logging.info("")
        logging.info("-------------------------------------------------")
        logging.info("Tenant: %s", TENANT_URL)
        logging.info("Log file: %s", LOG_FILE)
        estimate_costs()

    except Exception as e:  # catch all exceptions
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logging.error(traceback.print_exc(), e)
        traceback.print_exc()

    if printUsage:
        doUsage(sys.argv)
    else:
        print("\nDone calculatig costs... have a nice day")
    exit


def get_usage_as_string():
    return """
Dynatrace Kubernetes License Estimation 
================================================================
Usage: estimate.py

*** For more information read the README.md file ***
================================================================
"""


def doUsage(args):
    "Just printing Usage"
    usage = get_usage_as_string()
    print(usage)
    exit


# Start Main
if __name__ == "__main__":
    main()

