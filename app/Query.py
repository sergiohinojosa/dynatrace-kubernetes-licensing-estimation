class Query:

    def __init__(self, query):
        self.query = query
        self.response = {}
        self.json_payload = {}
        self.warnings = []
        self.pgis = {}
        self.shortliving_pgis = []
        self.total_memory = 0
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