# -*- coding: utf-8 -*-
# Required Libraries.
import json
import logging
import os
import sys
import traceback
import requests


# pod-hour calculation as per doc
# https://docs.dynatrace.com/docs/shortlink/dps-containers#billing-granularity-for-pod-hour-consumption

# gibHour calculation  
# https://docs.dynatrace.com/docs/manage/subscriptions-and-licensing/dynatrace-platform-subscription/host-monitoring#gib-hour-calculation-for-containers-and-application-only-monitoring


# Read Configuration and assign the variables
config = json.load(open('config.json'))

min_memory = 0.25

LOG_FILE = config['log_file']
LOG_DIR = config['log_dir']

TENANT_URL = config['tenant_url']
API_TOKEN = config['api_token']

#
# Query to fetch the avg size of K8s PGIs and the ammount of datapoints with a 
# 15m resolution 
#
query="""/api/v2/metrics/query?metricSelector=
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
)):splitBy("dt.entity.process_group_instance"):avg:fold(avg):sort(value(avg,ascending)):toUnit(Byte,GigaByte)
&resolution=15m&from=now-27d
"""
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
        self.memory_total = (self.memory_rounded / 4) * self.count
        logging.debug("%s", self)

    def __str__(self):
        return f"{self.id}, count({self.count}), mem({self.memory}), rounded({self.memory_rounded}), total({self.memory_total})"


def check_create_dir(dir_name):
    """Verify if dir exists, if not create one"""
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

# Logging configuration
# Create log directory at initialization
check_create_dir(LOG_DIR)

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
    return {'content-type': 'application/json', "Authorization": "Api-Token " + API_TOKEN}

def verify_request():
    """Verify request"""
    return True

def do_get(endpoint):
    """Function get http request"""
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
        logging.warning(action + ':\t: code:' + result +
                        ' reason:' + response.reason + ' Content:' + str(response.content))
        action_status = False

    logging.info(action + ':\t:' + result)
    logging.debug(action + ':\t:' + result + 'Content:' + str(response.content))
    return action_status

def estimate_costs():
    """Function to estimate the costs"""
    logging.info("----------- Estimating Kubernetes costs ------------------------")
    
    response = do_get(query)
    
    # Validate response
    if not validate_set_action_status(response, 'query builtin:tech.generic.mem.workingSetSize'):
        return

    #
    json_payload = json.loads(response.text)
    totalCount = json_payload['totalCount']
    nextPageKey = json_payload['nextPageKey']
    resolution = json_payload['resolution']
    dataPointCountRatio = json_payload['result'][0]['dataPointCountRatio']
    dimensionCountRatio = json_payload['result'][0]['dimensionCountRatio']
    logging.info("Total Count:%s, resolution:%s, dataPointCountRatio:%s, dimensionCountRatio:%s, nextPageKey:%s",totalCount,resolution, dataPointCountRatio, dimensionCountRatio, nextPageKey)
    # TODO Validate Resolution of 15m
    # TODO Check for Warnings
    # TODO Calculate ratios?
    # TODO Get Names
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


    logging.info("Total memory is %s GiB-hour for %s pod instances", total_memory, len(pgis))
    
    return 


def main():
    try:
        printUsage = False

        logging.info("----------------------------------------------")
        logging.info("Starting Dynatrace Kubernetes License Estimation\n")

        estimate_costs()

    except Exception as e:  # catch all exceptions
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logging.error(traceback.print_exc(), e)
        traceback.print_exc()
        # Save it in object
        #save_json(DATA_DIR, "error-results", CSV_DATA)
        # Write Backup
        #save_results(CSV_TEMP_DIR + '/error-' +
         #            getNowAsString() + '-' + CSV_FILE)

    if printUsage:
        doUsage(sys.argv)
    else:
        print("\nDone calculatig costs... have a nice day")
    exit


def get_usage_as_string():
    return """
Dynatrace Kubernetes License Estimation 
================================================================
Usage: estimate.py [command] [options]

Help Commands:
 help           Prints this options
 validate       Validates and prints the config file, tests tests...

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

