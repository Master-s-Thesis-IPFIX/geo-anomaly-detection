import json
import faust
from google.protobuf.internal.decoder import _DecodeVarint32
from google.protobuf.json_format import MessageToJson
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

import flow_pb2
from IP2Geo import IP2Geo
from helper import bytes_to_ip, draw_map, geo_to_lat_long

app = faust.App('geo-anomaly-detection', broker='kafka://kafka:9092', producer_compression_type='lz4')
malfix_topic = app.topic('malfix', value_serializer='raw')
geo_anomaly_topic = app.topic('ipfix_geo_data_anomaly', value_serializer='json')
geo_topic = app.topic('ipfix_geo_data', value_serializer='json')

json_flows: list = []

geo_ip = IP2Geo()
geo_ip.load_geoip_db()

scaler = StandardScaler()

iforest = IsolationForest(n_estimators=200,contamination=0.1, random_state=42, max_features=2)
enable_map=False
initial_training_finished = False
@app.agent(malfix_topic)
async def process(flows: faust.Stream) -> None:
    global initial_training_finished
    async for flow in flows:
        index = 0
        msg_len, new_pos = _DecodeVarint32(flow, index)
        index += new_pos  # Move the index past the varint
        flow_message_bytes = flow[index:index + msg_len]
        flow_pb = flow_pb2.FlowMessage()
        flow_pb.ParseFromString(flow_message_bytes)

        record = json.loads(MessageToJson(flow_pb))
        record['srcAddr'] = bytes_to_ip(record['srcAddr'])
        record['dstAddr'] = bytes_to_ip(record['dstAddr'])
        record['samplerAddress'] = bytes_to_ip(record['samplerAddress'])

        src_geo = geo_ip.find_ip_entry(record['srcAddr'])
        dst_geo = geo_ip.find_ip_entry(record['dstAddr'])

        record['src_geo'] = src_geo
        record['dst_geo'] = dst_geo

        await geo_topic.send(value=record)
        if initial_training_finished:
            geos = [geo_to_lat_long(geo) for geo in [src_geo, dst_geo] if geo is not None]

            if len(geos) > 0:
                predictions = iforest.predict(scaler.fit_transform(geos))
                if -1 in predictions:
                    await geo_anomaly_topic.send(value=record)

        json_flows.append(record)

@app.timer(interval=60*60*24)
async def clear():
    json_flows.clear()

@app.timer(interval=30)
async def train():
    global initial_training_finished, iforest
    if len(json_flows) < 1:
        return
    remote_flows = []
    for flow in json_flows:
        if flow['dst_geo'] is not None:
            flow['geo'] = flow['dst_geo']
            remote_flows.append(flow)
        if flow['src_geo'] is not None:
            flow['geo'] = flow['src_geo']
            remote_flows.append(flow)
    print(len(remote_flows))
    if len(remote_flows) > 1000:
        geo_data = [geo_to_lat_long(flow['geo']) for flow in remote_flows]
        iforest.fit(scaler.fit_transform(geo_data))
        initial_training_finished=True
        if enable_map:
            draw_map(remote_flows, iforest.predict(scaler.fit_transform(geo_data)))

app.main()
