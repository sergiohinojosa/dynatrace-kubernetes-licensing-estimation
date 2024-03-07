# -*- coding: utf-8 -*-
# Required Libraries.
import json
import logging
import os
import sys
import traceback
import requests


# Read Configuration and assign the variables
config = json.load(open('config.json'))


LOG_FILE = config['log_file']
LOG_DIR = config['log_dir']

TENANT_URL = config['tenant_url']
API_TOKEN = config['api_token']


class EmptyResponse:
    status_code = 500
    reason = 'Unkown'
    content = 'Empty'

def check_create_dir(dir_name):
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

# Logging configuration
# Create log directory at initialization
check_create_dir(LOG_DIR)

# Initialize logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', filename=LOG_DIR + '/' + LOG_FILE,
                    level=logging.DEBUG)

# Add logging also to the console of the running program
logging.getLogger().addHandler(logging.StreamHandler())

def getHeaderJson():
    return {'content-type': 'application/json'}

def getHeader():
    return {'content-type': 'application/json', "Authorization": "Api-Token " + API_TOKEN}

def verifyRequest():
    return True

def do_get(endpoint):
    response = requests.get(TENANT_URL + endpoint, headers=getHeader(), verify=verifyRequest())
    logging.debug('GET Reponse content: ' +
                  str(response.content) + '-' + endpoint)
    return response


def action_create():

    logging.info("-----------DOGET------------------------")
    response = do_get("/api/v2/entities?entitySelector=type(PROCESS_GROUP_INSTANCE),toRelationships.runsOnProcessGroupInstance(type(SERVICE),agentTechnologyType.exists())")


    return 


def main():
    try:
        printUsage = False

        logging.info("----------------------------------------------")
        logging.info("Starting Dynatrace Kubernetes License Estimation\n")

        action_create()

        if len(sys.argv) >= 2:
            command = sys.argv[1]

            if command == 'validate':
                logging.info("====== Validate action called ======")
                saveResults = True

            elif command == 'test':
                logging.info("====== Test action called ======")
                saveResults = True

            elif command == 'help':
                printUsage = True

            elif command == 'validate':
                logging.info(
                    "====== Validating configuration and users ======")
                #do_validate()
                printUsage = False

            else:
                logging.warning("Command not recognized:" + command)
                printUsage = True

            if saveResults:
                logging.info("====== Save Results? ======")
        else:
            logging.warning("You need to give at least one argument")
            printUsage = True

    except Exception as e:  # catch all exceptions
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logging.error(traceback.print_exc())
        traceback.print_exc()
        # Save it in object
        #save_json(DATA_DIR, "error-results", CSV_DATA)
        # Write Backup
        #save_results(CSV_TEMP_DIR + '/error-' +
         #            getNowAsString() + '-' + CSV_FILE)

    if printUsage:
        doUsage(sys.argv)
    else:
        print("\nDone automating... have a nice day")
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

