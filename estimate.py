# -*- coding: utf-8 -*-
# Required Libraries.
import calendar
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

# POD-hour calculation as per doc
# https://docs.dynatrace.com/docs/shortlink/dps-containers#billing-granularity-for-pod-hour-consumption

# GiBHour calculation  
# https://docs.dynatrace.com/docs/manage/subscriptions-and-licensing/dynatrace-platform-subscription/host-monitoring#gib-hour-calculation-for-containers-and-application-only-monitoring

# Read Configuration and assign the variables
config = json.load(open('config.json'))

min_memory = 0.25

MANAGED_DNS = "managed.internal.dynatrace"
FORMAT_DATE = '%Y-%m-%d'
LOG_FILE = config['log_file']
LOG_DIR = config['log_dir']
REPORT_DIR = config['report_dir']

TENANT_URL = config['tenant_url']
API_TOKEN = config['api_token']

price_pod_hour =  config['price_pod_hour']
price_gib_hour =  config['price_gib_hour']

ssoCSRFCookie = config['mission_control']['ssoCSRFCookie']
JSESSIONID = config['mission_control']['JSESSIONID']

unit=config['query']['unit']
resolution=config['query']['resolution']
from_timeframe=config['query']['from']
to_timeframe=config['query']['to']
iterations=config['query']['iterations']
days_per_iteration=config['query']['days_per_iteration']
iterative_query=config['query']['iterative_query']


# API V2 Endpoint for metric selection
q_metric_selector_endpoint="/api/v2/metrics/query?metricSelector="
#
# Query to fetch the avg size of K8s PGIs and the ammount of datapoints with a 
# 15m resolution 
query_body="""
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
q_resolution_1h="&resolution=1h"
q_from="&from=" 
q_from_t = q_from + from_timeframe
q_to="&to="
q_to_t= q_to + to_timeframe
q_podhour_metric = "builtin:kubernetes.pods:splitBy():sum:fold(value)"

# Put the parametrized Query together
query_pods_by_ns_static = q_metric_selector_endpoint +  q_podhour_metric + q_resolution_1h + q_from_t + q_to_t 
query_pods_by_ns_dyn = q_metric_selector_endpoint +  q_podhour_metric + q_resolution_1h 

# Put the parametrized Query together
query_memory_static = q_metric_selector_endpoint + query_body + q_to_unit + q_resolution + q_from_t + q_to_t 
query_memory_dyn = q_metric_selector_endpoint + query_body + q_to_unit + q_resolution  

class Query:

    def __init__(self, query):
        self.query = query
        self.response = {}
        self.json_payload = {}
        self.warnings = []
        self.pgis = {}
        self.shortliving_pgis = []
        self.total_memory = 0
        self.issues = False
        self.total_pod_hours = 0
        self.date_from = None
        self.date_to = None


    def set_response(self, response):
        self.response = response

    def set_json_payload(self, json_payload):
        self.json_payload = json_payload

    def set_warnings(self, warnings):
        self.warnings = warnings
    
    def get_query(self):
        return self.query
    
    def get_response(self):
        return self.response
    
    def get_warnings(self):
        return self.warnings
    
    def get_json_payload(self):
        return self.json_payload
    
    def get_pgis(self):
        return self.pgis
    
    def get_shortliving_pgis(self):
        return self.shortliving_pgis
    
    def get_total_memory(self):
        return self.total_memory
    
    def set_total_memory(self, total_memory):
        self.total_memory = total_memory
    
    def had_issues(self):
        return self.issues
    
    def has_issues(self):
        self.issues = True

    def get_total_pod_hours(self):
        return self.total_pod_hours
    
    def set_total_pod_hours(self, total_pod_hours):
        self.total_pod_hours = total_pod_hours
    
    def get_date_from(self):
        return self.date_from
    
    def set_date_from(self, date_from):
        self.date_from = date_from

    def get_date_to(self):
        return self.date_to
    
    def set_date_to(self, date_to):
        self.date_to = date_to

    
class EmptyResponse:
    """Set an empty response with code"""
    status_code = 500
    reason = 'Unkown'
    content = 'Empty'

class PGI:
    """ PGI Class, contains logic for rounding up and calculating total memory per PGI based on resolution"""
    # init method or constructor
    def __init__(self, id, count, memory):
        self.id = id
        self.count = count
        self.memory = memory
        self.memory_rounded = 0
        self.memory_total = 0

    def get_memory_total(self):
        return self.memory_total
    
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

        elif resolution == "6h":
            self.memory_total = self.memory_rounded * self.count * 6

        elif resolution == "1d":
            self.memory_total = self.memory_rounded * self.count * 24

        else:
            logging.error("Resolution not expected for calulating total memory %s", resolution)
            self.memory_total = (self.memory_rounded / 4) * self.count

        logging.debug("Set memory for %s", self)

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
        logging.debug("Querying a Managed server, you need to be inside Dynatrace internal network")
        logging.debug("Using MC Cookies from config file")
        logging.debug("Node:%s", TENANT_URL)
        endpoint = endpoint + "&Api-Token " + API_TOKEN
        response = requests.get(TENANT_URL + endpoint, headers=get_header_managed(), verify=verify_request(), timeout=120)
    else:
        response = requests.get(TENANT_URL + endpoint, headers=get_header(), verify=verify_request(), timeout=10)       
    logging.debug("GET Reponse content: %s - %s ", str(response.content), endpoint)
    return response

def validate_query(query, action, defaultvalue=''):
    """Validate response and payload"""
    result = defaultvalue
    status = True
    response = query.get_response()
    json_payload = query.get_json_payload()

    if 200 <= response.status_code <= 300:
        # If not default value, then set the reason
        if not defaultvalue:
            result = response.reason

        status = True
        try:
            json_payload = json.loads(response.text)
            query.set_json_payload(json_payload)

            totalCount = json_payload['totalCount']
            nextPageKey = json_payload['nextPageKey']
            response_resolution = json_payload['resolution']
            dataPointCountRatio = json_payload['result'][0]['dataPointCountRatio']
            dimensionCountRatio = json_payload['result'][0]['dimensionCountRatio']
    
            warnings = json_payload['warnings']
            query.set_warnings(warnings)
            logging.error("%s:warnings in the response:%s", action, warnings)
        except KeyError:
            logging.debug("No warnings in the response")
        except json.decoder.JSONDecodeError:
            if MANAGED_DNS in TENANT_URL:
                logging.error("Please make sure that you have set the proper Mission Control Cookies 'ssoCSRFCookie' 'JSESSIONID'")
                logging.error("and you have established a connection to the Cluster via MC.")
                query.has_issues()
                return False
            else:
                # raise uknown e
                query.has_issues()
                raise
    
        logging.debug("Total Count:%s, response_resolution:%s, dataPointCountRatio:%s, dimensionCountRatio:%s, nextPageKey:%s",totalCount,response_resolution, dataPointCountRatio, dimensionCountRatio, nextPageKey)
        
        if resolution != response_resolution:
            logging.warning("The response resolution of %s does not match the requested resolution %s", response_resolution, resolution)
    
    else:
        result = str(response.status_code)
        logging.warning("%s :\t code:%s reason:%s  Content:%s", action, result, response.reason, str(response.content))
        query.has_issues()
        status = False

    logging.debug("%s:%s",action,result)
    logging.debug("%s:%s Content:%s",action, result, str(response.content))
    return status

def estimate_podhours(podQuery):
    """Function to calculate the pod hours"""

    podQuery.set_response(do_get(podQuery.get_query()))

    # Validate response
    if not validate_query(podQuery, "Query [builtin:kubernetes.pods] status"):
        return

    # Work with the payload
    # TODO Finish the calculation by NS for doing a report
    total_pod_hours = int(podQuery.get_json_payload()['result'][0]['data'][0]['values'][0])
    podQuery.set_total_pod_hours(total_pod_hours)

    return

def estimate_costs():
    """Function to estimate the costs"""
    # TODO Get Names in the payload
    pod_Queries = []
    mem_Queries = []

    # We Iterate the whole i times
    if iterative_query:
        logging.info("Fetching all PGI datapoints from %s. Iterating %s times by %s days in %s resolution", from_timeframe, iterations, days_per_iteration, resolution)

        date_from = datetime.datetime.strptime(from_timeframe, FORMAT_DATE)
        
        for i in range(iterations):

            if i == 0:
                date_from_start = date_from 
                date_from_end = date_from + datetime.timedelta(days=days_per_iteration)
            else:
                date_from_start = date_from + datetime.timedelta(days=(i * days_per_iteration))
                date_from_end = date_from + datetime.timedelta(days=((i * days_per_iteration) + days_per_iteration))

            # Convert microseconds in miliseconds
            q_from_dyn = q_from + str(int(date_from_start.timestamp() * 1000))
            q_to_dyn = q_to + str(int(date_from_end.timestamp() * 1000))
            
            pod_query = Query(query_pods_by_ns_dyn + q_from_dyn + q_to_dyn)
            pod_query.set_date_from(date_from_start)
            pod_query.set_date_to(date_from_end)
            pod_Queries.append(pod_query)

            mem_query = Query(query_memory_dyn + q_from_dyn + q_to_dyn)
            mem_query.set_date_from(date_from_start)
            mem_query.set_date_to(date_from_end)
            mem_Queries.append(mem_query)
    else:
        logging.info("Fetching all PGI datapoints from %s until %s in %s resolution", from_timeframe, to_timeframe, resolution)
        # To is static - already embebded in the query string
        date_to = datetime.datetime.strptime(to_timeframe, FORMAT_DATE)

        pod_query = Query(query_pods_by_ns_static)
        pod_query.set_date_from(date_from)
        pod_query.set_date_to(date_to)
        pod_Queries.append(pod_query)
        
        mem_query = Query(query_memory_static)
        mem_query.set_date_from(date_from)
        mem_query.set_date_to(date_to)
        mem_Queries.append(mem_query)
        logging.debug("From to Query mode activated.")

    # Execute the Queries
    actual_i = len(pod_Queries)

    t_pod_h = 0
    t_gib_h = 0
    t_instances = 0
    t_shortliving_instances = 0

    for i in range(actual_i):
        # Calculate the POD-hours
        pod_query = pod_Queries[i]
        estimate_podhours(pod_query)
        if pod_query.had_issues():
            # If there is an issue with this query we go out.
            return
        
        # Calculate the Gib-hours
        mem_query = mem_Queries[i]
        estimate_memory(mem_query)
    
        # write_report(memQuery.get_pgis(), memQuery.get_total_memory())
        instances = len(mem_query.get_pgis())
        shortliving_instances = len(mem_query.get_shortliving_pgis())
        percentage_shortliving = 100 * float(shortliving_instances)/float(instances)

        date_from = pod_query.get_date_from().strftime(FORMAT_DATE)
        date_to = pod_query.get_date_to().strftime(FORMAT_DATE)
        
        l = " " + str(i + 1) + " of "+ str(days_per_iteration) +"d \t"+ date_from + " to " + date_to

        pod_h = pod_query.get_total_pod_hours()
        gib_h = mem_query.get_total_memory()

        logging.info("%s\t%s pod-hours", l, f"{pod_h:,}")
        logging.info("%s\t%s GiB-hours from %s pod instances",l , f"{gib_h:,}", f"{instances:,}")
        logging.info("%s\t%s instances lived under %s vs a total of %s instances equals %s %%",l, f"{shortliving_instances:,}" , resolution, f"{instances:,}", ("%.3f" % percentage_shortliving))
        logging.info("")

        t_pod_h = t_pod_h + pod_h
        t_gib_h = t_gib_h + gib_h
        t_instances = t_instances + instances
        t_shortliving_instances = t_shortliving_instances + shortliving_instances
        
    k8_costs= t_pod_h * price_pod_hour
    app_costs= t_gib_h * price_gib_hour
    
    logging.info("Kubernetes Monitoring consumption from %s to %s = %s pod-hours", from_timeframe, date_to, f"{t_pod_h:,}")
    logging.info("Kubernetes Monitoring estimated costs are %s pod-hours * %s USD = $%s USD", f"{t_pod_h:,}", str(price_pod_hour), f"{k8_costs:,}")
    logging.info("")
    logging.info("Application Observability consumption from %s to %s = %s Gib-hours", from_timeframe, date_to, f"{t_gib_h:,}")
    logging.info("Application Observability estimated costs are %s Gib-hours * %s USD = $%s USD", f"{t_gib_h:,}", str(price_gib_hour), f"{app_costs:,}")
    
    logging.info("")
    logging.info("Total costs are $%s USD", f"{(k8_costs + app_costs):,}")

    return 

def estimate_memory(memQuery):
    """ Function to estimate the Gib-hour consumption"""
    # pgis, total_memory, shortliving_pgis
    memQuery.set_response(do_get(memQuery.get_query()))

    # Validate response
    if not validate_query(memQuery, "Query [builtin:tech.generic.mem.workingSetSize] status"):
        return
    
    json_payload = memQuery.get_json_payload()
    pgis = memQuery.get_pgis()
    shortliving_pgis = memQuery.get_shortliving_pgis()
    total_memory = memQuery.get_total_memory()

    # Work with the payload
    # We iterate in count
    for line in json_payload['result'][0]['data']:
        pgi_id = line['dimensions'][0]
        count = line['values'][0]
        pgi = PGI(pgi_id, count, 0)
        pgis[pgi_id]= pgi

        # We store the shortliving pgis to be aware of
        # their ratio.
        if count == 1:
            shortliving_pgis.append(pgi)

    # Add and calculate the Memory
    for line in json_payload['result'][1]['data']:
        pgi_id = line['dimensions'][0]
        mem = line['values'][0]
        pgi = pgis[pgi_id]
        pgi.set_memory(mem)
        total_memory = total_memory + pgi.get_memory_total()

    memQuery.set_total_memory(total_memory)

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
        logging.info("   Dynatrace License cost estimation for      \n")
        logging.info("        Kubernetes Monitoring")
        logging.info("                 and ")
        logging.info("      Application Observability  ")
        logging.info("=================================================")
        logging.info("")
        logging.info("Fetching all pod instances that have run in Kubernetes or ")
        logging.info("Openshift environments")
        logging.info("")
        logging.info("-------------------------------------------------")
        logging.info("Tenant: %s", TENANT_URL)
        logging.debug("Log file: %s", LOG_FILE)

        estimate_costs()

    except Exception as e:  # catch all exceptions
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logging.error(traceback.print_exc(), e)
        traceback.print_exc()

    if printUsage:
        doUsage(sys.argv)
    else:
        print("\nDone calculating costs... have a nice day")
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
