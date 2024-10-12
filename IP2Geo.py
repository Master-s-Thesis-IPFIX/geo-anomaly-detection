import bisect
import csv
import ipaddress


def ip_to_int(ip):
    try:
        if len(ip) > 15:
            return int(ipaddress.IPv6Address(ip))
        else:
            return int(ipaddress.IPv4Address(ip))
    except:
        return int(ipaddress.IPv4Address('0.0.0.0'))


class IP2Geo:
    def __init__(self):
        self._v4file_path = 'IP2LOCATION-LITE-DB5.CSV'
        self._v6file_path = 'IP2LOCATION-LITE-DB5.IPV6.CSV'
        self._database = None
        self._start_ips = None

    def load_geoip_db(self):
        keys = ["start_ip", "end_ip", "country_code", "country", "region", "city", "latitude", "longitude"]

        entries = []
        with open(self._v4file_path, mode='r') as file:
            csv_reader = csv.reader(file)
            for row in csv_reader:
                entry = dict(zip(keys, row))
                entries.append(entry)
        with open(self._v6file_path, mode='r') as file:
            csv_reader = csv.reader(file)
            for row in csv_reader:
                entry = dict(zip(keys, row))
                entries.append(entry)

        for entry in entries:
            entry['start_ip'] = int(entry['start_ip'])
            entry['end_ip'] = int(entry['end_ip'])
            entry['latitude'] = float(entry['latitude'])
            entry['longitude'] = float(entry['longitude'])
        self._database = entries
        self._preprocess_entries()

    def _preprocess_entries(self):
        self._database.sort(key=lambda x: int(x['start_ip']))
        self._start_ips = [int(entry['start_ip']) for entry in self._database]

    def find_ip_entry(self, ip_number):
        ip_number = ip_to_int(ip_number)
        idx = bisect.bisect_right(self._start_ips, ip_number) - 1


        if idx >= 0 and int(self._database[idx]['start_ip']) <= ip_number <= int(self._database[idx]['end_ip']):
            potential_lat = self._database[idx]['latitude']
            potential_long = self._database[idx]['longitude']
            if not (potential_lat == 0 and potential_long == 0):
                return self._database[idx]
        return None