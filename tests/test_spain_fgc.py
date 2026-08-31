from __future__ import annotations
import json, sqlite3, sys, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"gen"))
from countries.spain import fgc

def _zip(path):
    files={
      "agency.txt":"agency_id,agency_name\nFGC,Ferrocarrils de la Generalitat de Catalunya\n",
      "routes.txt":"route_id,agency_id,route_short_name,route_long_name,route_type\nS1,FGC,S1,Rail,2\nL7,FGC,L7,Metro,1\nFM,FGC,FM,Funicular,7\n",
      "stops.txt":"stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station,platform_code\nA,Alpha,41.0,2.0,1,,\nA1,Alpha p1,41.0,2.0,0,A,1\nB,Beta,41.1,2.1,1,,\nB1,Beta p1,41.1,2.1,0,B,2\nM,Metro,41.2,2.2,1,,\nM1,Metro p1,41.2,2.2,0,M,\n",
      "trips.txt":"route_id,service_id,trip_id,trip_headsign,trip_short_name\nS1,WK,R1,Beta,101\nL7,WK,M1,Metro,7\n",
      "stop_times.txt":"trip_id,arrival_time,departure_time,stop_id,stop_sequence\nR1,10:00:00,10:00:00,A1,1\nR1,10:10:00,10:10:00,B1,2\nM1,11:00:00,11:00:00,M1,1\n",
      "calendar.txt":"service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nWK,1,1,1,1,1,1,1,20260801,20261231\n",
      "calendar_dates.txt":"service_id,date,exception_type\n",
      "feed_info.txt":"feed_publisher_name,feed_publisher_url,feed_lang,feed_start_date,feed_end_date\nFGC,https://www.fgc.cat,ca,20260801,20261231\n",
    }
    with zipfile.ZipFile(path,"w") as z:
        for n,v in files.items(): z.writestr(n,v)

def test_fgc_uses_native_parent_station_ids_and_defers_nonrail(tmp_path):
    p=tmp_path/"fgc.zip"; _zip(p)
    nodes,index,stats=fgc.build(fgc.load_feed(p),retained_station_ids=set())
    assert [n["id"] for n in nodes]==["A","B"]
    assert nodes[0]["tags"]["stop_ids"]==["A1"]
    assert index["trips"]["R1"]["stops"][0]["platform_code"]=="1"
    assert stats["rail_routes"]==1 and stats["deferred_nonrail_routes"]==2
    assert "M" not in index["stations"]

def test_reviewed_no_trip_station_must_exist_in_official_namespace(tmp_path):
    p=tmp_path/"fgc.zip"; _zip(p); feed=fgc.load_feed(p)
    nodes,_,stats=fgc.build(feed,retained_station_ids={"M"})
    row=next(n for n in nodes if n["id"]=="M")
    assert row["tags"]["reviewed_no_current_rail_trip"] is True
    assert stats["retained_without_current_trip"]==1
    import pytest
    with pytest.raises(ValueError,match="absent from official GTFS"):
        fgc.build(feed,retained_station_ids={"INVENTED"})

def test_fgc_index_is_runtime_ready_and_contains_feed_expiry(tmp_path):
    p=tmp_path/"fgc.zip"; _zip(p)
    _,index,_=fgc.build(fgc.load_feed(p),retained_station_ids=set())
    db=tmp_path/"fgc.sqlite"; fgc.write_index(index,db)
    con=sqlite3.connect(db)
    meta=dict(con.execute("select key,value from metadata"))
    assert meta["provider"]=="fgc"
    assert meta["feed_end_date"]=="20261231"
    assert con.execute("select platform_code from stop_times where stop_id='A1'").fetchone()==("1",)
    con.close()
