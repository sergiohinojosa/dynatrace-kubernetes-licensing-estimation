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

# POD-hour calculation as per doc
# https://docs.dynatrace.com/docs/shortlink/dps-containers#billing-granularity-for-pod-hour-consumption

# GiBHour calculation  
# https://docs.dynatrace.com/docs/manage/subscriptions-and-licensing/dynatrace-platform-subscription/host-monitoring#gib-hour-calculation-for-containers-and-application-only-monitoring


class QueryResult:
    def __init__(self):
        self.instances = 0
        self.shortliving_instances = 0
        self.percentage_shortliving = 0
        self.date_from = ""
        self.date_to = ""
        self.pod_h = 0
        self.gib_h = 0
        self.warning = []
        self.resolution = ""


class Estimate:

    def __init__(self, tenant_url, api_token, uid):
        self.tenant_url = tenant_url
        self.api_token = api_token
        self.uid = uid
        self.estimation_running = False
        
        # QueryResults
        self.queryresult = []

        # Managed Vars
        self.ssoCSRFCookie = ""
        self.jsessionId = ""

        # Runtime
        self.iterative_query = True
        self.from_timeframe = "2024-05-01"
        self.to_timeframe = "2024-05-31"
        self.iterations = 4
        self.days_per_iteration = 7

        # Config
        self.unit= "GibiByte"
        self.resolution = "1h"
        self.price_pod_hour = 0.002
        self.price_gib_hour = 0.01

        # K8s Env vars
        self.inside_vpn = False
        self.release_version = "0.0"
        self.pod_name = "pod_name"
        self.pod_namespace = "namespace"
        self.node_name = "node_name"

        # FullStack Consumption
        self.t_gib_h_fullstack = 0
        self.t_gib_h_fullstack_k8s = 0
        self.t_gib_h_fullstack_apponly = 0

        # Results
        self.t_pod_h = 0
        self.t_gib_h = 0
        self.t_instances = 0
        self.t_shortliving_instances = 0

        self.k8_costs = 0
        self.app_costs = 0
        self.errors = ""
        self.console = ""

        # Charting 
        self.chart_labels = []
        self.chart_values_pod = []
        self.chart_values_gib = []

        # Dynamic Query
        # API V2 Endpoint for metric selection
        self.q_metric_selector_endpoint="/api/v2/metrics/query?metricSelector="

        self.q_condition_k8s_host="""or(
        in("dt.entity.host",entitySelector("type(HOST),softwareTechnologies(KUBERNETES)")),
        in("dt.entity.host",entitySelector("type(HOST),paasVendorType(KUBERNETES)")),
        in("dt.entity.host",entitySelector("type(HOST),paasVendorType(OPENSHIFT)")
        ))))
        """
        
        # Query to fetch the avg size of K8s PGIs and the ammount of datapoints with a 
        # 15m resolution  
        ## TODO Refactor the k8s condition
        self.q_k8s_filter = """:filter(and(
        or(
        in("dt.entity.host",entitySelector("type(HOST),softwareTechnologies(KUBERNETES)")),
        in("dt.entity.host",entitySelector("type(HOST),paasVendorType(KUBERNETES)")),
        in("dt.entity.host",entitySelector("type(HOST),paasVendorType(OPENSHIFT)")
        ))))"""

        self.query_body="""
        builtin:tech.generic.mem.workingSetSize:parents:filter(
        and(
        in("dt.entity.process_group_instance",entitySelector("type(PROCESS_GROUP_INSTANCE),
        toRelationships.runsOnProcessGroupInstance(type(SERVICE),agentTechnologyType.exists())")),
        or(
        in("dt.entity.host",entitySelector("type(HOST),softwareTechnologies(KUBERNETES)")),
        in("dt.entity.host",entitySelector("type(HOST),paasVendorType(KUBERNETES)")),
        in("dt.entity.host",entitySelector("type(HOST),paasVendorType(OPENSHIFT)")
        ))))
        :splitBy("dt.entity.process_group_instance"):count:fold(sum):sort(value(sum,ascending)),
        builtin:tech.generic.mem.workingSetSize:parents:filter(
        and(
        in("dt.entity.process_group_instance",entitySelector("type(PROCESS_GROUP_INSTANCE),
        toRelationships.runsOnProcessGroupInstance(type(SERVICE),agentTechnologyType.exists())")),
        or(
        in("dt.entity.host",entitySelector("type(HOST),softwareTechnologies(KUBERNETES)")),
        in("dt.entity.host",entitySelector("type(HOST),paasVendorType(KUBERNETES)")),
        in("dt.entity.host",entitySelector("type(HOST),paasVendorType(OPENSHIFT)")))))
        :splitBy("dt.entity.process_group_instance"):avg:fold(avg):sort(value(avg,ascending))
        """

        self.q_to_unit=":toUnit(Byte," + self.unit + ")"

        self.q_fullstack_k8s = """builtin:billing.full_stack_monitoring.usage_per_host:filter(and(
        in("dt.entity.host",entitySelector("type(HOST),softwareTechnologies(KUBERNETES)"))
        )):splitBy():splitBy():sum:fold(value)"""

        self.q_fullstack = "builtin:billing.full_stack_monitoring.usage:splitBy():sum:fold(value)"

        self.q_fullstack_apponly = "builtin:billing.full_stack_monitoring.usage_per_container:splitBy():sum:fold(value)"
        
        self.q_resolution_1h="&resolution=1h"
        self.q_from="&from=" 
        self.q_from_t = self.q_from + self.from_timeframe
        self.q_to="&to="
        self.q_to_t= self.q_to + self.to_timeframe
        self.q_podhour_metric = "builtin:kubernetes.pods:splitBy():sum:fold(value)"

    
    def get_query_fullstack_apponly(self):
        return self.q_metric_selector_endpoint +  self.q_fullstack_apponly 
    
    def get_query_fullstack_k8s(self):
        return self.q_metric_selector_endpoint +  self.q_fullstack_k8s 
    
    def get_query_fullstack(self):
        return self.q_metric_selector_endpoint +  self.q_fullstack 

    # Put the parametrized Query together
    def get_query_pods_by_ns_static(self):
        return self.q_metric_selector_endpoint +  self.q_podhour_metric + self.q_resolution_1h + self.q_from_t + self.q_to_t 

    # Put the parametrized Query together
    def get_query_memory_static(self):
        return self.q_metric_selector_endpoint + self.query_body + self.q_to_unit +  self.get_q_resolution() + self.q_from_t + self.q_to_t 

    def get_query_pods_by_ns_dyn(self):
        return self.q_metric_selector_endpoint +  self.q_podhour_metric + self.q_resolution_1h 
    
    def get_query_memory_dyn(self):
        return self.q_metric_selector_endpoint + self.query_body + self.q_to_unit + self.get_q_resolution()
    
    def get_q_resolution(self):
        return "&resolution=" + self.resolution
    
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


    def validate_form_fields(self):

        if not ("https://") in self.tenant_url:
            raise SyntaxWarning("Tenant URL needs to contain HTTPS")
        
        if ("apps.dynatrace.com") in self.tenant_url:
            raise SyntaxWarning("Please change the Tenant URL subdomain 'apps' -> 'live'")
        
        if not any(value in self.tenant_url for value in ('.live.dynatrace.com' or '.sprint.dynatracelabs.com' or 'managed.internal.dynatrace.com')):
            raise SyntaxWarning("Tenant URL does not contain a valid (sub)domain for querying the API. See the documentation.")

        if self.tenant_url.endswith('/'):
            self.tenant_url = self.tenant_url.strip('/')

        if not any(value in self.resolution for value in('15m', '1h' , '6h',  '1d')):
            raise SyntaxWarning("Valid resolution tipes are 15m, 1h, 6h, 1d")
        
        if not ("dt0c01.") in self.api_token:
            raise SyntaxWarning("API Token does not contain a valid format")
       
        if self.iterations >= 30:
            raise SyntaxWarning("Really? Do you want to iterate more than 30 times?")
    
        if self.iterations > 0 and self.days_per_iteration >= 31:
            raise SyntaxWarning("Really? Do you want to iterate more than 31 days per iteration?")
        