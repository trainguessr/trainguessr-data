"""Capture broad Catalonia passenger-rail physical evidence for FGC reconciliation.

This is discovery evidence only.  It never assigns provider IDs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen"))

from common.io import ROOT  # noqa: E402

OUT=ROOT/"cache"/"spain"/"fgc"/"audit"/"osm-passenger-sites.json"
OVERPASS="https://overpass-api.de/api/interpreter"
QUERY="""[out:json][timeout:180];
area["ISO3166-2"="ES-CT"][boundary=administrative]->.a;
(
 nwr(area.a)["railway"~"^(station|halt|stop)$"];
 nwr(area.a)["disused:railway"~"^(station|halt|stop)$"];
 nwr(area.a)["abandoned:railway"~"^(station|halt|stop)$"];
);
out center tags;"""

def capture(output=OUT):
    r=requests.post(OVERPASS,data={"data":QUERY},timeout=240,headers={"User-Agent":"TrainGuessr-data/1.0"})
    r.raise_for_status(); payload=r.json()
    rows=[]
    for e in payload.get("elements",[]):
        tags=e.get("tags") or {}; center=e.get("center") or {}
        lat=e.get("lat",center.get("lat")); lon=e.get("lon",center.get("lon"))
        rows.append({"osm_type":e.get("type"),"osm_id":e.get("id"),"lat":lat,"lon":lon,"tags":tags})
    rows.sort(key=lambda x:(str(x["osm_type"]),int(x["osm_id"])))
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({"source":"OpenStreetMap/Overpass","query":QUERY,"elements":rows},ensure_ascii=False,indent=2)+"\n")
    return len(rows)

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--output",type=Path,default=OUT); a=p.parse_args()
    print(f"Captured {capture(a.output)} Catalonia passenger-site candidates")
