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
from .cache import *
import requests

from app import Estimate as conf
from app.PGI import PGI
from app.Query import Query

# TODO Documentation

# TODO Installation PIP Requirements

class EmptyResponse:
    """Set an empty response with code"""
    status_code = 500
    reason = 'Unkown'
    content = 'Empty'

def check_create_dir(dir_name):
    """Verify if dir exists, if not create one"""
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

# Logging configuration
# Create log directory at initialization
check_create_dir(conf.LOG_DIR)

check_create_dir(conf.REPORT_DIR)

# Initialize logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename=conf.LOG_DIR + '/' + conf.LOG_FILE,
                    level=logging.INFO)

# Add logging also to the console of the running program
logging.getLogger().addHandler(logging.StreamHandler())

def get_header_json():
    """Header builder as json"""
    return {'content-type': 'application/json'}

def get_header(api_token):
    """"Header builder"""
    return {'content-type': 'application/json', "Authorization": "Api-Token " + api_token }

def get_header_managed(api_token, ssoCSRFCookie, jsessionId ):
    """"Header builder for MC"""
    return {'content-type': 'application/json', "Authorization": "Api-Token " + api_token ,
            "Cookie": "ssoCSRFCookie= " + ssoCSRFCookie + ";JSESSIONID=" + jsessionId }

def verify_request():
    """Verify request"""
    return True

def get_now_as_string():
    ts = time.time()
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d_%H-%M-%S')

def do_get(e, endpoint):
    """Function get http request"""
    if conf.MANAGED_DNS in e.get_tenant_url():
        logging.debug("Querying a Managed server, you need to be inside Dynatrace internal network")
        logging.debug("Using MC Cookies from config file")
        logging.debug("Node:%s", e.get_tenant_url())
        endpoint = endpoint + "&Api-Token " + e.get_api_token()
        response = requests.get(e.get_tenant_url() + endpoint, headers=get_header_managed(e.get_api_token(), e.get_ssoCSRFCookie(), e.get_jsessionId()), verify=verify_request(), timeout=120)
    else:
        response = requests.get(e.get_tenant_url() + endpoint, headers=get_header(e.get_api_token()), verify=verify_request(), timeout=10)       
    logging.debug("GET Reponse content: %s - %s ", str(response.content), endpoint)
    return response

def validate_query(e, query, action, defaultvalue=''):
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
            if conf.MANAGED_DNS in e.get_tenant_url():
                logging.error("Please make sure that you have set the proper Mission Control Cookies 'ssoCSRFCookie' 'JSESSIONID'")
                logging.error("and you have established a connection to the Cluster via MC.")
                query.has_issues()
                return False
            else:
                # raise uknown e
                query.has_issues()
                raise
    
        logging.debug("Total Count:%s, response_resolution:%s, dataPointCountRatio:%s, dimensionCountRatio:%s, nextPageKey:%s",totalCount,response_resolution, dataPointCountRatio, dimensionCountRatio, nextPageKey)
        
        if e.resolution != response_resolution:
            logging.warning("The response resolution of %s does not match the requested resolution %s", response_resolution, e.resolution)
    
    else:
        result = str(response.status_code)
        logging.warning("%s :\t code:%s reason:%s  Content:%s", action, result, response.reason, str(response.content))
        query.has_issues()
        status = False

    logging.debug("%s:%s",action,result)
    logging.debug("%s:%s Content:%s",action, result, str(response.content))
    return status

def estimate_podhours(e, podQuery):
    """Function to calculate the pod hours"""

    podQuery.set_response(do_get(e, podQuery.get_query()))

    # Validate response
    if not validate_query(e, podQuery, "Query [builtin:kubernetes.pods] status"):
        return

    # Work with the payload
    # TODO Finish the calculation by NS for doing a report
    total_pod_hours = int(podQuery.get_json_payload()['result'][0]['data'][0]['values'][0])
    podQuery.set_total_pod_hours(total_pod_hours)

    return

def do_work(e):

    e.estimation_running = True
    print("sleeping")
    time.sleep(20)
    e.estimation_running = False
    e.k8_costs = 1000
    set_user_cache(e)
    print("woke up and adding to cache")
    return


def estimate_costs(e):

    if e == None:
        # TODO Pass all variables to estimate
        print("NEED TO REFACTOR")

    e.set_estimation_running(True)

    print(e.get_tenant_url())
    print(e.get_api_token())

    """Function to estimate the costs"""
    pod_Queries = []
    mem_Queries = []

    # TODO Get variables from WEB Session 
    # or from Config

    # We iterate the whole i times
    if e.iterative_query:
        logging.info("Fetching all PGI datapoints from %s. Iterating %s times by %s days in %s resolution", e.from_timeframe, e.iterations, e.days_per_iteration, e.resolution)

        date_from = datetime.datetime.strptime(e.from_timeframe, conf.FORMAT_DATE)
        
        for i in range(e.iterations):

            if i == 0:
                date_from_start = date_from 
                date_from_end = date_from + datetime.timedelta(days=e.days_per_iteration)
            else:
                date_from_start = date_from + datetime.timedelta(days=(i * e.days_per_iteration))
                date_from_end = date_from + datetime.timedelta(days=((i * e.days_per_iteration) + e.days_per_iteration))

            # Convert microseconds in miliseconds
            q_from_dyn = e.q_from + str(int(date_from_start.timestamp() * 1000))
            q_to_dyn = e.q_to + str(int(date_from_end.timestamp() * 1000))
            
            pod_query = Query(e.query_pods_by_ns_dyn + q_from_dyn + q_to_dyn)
            pod_query.set_date_from(date_from_start)
            pod_query.set_date_to(date_from_end)
            pod_Queries.append(pod_query)

            mem_query = Query(e.query_memory_dyn + q_from_dyn + q_to_dyn)
            mem_query.set_date_from(date_from_start)
            mem_query.set_date_to(date_from_end)
            mem_Queries.append(mem_query)
    else:
        logging.info("Fetching all PGI datapoints from %s until %s in %s resolution", e.from_timeframe, e.to_timeframe, e.resolution)
        # To is static - already embebded in the query string
        date_to = datetime.datetime.strptime(e.to_timeframe, conf.FORMAT_DATE)

        pod_query = Query(e.query_pods_by_ns_static)
        pod_query.set_date_from(date_from)
        pod_query.set_date_to(date_to)
        pod_Queries.append(pod_query)
        
        mem_query = Query(e.query_memory_static)
        mem_query.set_date_from(date_from)
        mem_query.set_date_to(date_to)
        mem_Queries.append(mem_query)
        logging.debug("From to Query mode activated.")

    # Execute the Queries
    actual_i = len(pod_Queries)

    for i in range(actual_i):
        # Calculate the POD-hours
        pod_query = pod_Queries[i]
        estimate_podhours(e, pod_query)
        if pod_query.had_issues():
            # If there is an issue with this query we go out.
            return
        
        # Calculate the Gib-hours
        mem_query = mem_Queries[i]
        estimate_memory(e, mem_query)
    
        # write_report(memQuery.get_pgis(), memQuery.get_total_memory())
        instances = len(mem_query.get_pgis())
        shortliving_instances = len(mem_query.get_shortliving_pgis())
        percentage_shortliving = 100 * float(shortliving_instances)/float(instances)

        date_from = pod_query.get_date_from().strftime(conf.FORMAT_DATE)
        date_to = pod_query.get_date_to().strftime(conf.FORMAT_DATE)
        
        l = " " + str(i + 1) + " of "+ str(e.days_per_iteration) +"d \t"+ date_from + " to " + date_to

        pod_h = pod_query.get_total_pod_hours()
        gib_h = mem_query.get_total_memory()

        logging.info("%s\t%s pod-hours", l, f"{pod_h:,}")
        logging.info("%s\t%s GiB-hours from %s pod instances",l , f"{gib_h:,}", f"{instances:,}")
        logging.info("%s\t%s instances lived under %s vs a total of %s instances equals %s %%",l, f"{shortliving_instances:,}" , e.resolution, f"{instances:,}", ("%.3f" % percentage_shortliving))
        logging.info("")

        e.t_pod_h = e.t_pod_h + pod_h
        e.t_gib_h = e.t_gib_h + gib_h
        e.t_instances = e.t_instances + instances
        e.t_shortliving_instances = e.t_shortliving_instances + shortliving_instances
        
    e.k8_costs= e.t_pod_h * e.price_pod_hour
    e.app_costs= e.t_gib_h * e.price_gib_hour
    
    logging.info("Kubernetes Monitoring consumption from %s to %s = %s pod-hours", e.from_timeframe, date_to, f"{e.t_pod_h:,}")
    logging.info("Kubernetes Monitoring estimated costs are %s pod-hours * %s USD = $%s USD", f"{e.t_pod_h:,}", str(e.price_pod_hour), f"{e.k8_costs:,}")
    logging.info("")
    logging.info("Application Observability consumption from %s to %s = %s Gib-hours", e.from_timeframe, date_to, f"{e.t_gib_h:,}")
    logging.info("Application Observability estimated costs are %s Gib-hours * %s USD = $%s USD", f"{e.t_gib_h:,}", str(e.price_gib_hour), f"{e.app_costs:,}")
    
    logging.info("")
    logging.info("Total costs are $%s USD", f"{(e.k8_costs + e.app_costs):,}")

    return 

def estimate_memory(e, memQuery):
    """ Function to estimate the Gib-hour consumption"""
    # pgis, total_memory, shortliving_pgis
    memQuery.set_response(do_get(e, memQuery.get_query()))

    # Validate response
    if not validate_query(e, memQuery, "Query [builtin:tech.generic.mem.workingSetSize] status"):
        return
    
    json_payload = memQuery.get_json_payload()
    pgis = memQuery.get_pgis()
    shortliving_pgis = memQuery.get_shortliving_pgis()
    total_memory = memQuery.get_total_memory()

    # Work with the payload
    # We iterate in count - Equals the amount of datapoints or existance in the timeframe (1h)
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
        pgi.set_memory(mem, e.resolution)
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
    with open(conf.REPORT_DIR + "/" + filename, 'w') as csvfile:
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

        estimate_costs(None)

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

if __name__ == '__main__':
    main()