import base64
import json
import socket

import faust
import pandas as pd
import requests
import torch
from deepod.models.tabular import DeepSVDD
from google.protobuf.internal.decoder import _DecodeVarint32
from google.protobuf.json_format import MessageToJson
from matplotlib import pyplot as plt
from mpl_toolkits.basemap import Basemap
from sklearn.preprocessing import StandardScaler

import flow_pb2

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
scaler = StandardScaler()

app = faust.App('geo-anomaly-detection', broker='kafka://kafka:9092', value_serializer='raw', producer_compression_type='lz4')
malfix_topic = app.topic('malfix')

json_flows: list = []


def draw_map(lats_lons):
    plt.figure(figsize=(10, 7))

    m = Basemap(projection='merc', llcrnrlat=-60, urcrnrlat=85,
                llcrnrlon=-180, urcrnrlon=180, resolution='c')

    m.drawcoastlines()
    m.drawcountries()
    m.drawmapboundary(fill_color='aqua')
    m.fillcontinents(color='lightgray', lake_color='aqua')

    x, y = zip(*[m(entry['lon'], entry['lat']) for entry in lats_lons])

    m.scatter(x, y, marker='o', color='red', zorder=5)

    plt.title('World Map with Latitude and Longitude Points')
    plt.show()


def bytes_to_ip(base_str):
    byte_str = base64.b64decode(base_str)
    if len(byte_str) == 4:
        return socket.inet_ntoa(bytes(byte_str))
    elif len(byte_str) == 16:
        return socket.inet_ntop(socket.AF_INET6, bytes(byte_str))
    else:
        raise ValueError("Invalid byte length for IP address")


@app.agent(malfix_topic)
async def process(flows: faust.Stream) -> None:
    async for flow in flows:
        index = 0
        msg_len, new_pos = _DecodeVarint32(flow, index)
        index += new_pos  # Move the index past the varint
        flow_message_bytes = flow[index:index + msg_len]
        flow_pb = flow_pb2.FlowMessage()
        flow_pb.ParseFromString(flow_message_bytes)
        print(MessageToJson(flow_pb))
        json_flows.append(MessageToJson(flow_pb))


def ips_to_lat_lon(ips):
    lat_lon = []
    try:
        response = requests.post(f"http://ip-api.com/batch?fields=status,lat,lon,as", json=ips)
        lat_lon = response.json()
    except Exception as e:
        print(e)
    return [{"lat": geo["lat"], "lon": geo["lon"]} if geo['status'] != 'fail' else {"lat": 48.525243146351485,
                                                                                    "lon": 9.060386676924153} for
            geo in lat_lon]


@app.timer(interval=1.0)
async def every_1_seconds():
    return
    parsed_data = [json.loads(record) for record in json_flows]
    ip_geo_list = []

    for record in parsed_data:
        record['srcAddr'] = bytes_to_ip(record['srcAddr'])
        record['dstAddr'] = bytes_to_ip(record['dstAddr'])
        record['samplerAddress'] = bytes_to_ip(record['samplerAddress'])

    for i in range(0, len(parsed_data), 100):
        ip_geo_list.extend(ips_to_lat_lon([record['dstAddr'] for record in parsed_data[i:i + 100]]))

    draw_map(ip_geo_list)
    df_lat_long = pd.DataFrame(ip_geo_list).values

    clf = DeepSVDD(device=device)

    clf.fit(df_lat_long, y=None)

    test = clf.decision_function(
        pd.DataFrame(ips_to_lat_lon(
            ["172.221.121.1", "101.96.128.0", "116.172.130.191", "207.148.5.58", "106.52.103.154"])).values)
    draw_map(ips_to_lat_lon(["172.221.121.1", "101.96.128.0", "116.172.130.191", "207.148.5.58", "106.52.103.154"]))
    print(test)


app.main()
