"""Generate FGC nodes and a runtime index from the official GTFS feed."""
from __future__ import annotations
import csv, hashlib, io, json, os, shutil, sqlite3, tempfile, zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
import requests

from common.io import ROOT, write_ndjson
from common.validate import validate_nodes

OFFICIAL_GTFS_URL = "https://www.fgc.cat/google/google_transit.zip"
OUTPUT = ROOT / "nodes" / "nodes-spain-fgc.json"
CACHE_ROOT = ROOT / "cache" / "spain" / "fgc"
INDEX_OUTPUT = ROOT / "cache" / "spain-fgc.sqlite"
RETAINED = ROOT / "overrides" / "spain-fgc-retained-stations.json"
CATEGORY = "spain_fgc"

def _clean(row):
    return {str(k or "").strip(): str(v or "").strip() for k, v in row.items()}

def _table(zf, name):
    try:
        raw = zf.read(name).decode("utf-8-sig", errors="replace")
    except KeyError:
        return []
    return [_clean(r) for r in csv.DictReader(io.StringIO(raw))]

def fetch_official_feed(*, session=None):
    """Download the current official FGC GTFS into ignored cache."""
    client = session or requests.Session()
    close = session is None
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    target = CACHE_ROOT / "google_transit.zip"
    temp = target.with_suffix(".zip.tmp")
    try:
        with client.get(OFFICIAL_GTFS_URL, stream=True, timeout=(10, 120),
                        headers={"User-Agent": "TrainGuessr-data/1.0"}) as response:
            response.raise_for_status()
            with temp.open("wb") as out:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk: out.write(chunk)
        if not zipfile.is_zipfile(temp):
            raise RuntimeError("FGC official GTFS response is not a ZIP archive")
        os.replace(temp, target)
        return target
    finally:
        temp.unlink(missing_ok=True)
        if close: client.close()

def load_feed(path):
    path = Path(path)
    if not zipfile.is_zipfile(path):
        raise ValueError(f"Not a GTFS ZIP: {path}")
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        required = {"stops.txt","routes.txt","trips.txt","stop_times.txt"}
        missing = required - names
        if missing: raise ValueError("FGC GTFS missing: " + ", ".join(sorted(missing)))
        return {
            "stops": _table(zf,"stops.txt"), "routes": _table(zf,"routes.txt"),
            "trips": _table(zf,"trips.txt"), "stop_times": _table(zf,"stop_times.txt"),
            "calendar": _table(zf,"calendar.txt"), "calendar_dates": _table(zf,"calendar_dates.txt"),
            "feed_info": _table(zf,"feed_info.txt"), "agency": _table(zf,"agency.txt"),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

def _rail_route(row):
    try: rt = int(row.get("route_type",""))
    except ValueError: return False
    return rt == 2 or 100 <= rt <= 199

def _load_retained(path=RETAINED):
    if not Path(path).is_file(): return set()
    payload=json.loads(Path(path).read_text())
    vals=payload.get("station_ids", payload) if isinstance(payload,dict) else payload
    if not isinstance(vals,list): raise ValueError("FGC saved-station override must be a list")
    return {str(x) for x in vals}

def _station_for_stop(stop_id, stops):
    row=stops.get(stop_id)
    if not row: return None
    parent=str(row.get("parent_station") or "").strip()
    if parent:
        p=stops.get(parent)
        if not p or str(p.get("location_type") or "0") != "1":
            raise ValueError(f"FGC stop {stop_id} has invalid parent_station {parent}")
        return parent
    if str(row.get("location_type") or "0") == "1":
        return stop_id
    # Keep a native stop ID when the feed does not provide a parent station.
    return stop_id

def _feed_end(feed):
    info=feed.get("feed_info") or []
    if info and info[0].get("feed_end_date"): return info[0]["feed_end_date"]
    dates=[r.get("end_date","") for r in feed.get("calendar") or [] if r.get("end_date")]
    return max(dates) if dates else ""

def build(feed, *, retained_station_ids=None):
    routes_all={r["route_id"]:r for r in feed["routes"] if r.get("route_id")}
    rail_routes={k:v for k,v in routes_all.items() if _rail_route(v)}
    trips_all={r["trip_id"]:r for r in feed["trips"] if r.get("trip_id")}
    rail_trips={k:v for k,v in trips_all.items() if v.get("route_id") in rail_routes}
    stops={r["stop_id"]:r for r in feed["stops"] if r.get("stop_id")}
    stop_times=defaultdict(list)
    station_routes=defaultdict(set)
    station_children=defaultdict(set)

    for r in feed["stop_times"]:
        tid=r.get("trip_id","")
        if tid not in rail_trips: continue
        sid=r.get("stop_id","")
        station=_station_for_stop(sid,stops)
        if not station: continue
        rr=dict(r); rr["station_id"]=station
        stop_times[tid].append(rr)
        station_routes[station].add(rail_trips[tid]["route_id"])
        station_children[station].add(sid)

    retained=set(retained_station_ids or _load_retained())
    for station in retained:
        if station not in stops:
            raise ValueError(f"Reviewed FGC station id is absent from official GTFS: {station}")

    selected=set(station_routes)|retained
    nodes=[]
    for station_id in sorted(selected):
        row=stops[station_id]
        try: lat=float(row["stop_lat"]); lon=float(row["stop_lon"])
        except (KeyError,ValueError) as exc:
            raise ValueError(f"FGC station {station_id} lacks valid coordinates") from exc
        children=sorted(station_children.get(station_id) or {station_id})
        nodes.append({
            "type":"node", "id": station_id,
            "lat": lat, "lon": lon, "category": CATEGORY,
            "tags": {
                "name":row.get("stop_name") or station_id,
                "provider":"FGC", "fgc_stop_id":station_id,
                "stop_ids":children, "route_ids":sorted(station_routes.get(station_id,())),
                **({"reviewed_no_current_rail_trip":True} if station_id in retained and station_id not in station_routes else {}),
            },
        })

    trips={}
    for tid,tr in rail_trips.items():
        rows=sorted(stop_times.get(tid,[]), key=lambda r:int(r.get("stop_sequence") or 0))
        if not rows: continue
        trips[tid]={
            "source_trip_id":tid, "source_feed":"fgc", "service_id":tr.get("service_id",""),
            "route_id":tr.get("route_id",""), "short_name":tr.get("trip_short_name",""),
            "headsign":tr.get("trip_headsign",""), "stops":[{
                "stop_id":r.get("stop_id",""), "station_id":r["station_id"],
                "arrival_time":r.get("arrival_time",""), "departure_time":r.get("departure_time",""),
                "stop_sequence":int(r.get("stop_sequence") or 0),
                "platform_code":(stops.get(r.get("stop_id","")) or {}).get("platform_code",""),
            } for r in rows],
        }
    index={
        "metadata":{"version":"1","provider":"fgc","source_url":OFFICIAL_GTFS_URL,
                    "source_sha256":feed["sha256"],"feed_end_date":_feed_end(feed)},
        "stations":{n["id"]:{"name":n["tags"]["name"],"stop_ids":n["tags"]["stop_ids"]} for n in nodes},
        "routes":rail_routes, "calendar":{r["service_id"]:r for r in feed["calendar"] if r.get("service_id")},
        "calendar_dates":feed["calendar_dates"], "trips":trips,
    }
    return nodes,index,{
        "raw_stops":len(feed["stops"]), "raw_routes":len(feed["routes"]),
        "rail_routes":len(rail_routes), "rail_trips":len(trips), "playable_stations":len(nodes),
        "retained_without_current_trip":sum(1 for s in retained if s not in station_routes),
        "deferred_nonrail_routes":len(routes_all)-len(rail_routes),
    }

def write_index(index, output=INDEX_OUTPUT):
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix="spain-fgc-",suffix=".sqlite",dir=output.parent); os.close(fd)
    db=Path(name)
    try:
        c=sqlite3.connect(db)
        with c:
            c.executescript("""
            PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
            CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE stations(id TEXT PRIMARY KEY,name TEXT NOT NULL,stop_ids TEXT NOT NULL);
            CREATE TABLE routes(id TEXT PRIMARY KEY,data TEXT NOT NULL);
            CREATE TABLE calendar(service_id TEXT PRIMARY KEY,data TEXT NOT NULL);
            CREATE TABLE calendar_dates(service_id TEXT NOT NULL,date TEXT NOT NULL,exception_type TEXT NOT NULL);
            CREATE TABLE trips(id TEXT PRIMARY KEY,source_trip_id TEXT NOT NULL,source_feed TEXT NOT NULL,service_id TEXT NOT NULL,route_id TEXT NOT NULL,short_name TEXT,headsign TEXT);
            CREATE TABLE stop_times(trip_id TEXT NOT NULL,stop_id TEXT NOT NULL,station_id TEXT NOT NULL,arrival_time TEXT,departure_time TEXT,stop_sequence INTEGER NOT NULL,platform_code TEXT);
            """)
            c.executemany("INSERT INTO metadata VALUES (?,?)", sorted(index["metadata"].items()))
            c.executemany("INSERT INTO stations VALUES (?,?,?)",[(k,v["name"],json.dumps(v["stop_ids"],separators=(",",":"))) for k,v in sorted(index["stations"].items())])
            c.executemany("INSERT INTO routes VALUES (?,?)",[(k,json.dumps(v,sort_keys=True,separators=(",",":"))) for k,v in sorted(index["routes"].items())])
            c.executemany("INSERT INTO calendar VALUES (?,?)",[(k,json.dumps(v,sort_keys=True,separators=(",",":"))) for k,v in sorted(index["calendar"].items())])
            c.executemany("INSERT INTO calendar_dates VALUES (?,?,?)",[(r.get("service_id",""),r.get("date",""),r.get("exception_type","")) for r in index["calendar_dates"]])
            for tid,tr in sorted(index["trips"].items()):
                c.execute("INSERT INTO trips VALUES (?,?,?,?,?,?,?)",(tid,tr["source_trip_id"],tr["source_feed"],tr["service_id"],tr["route_id"],tr["short_name"],tr["headsign"]))
                c.executemany("INSERT INTO stop_times VALUES (?,?,?,?,?,?,?)",[(tid,s["stop_id"],s["station_id"],s["arrival_time"],s["departure_time"],s["stop_sequence"],s.get("platform_code","")) for s in tr["stops"]])
            c.executescript("CREATE INDEX fgc_st_station ON stop_times(station_id); CREATE INDEX fgc_st_stop ON stop_times(stop_id); CREATE INDEX fgc_st_trip ON stop_times(trip_id,stop_sequence);")
        c.close(); os.replace(db,output); os.chmod(output,0o644); db=None
    finally:
        if db is not None: db.unlink(missing_ok=True)

def generate(path=None):
    source=Path(path) if path else fetch_official_feed()
    nodes,index,stats=build(load_feed(source))
    errors=validate_nodes(nodes)
    if errors: raise ValueError("FGC node validation failed: "+"; ".join(errors[:10]))
    write_ndjson(OUTPUT,nodes); write_index(index)
    return stats
