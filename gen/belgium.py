# {"version":"1.3","timestamp":"1755002972","station":[   {
#       "@id": "http://irail.be/stations/NMBS/008883212",
#       "id": "BE.NMBS.008883212",
#       "name": "Écaussinnes",
#       "locationX": "4.156639",
#       "locationY": "50.56239",
#       "standardname": "Écaussinnes"
#     }
#   ]}
# 
#   to
# 
#  {"type": "node", "id": "ATN", "lat": 51.921326524551, "lon": 6.5786272287369, "tags": {"name": "Aalten", "uic": "8400045", "name_short": "Aalten", "name_medium": "Aalten", "slug": "aalten", "type": "stoptreinstation"}, "category": "netherlands_all"}

import json
import sys
import requests

output = []

endpoint = "https://api.irail.be/stations/?format=json&lang=en"

print("Fetching stations from iRail...")

data = json.loads(requests.get(endpoint).text)
# GET /stations/?format=json&lang=en

stations = data['station']
for station in stations:
    if 'standardname' not in station:
        raise ValueError("Missing 'standardname' in station data")
    if 'locationX' not in station or 'locationY' not in station:
        raise ValueError("Missing 'locationX' or 'locationY' in station data")
    if 'id' not in station:
        raise ValueError("Missing 'id' in station data")

    output.append({
        "type": "node",
        "id": station['id'],
        "lat": float(station['locationY']),
        "lon": float(station['locationX']),
        "tags": {
            "name": station['standardname'],
        },
        "category": "belgium_all"
    })

excludes = "../changes/excluded-belgium.json"
to_remove = set()
with open(excludes, 'r', encoding='utf-8') as f:
    # Assume same format as output
    for line in f:
        __id = json.loads(line)['id']
        to_remove.add(__id)

output_sorted = sorted(output, key=lambda x: x['tags']['name'])

output_file = "../nodes/nodes-belgium.json"

with open(output_file, 'w', encoding='utf-8') as f:
    for item in output:
        if item['id'] in to_remove:
            continue
        f.write(json.dumps(item) + '\n')

print(f"Data has been written to {output_file}")
