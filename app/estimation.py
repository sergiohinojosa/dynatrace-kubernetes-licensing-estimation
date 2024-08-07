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
        response = requests.get(e.get_tenant_url() + endpoint, headers=get_header_managed(e.get_api_token(), e.get_ssoCSRFCookie(), e.get_jsessionId()), verify=verify_request(), timeout=180)
    else:
        response = requests.get(e.get_tenant_url() + endpoint, headers=get_header(e.get_api_token()), verify=verify_request(), timeout=120)       
    logging.debug("GET Reponse content: %s - %s ", str(response.content), endpoint)
    return response

def validate_query(e, query, action, defaultvalue=''):
    """Validate response and payload"""
    result = defaultvalue
    response = query.get_response()
    json_payload = query.get_json_payload()

    if 200 <= response.status_code <= 300:
        # If not default value, then set the reason
        if not defaultvalue:
            result = response.reason

        try:
            json_payload = json.loads(response.text)
            query.set_json_payload(json_payload)

            totalCount = json_payload['totalCount']
            nextPageKey = json_payload['nextPageKey']
            response_resolution = json_payload['resolution']
            dataPointCountRatio = json_payload['result'][0]['dataPointCountRatio']
            dimensionCountRatio = json_payload['result'][0]['dimensionCountRatio']
    
            warnings = json_payload['warnings']
            query.warnings.append(warnings)
            logging.warning("%s:warnings in the response:%s", action, warnings)
        except KeyError:
            logging.debug("No warnings in the response") # TODO if data is empty, add warning and zero to value?
        except json.decoder.JSONDecodeError as err:
            if conf.MANAGED_DNS in e.get_tenant_url():
                msg = "Please make sure that you have set the proper Mission Control Cookies 'ssoCSRFCookie' 'JSESSIONID' and you have established a connection to the Cluster via MC"
                logging.error(msg)
                raise Exception(msg)
            else:
                # raise uknown e, handled by wrapper
                raise err
    
        logging.debug("Total Count:%s, response_resolution:%s, dataPointCountRatio:%s, dimensionCountRatio:%s, nextPageKey:%s",totalCount,response_resolution, dataPointCountRatio, dimensionCountRatio, nextPageKey)
        
        if e.resolution != response_resolution:
            warn_msg = "The response resolution of {} does not match the requested resolution {}".format(response_resolution, e.resolution)
            query.warnings.append(warn_msg)
            logging.warning(warn_msg)
    
    else:
        result = str(response.status_code)
        msg = "{} :\t code:{} reason:{}  Content:{}".format( action, result, response.reason, response.content)
        logging.warning(msg)
        # Exception will be handled by the wrapper
        raise Exception(msg)

    logging.debug("%s:%s",action,result)
    logging.debug("%s:%s Content:%s",action, result, str(response.content))

def estimate_podhours(e, podQuery):
    """Function to calculate the pod hours"""

    podQuery.set_response(do_get(e, podQuery.get_query()))

    # Validate response
    validate_query(e, podQuery, "Query [builtin:kubernetes.pods] status")
        

    # Work with the payload
    # TODO Finish the calculation by NS for doing a report
    try:
        total_pod_hours = int(podQuery.get_json_payload()['result'][0]['data'][0]['values'][0])
    except IndexError as err:
        podQuery.warnings.append("No pods in the queried timeframe")
        total_pod_hours = 0

    podQuery.set_total_pod_hours(total_pod_hours)
    return

def fetch_actual_consumption(e, fullstackQuery, fullstackK8sQuery, fullstackApponly):
    """Function to fetch actual DPS FullStack consumption """

    fullstackQuery.set_response(do_get(e, fullstackQuery.get_query()))
    # Validate response
    validate_query(e, fullstackQuery, "Query [builtin:billing.full_stack_monitoring.usage_per_host] status")

    fullstackK8sQuery.set_response(do_get(e, fullstackK8sQuery.get_query()))
    validate_query(e, fullstackK8sQuery, "Query [builtin:billing.full_stack_monitoring.usage_per_host:filter(k8s)] status")

    fullstackApponly.set_response(do_get(e, fullstackApponly.get_query()))
    validate_query(e, fullstackApponly, "Query [builtin:billing.full_stack_monitoring.usage_per_container] status")

    try:
        t_gib_h_fullstack = int(fullstackQuery.get_json_payload()['result'][0]['data'][0]['values'][0])
    except IndexError as err:
        fullstackQuery.warnings.append("No FullStack consumption in the queried timeframe")
        t_gib_h_fullstack = 0
    try:
        t_gib_h_fullstack_k8s = int(fullstackK8sQuery.get_json_payload()['result'][0]['data'][0]['values'][0])
    except IndexError as err:
        fullstackK8sQuery.warnings.append("No FullStack consumption K8s in the queried timeframe")
        t_gib_h_fullstack_k8s = 0
    try:
        t_gib_h_fullstack_apponly = int(fullstackApponly.get_json_payload()['result'][0]['data'][0]['values'][0])
    except IndexError as err:
        fullstackApponly.warnings.append("No FullStack consumption AppOnly in the queried timeframe")
        t_gib_h_fullstack_apponly = 0
    
    e.t_gib_h_fullstack = t_gib_h_fullstack
    e.t_gib_h_fullstack_k8s = t_gib_h_fullstack_k8s
    e.t_gib_h_fullstack_apponly = t_gib_h_fullstack_apponly

    return

def estimate_costs_wrapper(e):
    """Wrapper function for estimate_costs for effective error handling"""
    try:    
        e.set_estimation_running(True)
        logging.info("Calculating estimation for tenant: %s and session %s", e.tenant_url, e.uid)
        
        # All fields will be validated, in an Error an Exception will be raised
        e.validate_form_fields()

        # Run logic for all queries
        estimate_costs(e)
        
        # Everything was ok
        e.set_estimation_running(False)
        
        # No errors
        set_user_cache(e)

    except Exception as err:
        e.set_estimation_running(False)
        e.errors = str(err)
        set_user_cache(e)
        logging.error("There was a %s error: %s", type(err), err)
        return
    return


def estimate_costs(e):

    """Function to estimate the consumption"""
    pod_Queries = []
    mem_Queries = []

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
            
            pod_query = Query(e.get_query_pods_by_ns_dyn() + q_from_dyn + q_to_dyn)
            pod_query.set_date_from(date_from_start)
            pod_query.set_date_to(date_from_end)
            pod_Queries.append(pod_query)

            mem_query = Query(e.get_query_memory_dyn() + q_from_dyn + q_to_dyn)
            mem_query.set_date_from(date_from_start)
            mem_query.set_date_to(date_from_end)
            mem_Queries.append(mem_query)
    else:
        logging.info("Fetching all PGI datapoints from %s until %s in %s resolution", e.from_timeframe, e.to_timeframe, e.resolution)
        # To is static - already embebded in the query string
        date_to = datetime.datetime.strptime(e.to_timeframe, conf.FORMAT_DATE)

        pod_query = Query(e.get_query_pods_by_ns_static())
        pod_query.set_date_from(date_from)
        pod_query.set_date_to(date_to)
        pod_Queries.append(pod_query)
        
        mem_query = Query(e.get_query_memory_static())
        mem_query.set_date_from(date_from)
        mem_query.set_date_to(date_to)
        mem_Queries.append(mem_query)
        logging.debug("From to Query mode activated.")

    # Hack for querying big environments. We can calculate endtime for 0 iterations, 
    # so we skip querying the cluster but still query billing metrics and amount of hosts.
    if e.iterations == 0:
        date_from_end = date_from + datetime.timedelta(days=e.days_per_iteration)
        date_to = date_from_end

    # Calculate again beginning and end for getting actual billing consumption, no iteration, 
    # getting the sum of the whole timeperiod
    q_from = e.q_from + str(int(datetime.datetime.strptime(e.from_timeframe, conf.FORMAT_DATE).timestamp() * 1000))
    q_to = e.q_to + str(int(date_from_end.timestamp() * 1000))
    fullstack_query = Query(e.get_query_fullstack() + q_from + q_to)
    fullstack_k8s_query = Query(e.get_query_fullstack_k8s() + q_from + q_to)
    fullstack_apponly_query = Query(e.get_query_fullstack_apponly() + q_from + q_to)

    # Execute the Queries
    actual_i = len(pod_Queries)

    for i in range(actual_i):
        # Calculate the POD-hours
        pod_query = pod_Queries[i]

        qr = Estimate.QueryResult()
        
        estimate_podhours(e, pod_query)
        
        # Calculate the Gib-hours
        mem_query = mem_Queries[i]
        estimate_memory(e, mem_query)
    
        instances = len(mem_query.get_pgis())
        shortliving_instances = len(mem_query.get_shortliving_pgis())
        percentage_shortliving = 100 * divide(shortliving_instances,instances) 

        date_from = pod_query.get_date_from().strftime(conf.FORMAT_DATE)
        date_to = pod_query.get_date_to().strftime(conf.FORMAT_DATE)
        
        line = "Iteration " + str(i + 1) + " of "+  str(e.iterations) + " with "+str(e.days_per_iteration) +"days - \t"+ date_from + " to " + date_to

        pod_h = pod_query.get_total_pod_hours()
        gib_h = mem_query.get_total_memory()


        # Write to Log and UI
        e.console = e.console + "<br>" + line
        logging.info(line)


        m_podh = "POD-Hours:\t{}".format( f"{pod_h:,}")
        e.console = e.console + "<br>" + m_podh
        logging.info(m_podh)
        if len(pod_query.warnings) > 0:
            logging.warning(str(pod_query.warnings))
            e.console = e.console + "<br>Warning, the previous query is not accurate due:" + str(pod_query.warnings)


        m_gibh = "GiB-Hours:\t{} from {} pod instances".format(f"{gib_h:,}", f"{instances:,}")
        e.console = e.console + "<br>" + m_gibh
        logging.info(m_gibh)
        if len(mem_query.warnings) > 0:
            logging.warning(str(mem_query.warnings))
            e.console = e.console + "<br>Warning, the previous query is not accurate due:" + str(mem_query.warnings)

        m_shortlive = "Shortliving instances:\t{} instances lived under {} vs a total of {} instances equals {} percent".format(f"{shortliving_instances:,}" , e.resolution, f"{instances:,}", ("%.3f" % percentage_shortliving))
        e.console = e.console + "<br>" + m_shortlive
        logging.info(m_shortlive)

        logging.info("")
        e.console = e.console + "<br>"
   
        # SUM Consumption
        e.t_pod_h = e.t_pod_h + pod_h
        e.t_gib_h = e.t_gib_h + gib_h
        e.t_instances = e.t_instances + instances
        e.t_shortliving_instances = e.t_shortliving_instances + shortliving_instances

        qr.instances = instances
        qr.shortliving_instances = shortliving_instances
        qr.percentage_shortliving = percentage_shortliving
        qr.date_from = date_from
        qr.date_to = date_to
        qr.pod_h = pod_h
        qr.gib_h = gib_h

        # Add values to Chart
        e.chart_labels.append(qr.date_to)
        e.chart_values_pod.append(qr.pod_h)
        e.chart_values_gib.append(qr.gib_h)

        e.queryresult.append(qr)
        set_user_cache(e)

    # Fetch the actual FullStack consumption of the Tenant
    fetch_actual_consumption(e, fullstack_query, fullstack_k8s_query, fullstack_apponly_query) 

    # Consumption calculation
    e.k8_costs= e.t_pod_h * e.price_pod_hour
    e.app_costs= e.t_gib_h * e.price_gib_hour
    # Avg Consumption pod-hour
    daily_pod_h = round(divide(e.t_pod_h, ( e.iterations * e.days_per_iteration)))
    year_pod_h = round(daily_pod_h * 365)
    # Avg Consumption Gib-hour
    daily_gib_h = round(divide(e.t_gib_h, ( e.iterations * e.days_per_iteration)))
    year_gib_h = round(daily_gib_h * 365)

    # Avg Total Consumption
    daily_total_gib_h = round(divide(e.t_gib_h_fullstack, ( e.iterations * e.days_per_iteration)))
    year_total_gib_h = round(daily_total_gib_h * 365)

    daily_k8s_total_gib_h = round(divide(e.t_gib_h_fullstack_k8s, ( e.iterations * e.days_per_iteration)))
    year_k8s_total_gib_h = round(daily_k8s_total_gib_h * 365)

    daily_app_total_gib_h = round(divide(e.t_gib_h_fullstack_apponly, ( e.iterations * e.days_per_iteration)))
    year_app_total_gib_h = round(daily_app_total_gib_h * 365)

    year_k8s_app_total_gib_h = year_k8s_total_gib_h + year_app_total_gib_h

    # Projected consumption for the year is total - k8s_from billing - app_only from billing + estimation of all pods 
    projected_total_gib_h = year_total_gib_h  - year_k8s_total_gib_h - year_app_total_gib_h + year_gib_h



    e.console = e.console + "<br>"
    e.console = e.console + "<br>"
    e.console = e.console + "======================== Summary of the estimations ========================<br>"
    e.console = e.console + "Summary of the estimations retrieved from the iterations from {} until {}:<br>".format(e.from_timeframe, date_to)
    e.console = e.console + "<br>"
    e.console = e.console + "Kubernetes Monitoring estimation = {} pod-hours<br>".format(f"{e.t_pod_h:,}")
    e.console = e.console + "- Avg daily estimation of {} pod-hours<br>".format(f"{daily_pod_h:,}")
    e.console = e.console + "- Yearly estimation of {} pod-hours<br>".format(f"{year_pod_h:,}")
    e.console = e.console + "<br>"
    e.console = e.console + "Application Observability estimation = {} Gib-hours<br>".format(f"{e.t_gib_h:,}")
    e.console = e.console + "- Avg daily estimation of {} Gib-hours<br>".format(f"{daily_gib_h:,}")
    e.console = e.console + "- Yearly estimation of {} Gib-hours<br>".format(f"{year_gib_h:,}")
    e.console = e.console + "<br>"
    e.console = e.console + "<br>"
    e.console = e.console + "--------------------------- billing.full_stack_monitoring consumption ---------------------------   <br>"
    e.console = e.console + "Actual consumption gathered from the billing metrics for the same timeframe:<br>"
    e.console = e.console + "<br>"
    e.console = e.console + "Total Fullstack consumption for all hosts is {} Gib-hours.<br>".format(f"{e.t_gib_h_fullstack:,}")
    e.console = e.console + " - Avg daily consumption for all hosts ~ {} Gib-hours.<br>".format(f"{daily_total_gib_h:,}")
    e.console = e.console + " - Yearly consumption for all hosts ~ {} Gib-hours.<br>".format(f"{year_total_gib_h:,}")
    log_console_limited_warning(e,fullstack_query)
    e.console = e.console + "<br>"
    e.console = e.console + "Kubernetes Classic/CloudNative consumption is {} Gib-hours.<br>".format(f"{e.t_gib_h_fullstack_k8s:,}")
    e.console = e.console + " - Avg daily Classic/CloudNative consumption ~ {} Gib-hours.<br>".format(f"{daily_k8s_total_gib_h:,}")
    e.console = e.console + " - Yearly Classic/CloudNative consumption ~ {} Gib-hours.<br>".format(f"{year_k8s_total_gib_h:,}")
    e.console = e.console + " - Represents {}% of the total FullStack consumption.<br>".format(f"{percentage(e.t_gib_h_fullstack_k8s , e.t_gib_h_fullstack):.3f}")
    e.console = e.console + "<br>"
    e.console = e.console + "Application Observability consumption is {} Gib-hours.<br>".format(f"{e.t_gib_h_fullstack_apponly:,}")
    e.console = e.console + " - Avg daily Application Observability consumption ~ {} Gib-hours.<br>".format(f"{daily_app_total_gib_h:,}")
    e.console = e.console + " - Yearly Application Observability ~ {} Gib-hours.<br>".format(f"{year_app_total_gib_h:,}")
    e.console = e.console + " - Represents {}% of the total FullStack consumption.<br>".format(f"{percentage(e.t_gib_h_fullstack_apponly , e.t_gib_h_fullstack ):.3f}")
    e.console = e.console + "<br>"
    e.console = e.console + "Classic/CloudNative + AppOnly yearly consumption ~ {} Gib-hours can decrease by {}% <br>".format(f"{year_k8s_app_total_gib_h:,}", f"{100 - percentage(year_gib_h, year_k8s_app_total_gib_h  ):.3f}")
    e.console = e.console + "<br>"
    e.console = e.console + "<br>"
    e.console = e.console + "<b>--------------------------- Use Cases --------------------------- </b><br>"
    e.console = e.console + "<br>"
    e.console = e.console + "<b>Use Case - stay with Classic/CloudNative </b><br>"
    e.console = e.console + "<br>"
    e.console = e.console + "The yearly consumptions from 'billing.full_stack_monitoring' applies. The billing from Application Observability will be reduced since the consumption is based on average usage and not on the limits of the containers nor host memory.<br>"
    e.console = e.console + "The POD-hours will be included in Classic/CloudNative deployments but this requires a change in the product and it's already in development. If you have any doubt in the DPS Licensing for Kubernetes, please reach out to your field Solution Engineer<br>"
    e.console = e.console + "<br>"
    e.console = e.console + "<br>"
    e.console = e.console + "<b>Use Case - move Classic/CloudNative -> 100% Application Observability</b><br>"
    e.console = e.console + "<br>"
    e.console = e.console + "The estimated yearly consumption for all hosts of ~ {} Gib-hours will be reduced to {} Gib-hours which is a reduction of {}% <br>".format(f"{year_total_gib_h:,}", f"{projected_total_gib_h:,}", f"{100 - percentage(projected_total_gib_h, year_total_gib_h):.3f}" )
    e.console = e.console + "Application Observability yearly estimation of ~ {} Gib-hours<br>".format(f"{year_gib_h:,}")
    e.console = e.console + "Kubernetes Observability yearly estimation of ~ {} Pod-hours<br>".format(f"{year_pod_h:,}")
    e.console = e.console + "<br>"
    e.console = e.console + "Be aware that for this change to take effect, the deployment needs to be changed in every cluster.<br> "
    e.console = e.console + "Some infrastructure metrics of the ClusterNodes will be missing and the Log Module needs to be configured."
    e.console = e.console + "<br>"
    e.console = e.console + "<br>"
    log_console_limited_warning(e,fullstack_apponly_query)

    logging.info("Kubernetes Monitoring estimation from %s to %s = %s pod-hours", e.from_timeframe, date_to, f"{e.t_pod_h:,}")
    logging.info("")
    logging.info("Application Observability estimation from %s to %s = %s Gib-hours", e.from_timeframe, date_to, f"{e.t_gib_h:,}")
    logging.info("")

    return 

def log_console_limited_warning(estimate, query):
    if len(query.warnings) > 0 and "limited" in str(query.warnings):
        estimate.console = estimate.console + "Warning, the above consumption is not accurate due dimension limits!<br>"

def percentage(part , whole):
    """ Function to return a percentage, handles also div by zero"""
    try:
        return 100 * ( divide(part, whole)) 
    except ZeroDivisionError: 
        return 0
    
def divide(part , whole):
    """ function to handle division by Zero, returns Zero if whole is 0"""
    return float(part) / float(whole) if whole else 0


def estimate_memory(e, memQuery):
    """ Function to estimate the Gib-hour consumption"""
    # pgis, total_memory, shortliving_pgis
    memQuery.set_response(do_get(e, memQuery.get_query()))

    # Validate response
    validate_query(e, memQuery, "Query [builtin:tech.generic.mem.workingSetSize] status")
    
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

    if not pgis:
         memQuery.warnings.append("No pods have been instrumented in the specified timeframe.")

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
        print("\nDone calculating consumption... have a nice day")
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