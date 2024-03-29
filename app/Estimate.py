#TODO extract variables and constants
import json

MIN_MEMORY = 0.25

MANAGED_DNS = "managed.internal.dynatrace"
FORMAT_DATE = '%Y-%m-%d'

# Read Configuration and assign the variables
#config = json.load(open('config.json'))

LOG_FILE = "estimate.log"
LOG_DIR = "log"
REPORT_DIR = "report"


  
# declaringa a class
class obj:
    
    # constructor
    def __init__(self, dict1):
        self.__dict__.update(dict1)

  
def dict2obj(dict1):
     
    # using json.loads method and passing json.dumps
    # method and custom object hook as arguments
    return json.loads(json.dumps(dict1), object_hook=obj)



# POD-hour calculation as per doc
# https://docs.dynatrace.com/docs/shortlink/dps-containers#billing-granularity-for-pod-hour-consumption

# GiBHour calculation  
# https://docs.dynatrace.com/docs/manage/subscriptions-and-licensing/dynatrace-platform-subscription/host-monitoring#gib-hour-calculation-for-containers-and-application-only-monitoring


class Estimate:

    def __init__(self, tenant_url, api_token):
        self.tenant_url = tenant_url
        self.api_token = api_token
        self.estimation_running = False
        
        # Managed Vars
        self.ssoCSRFCookie = "xxx"
        self.jsessionId = "xxx"

        # Runtime
        self.iterative_query = True
        self.from_timeframe = "2024-02-01"
        self.to_timeframe = "2024-02-29"
        self.iterations = 4
        self.days_per_iteration = 7

        # Config
        self.unit= "GibiByte"
        self.resolution = "1h"
        self.price_pod_hour = 0.002
        self.price_gib_hour = 0.01

        # Results
        self.t_pod_h = 0
        self.t_gib_h = 0
        self.t_instances = 0
        self.t_shortliving_instances = 0

        self.k8_costs = 0
        self.app_costs = 0

        # Dynamic Query
        # API V2 Endpoint for metric selection
        self.q_metric_selector_endpoint="/api/v2/metrics/query?metricSelector="
        #
        # Query to fetch the avg size of K8s PGIs and the ammount of datapoints with a 
        # 15m resolution 
        self.query_body="""
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
        self.q_to_unit=":toUnit(Byte," + self.unit + ")"
        self.q_resolution="&resolution="+ self.resolution
        self.q_resolution_1h="&resolution=1h"
        self.q_from="&from=" 
        self.q_from_t = self.q_from + self.from_timeframe
        self.q_to="&to="
        self.q_to_t= self.q_to + self.to_timeframe
        self.q_podhour_metric = "builtin:kubernetes.pods:splitBy():sum:fold(value)"

        # Put the parametrized Query together
        self.query_pods_by_ns_static = self.q_metric_selector_endpoint +  self.q_podhour_metric + self.q_resolution_1h + self.q_from_t + self.q_to_t 
        self.query_pods_by_ns_dyn = self.q_metric_selector_endpoint +  self.q_podhour_metric + self.q_resolution_1h 

        # Put the parametrized Query together
        self.query_memory_static = self.q_metric_selector_endpoint + self.query_body + self.q_to_unit + self.q_resolution + self.q_from_t + self.q_to_t 
        self.query_memory_dyn = self.q_metric_selector_endpoint + self.query_body + self.q_to_unit + self.q_resolution  



    def get_tenant_url(self):
        return self.tenant_url
    
    def set_tenant_url(self, tenant_url):
        self.tenant_url = tenant_url

    def get_api_token(self):
        return self.api_token
    
    def set_api_token(self, api_token):
        self.api_token = api_token

    def is_estimation_running(self):
        return self.estimation_running
    
    def set_estimation_running(self, estimation_running):
        self.estimation_running = estimation_running

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, 
            sort_keys=True, indent=4)

    def get_ssoCSRFCookie(self):
        return self.ssoCSRFCookie
        
    def get_jsessionId(self):
        return self.jsessionId
        
    def set_ssoCSRFCookie(self, ssoCSRFCookie):
        self.ssoCSRFCookie = ssoCSRFCookie
        
    def set_jsessionId(self, jsessionId):
        self.jsessionId = jsessionId