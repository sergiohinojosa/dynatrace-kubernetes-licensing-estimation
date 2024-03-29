import logging
from app import Estimate as conf

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
    
    def set_memory(self, memory, resolution):
        """ Method for rounding and calculating the memory_total based on the amount of datapoints (count). 
        The memory is rounded by the next MIN_MEMORY which is 0.025 GiB"""
        self.memory = memory

        if memory < conf.MIN_MEMORY:
            self.memory_rounded = conf.MIN_MEMORY
        else:
            # floor division
            dividend = memory // conf.MIN_MEMORY
            self.memory_rounded = dividend * conf.MIN_MEMORY

            # If we have remainders we increase to next round up
            if (memory % conf.MIN_MEMORY) > 0:
                self.memory_rounded = self.memory_rounded + conf.MIN_MEMORY

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

