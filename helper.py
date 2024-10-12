import base64
import socket
from mpl_toolkits.basemap import Basemap
import matplotlib.pyplot as plt
from collections import Counter

def bytes_to_ip(base_str):
    byte_str = base64.b64decode(base_str)
    if len(byte_str) == 4:
        return socket.inet_ntoa(bytes(byte_str))
    elif len(byte_str) == 16:
        return socket.inet_ntop(socket.AF_INET6, bytes(byte_str))
    else:
        raise ValueError("Invalid byte length for IP address")



def draw_map(flows, predictions, max_size=500):
    # Separate inliners and outliners
    outliner = []
    inliner = []
    for idx, flow in enumerate(flows):
        if predictions[idx] == 1:
            inliner.append(flow)
        else:
            outliner.append(flow)

    # Create a dictionary to count occurrences of each coordinate (longitude, latitude)
    def get_coordinates(flows):
        return [(entry['geo']['longitude'], entry['geo']['latitude']) for entry in flows]

    inliner_coords = get_coordinates(inliner)
    outliner_coords = get_coordinates(outliner)

    # Count occurrences of each coordinate
    inliner_count = Counter(inliner_coords)
    outliner_count = Counter(outliner_coords)

    # Set up the map
    plt.figure(figsize=(12, 8))

    m = Basemap(projection='merc', llcrnrlat=-60, urcrnrlat=85,
                llcrnrlon=-180, urcrnrlon=180, resolution='i')

    m.drawcoastlines(linewidth=0.5, antialiased=True)
    m.drawcountries(linewidth=0.5, antialiased=True)
    m.drawmapboundary(fill_color='aqua')
    m.fillcontinents(color='lightgray', lake_color='aqua', zorder=1)

    # Plot inliners with size based on occurrence and capped at max_size
    for (lon, lat), count in inliner_count.items():
        x, y = m(lon, lat)
        marker_size = min(5 + count * 3, max_size)  # Set a max size for the markers
        m.scatter(x, y, marker='o', color='blue', s=marker_size, zorder=5, alpha=0.7)

    # Plot outliners with size based on occurrence and capped at max_size
    for (lon, lat), count in outliner_count.items():
        x, y = m(lon, lat)
        marker_size = min(5 + count * 3, max_size)  # Set a max size for the markers
        m.scatter(x, y, marker='o', color='red', s=marker_size, zorder=5, alpha=0.7)

    plt.title('World Map with Latitude and Longitude Points (Size = Frequency, Max Size Capped)')
    plt.tight_layout()
    plt.show()


def geo_to_lat_long(geo):
    return [geo['latitude'], geo['longitude']]