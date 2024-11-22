import random, time, math

def generate_mac_address():
    mac_address = [random.randint(0x00, 0xff) for _ in range(5)]
    mac_address.insert(0,170)
    return ':'.join('{:02x}'.format(byte) for byte in mac_address)

class Step:
    def __init__(self):
        self.counter = 1.0

    def add(self):
        int_part = int(self.counter)
        if self.counter - int_part > 0 :
           self.counter = int_part
           self.counter += 1
           result = self.counter
        else:            
           result = self.counter
           self.counter += 1 
        return result

    def add_minor(self):
        self.counter += 0.1
        return self.counter


class MacAddressGenerator:
    def __init__(self):
        self.prefix = "00:a9:00:00:00:00"
        self.counter = 2  # Initialize the counter with 2

    def generate_mac_address(self):
        mac_address = f"{self.prefix[:-5]}{self.counter:02X}:{self.counter:02X}"
        self.counter += 1
        if self.counter > 255:
            raise StopIteration("No more unique MAC addresses available")
        return mac_address

    def __iter__(self):
        return self

    def __next__(self):
        return self.generate_mac_address()

def is_reserved_mac(mac_address) -> bool:
    reserved_prefixes = ['01:00:5e', '33:33', '00:00:00', '01:08:C2', '00:01:FF', '00:02:FF']
    for prefix in reserved_prefixes:
        if mac_address.startswith(prefix):
            return True
    return False

def generate_unique_mac_list(num_addresses):
    mac_list = set()
    while len(mac_list) < num_addresses:
        mac_address = generate_mac_address()
        if not is_reserved_mac(mac_address):
            mac_list.add(mac_address)
    return list(mac_list)


## Class used for storage of test variables - Seeing here as example, but most of them will be re-assigned by the user input
class testVars: pass


def expand_time_abbreviation(abbreviation) -> str :
    abbreviations = {
        'ms' : 'milliseconds',
        'msec' : 'milliseconds',
        'sec': 'seconds',
        's': 'seconds',
        'ns' : 'nanoseconds',
        'nsec' : 'nanoseconds',
        'us' : 'microseconds'
    }
    return abbreviations.get(abbreviation, 'Unknown abbreviation')

def convert_to_nanoseconds(value : str, unit : int) -> int:
    units = {
        'ns': 1,
        'nsec' : 1,
        'us': 1000,
        'ms': 1000 * 1000,
        'msec' : 1000 * 1000,
        'sec': 1000 * 1000 * 1000,
        's': 1000 * 1000 * 1000,
        'min': 1000 * 1000 * 1000 * 60,
        'hr': 1000 * 1000 * 1000 * 60 * 60,
        'day': 1000 * 1000 * 1000 * 60 * 60 * 24
        # Add more units and conversion factors as needed
    }

    if unit in units:
        conversion_factor = units[unit]
        nanoseconds = value * conversion_factor
        return nanoseconds
    else:
        return "Invalid unit of time."
    
def _myRun(ixNet,logStatus : bool = True):
        """Take in IxNework session and waits for traffic to be in running state"""
        preventInfLoop = 30        
        ixNet.Traffic.Start()        
        trafficNotRunnning = True
        while trafficNotRunnning: 
            currentTrafficState = ixNet.Traffic.State
            if logStatus:
                ixNet.info('Currently traffic is in ' + currentTrafficState + ' state')
            if currentTrafficState == 'started': 
                trafficNotRunnning = False
            time.sleep(2)
            preventInfLoop -= 2
            if preventInfLoop < 1: 
                return False
        return True

def checkTrafficState(ixNet, state, logStatus : bool = True):
        pleaseWait = True
        preventInfLoop = 60
        while pleaseWait: 
            currentTrafficState = ixNet.Traffic.State
            if logStatus:
                ixNet.info('Currently traffic is in ' + currentTrafficState + ' state')
            if currentTrafficState == state: 
                pleaseWait = False
            else:
                time.sleep(2)
            
            preventInfLoop -= 2
            if preventInfLoop < 1: 
                return False
        return True

def compare_numbers(num1, num2, thresholdNum = 0.99):
    threshold = thresholdNum
    difference = abs(num1 - num2)
    avg = (num1 + num2) / 2
    percent_difference = difference / avg
    
    if percent_difference <= (1 - threshold):
        return True
    else:
        return False
    
def getPktsPerSecond(packet_size_in_bytes : int = 100, preamble_size : int = 8, intergap_size : int = 12, transmission_rate_in_Mbps : int = 10_000):
    #bps per second = Megabits per second x 1,000,000
    bps_per_second = transmission_rate_in_Mbps * 1_000_000
    # Full Pkt 
    frameSize = packet_size_in_bytes + preamble_size + intergap_size
    frameSizeInBits = frameSize * 8 
    # Packets per Second   
    packets_per_second = bps_per_second / frameSizeInBits
    print("Packets per second:", packets_per_second)
    return packets_per_second

def getPktsPerDuration(packet_size_in_bytes : int = 100, preamble_size : int = 8, intergap_size : int = 12, total_time_in_us : int = 300, transmission_rate_in_Mbps : int = 10_000):
    pktPerSec = getPktsPerSecond(packet_size_in_bytes, preamble_size, intergap_size, transmission_rate_in_Mbps)
    return  math.floor( (pktPerSec * total_time_in_us) / 1_000_000)
        
def find_key_with_word(dictionary, word):
    for key in dictionary:
        if word in key:
            return key
    return None

def getNanoSeconds(dateVal:str):
    date_components = dateVal.split()
    time_with_fractional_seconds = date_components[1]
    # Split the string by the ':' character to extract the seconds part
    seconds_part = time_with_fractional_seconds.split(':')[2]
    # Split the string by the '.' character
    seconds, nanoseconds = seconds_part.split('.')
    # Convert seconds to nanoseconds and add nanoseconds
    total_nanoseconds = int(seconds) * 10**9 + int(nanoseconds)
    return total_nanoseconds
