import os
import json
import xml.etree.ElementTree as ET
import xml.dom.minidom
from datetime import datetime, timedelta


def _parse_iso_time(value):
    """Parse timeline timestamps without extra dependencies."""
    if not value:
        raise ValueError("empty time")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def parse_lat_lng(text):
    """Parse Google timeline lat/lng strings (degrees symbol, optional geo: prefix)."""
    if text is None:
        raise ValueError("missing coordinates")
    raw = str(text).replace("°", "").replace("geo:", "").strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) != 2:
        raise ValueError(f"expected two numbers, got {parts!r}")
    return float(parts[0]), float(parts[1])


def create_gpx_file(points, output_file):
    gpx = ET.Element("gpx", version="1.1", creator="https://github.com/Makeshit/Timeline-GPX-Exporter")
    trk = ET.SubElement(gpx, "trk")
    trkseg = ET.SubElement(trk, "trkseg")

    for point in points:
        trkpt = ET.SubElement(trkseg, "trkpt", lat=str(point["lat"]), lon=str(point["lon"]))
        ET.SubElement(trkpt, "time").text = point["time"]

    xml_str = xml.dom.minidom.parseString(ET.tostring(gpx)).toprettyxml(indent="  ")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xml_str)


def _append_point(points_by_date, lat, lon, time_text):
    try:
        dt = _parse_iso_time(time_text)
    except (ValueError, TypeError):
        return
    date = dt.date().isoformat()
    points_by_date.setdefault(date, []).append({"lat": lat, "lon": lon, "time": time_text})


def parse_semantic_export(data):
    """
    Phone / Maps export: object with semanticSegments (Timeline.json or location-history.json).
    Includes timelinePath, inferred visits, activities, and optional rawSignals positions.
    """
    points_by_date = {}

    for segment in data.get("semanticSegments", []):
        for path_point in segment.get("timelinePath", []):
            try:
                lat, lon = parse_lat_lng(path_point["point"])
                _append_point(points_by_date, lat, lon, path_point["time"])
            except (KeyError, ValueError, TypeError):
                continue

        visit = segment.get("visit")
        if visit:
            cand = visit.get("topCandidate") or {}
            place = cand.get("placeLocation") or {}
            latlng = place.get("latLng")
            if latlng and segment.get("startTime"):
                try:
                    lat, lon = parse_lat_lng(latlng)
                    _append_point(points_by_date, lat, lon, segment["startTime"])
                except (ValueError, TypeError):
                    pass

        activity = segment.get("activity")
        if activity:
            for corner, time_key in (("start", "startTime"), ("end", "endTime")):
                node = activity.get(corner) or {}
                latlng = node.get("latLng")
                t = segment.get(time_key)
                if latlng and t:
                    try:
                        lat, lon = parse_lat_lng(latlng)
                        _append_point(points_by_date, lat, lon, t)
                    except (ValueError, TypeError):
                        pass

    for raw in data.get("rawSignals", []):
        pos = raw.get("position")
        if not pos:
            continue
        latlng = pos.get("LatLng") or pos.get("latLng")
        ts = pos.get("timestamp")
        if not latlng or not ts:
            continue
        try:
            lat, lon = parse_lat_lng(latlng)
            _append_point(points_by_date, lat, lon, ts)
        except (ValueError, TypeError):
            continue

    for date, pts in points_by_date.items():
        pts.sort(key=lambda p: _parse_iso_time(p["time"]))

    return points_by_date


def parse_segment_array(data):
    """Legacy export: JSON root is a list of segments with geo: lat,lon and minute offsets."""
    points_by_date = {}
    if not isinstance(data, list):
        return points_by_date

    for segment in data:
        start_time = segment.get("startTime")
        if not start_time:
            continue
        try:
            base = _parse_iso_time(start_time)
        except (ValueError, TypeError):
            continue

        for path_point in segment.get("timelinePath", []):
            try:
                lat, lon = parse_lat_lng(path_point["point"])
                offset = path_point.get("durationMinutesOffsetFromStartTime")
                if offset is None:
                    continue
                t = base + timedelta(minutes=float(offset))
                _append_point(points_by_date, lat, lon, t.isoformat())
            except (KeyError, ValueError, TypeError):
                continue

    for date, pts in points_by_date.items():
        pts.sort(key=lambda p: _parse_iso_time(p["time"]))

    return points_by_date


def load_points_by_date(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return parse_segment_array(data)
    if isinstance(data, dict) and "semanticSegments" in data:
        return parse_semantic_export(data)
    return {}


def main():
    script_dir = os.getcwd()
    timeline_path = os.path.join(script_dir, "Timeline.json")
    location_path = os.path.join(script_dir, "location-history.json")
    output_dir = os.path.join(script_dir, "GPX_Output")

    if os.path.isfile(timeline_path):
        input_path = timeline_path
    elif os.path.isfile(location_path):
        input_path = location_path
    else:
        print(
            f"No input file found. Place 'Timeline.json' or 'location-history.json' in {script_dir}."
        )
        return

    os.makedirs(output_dir, exist_ok=True)

    points_by_date = load_points_by_date(input_path)
    if not points_by_date:
        print(f"No track points parsed from {input_path}. Check the JSON structure.")
        return

    for date, points in points_by_date.items():
        output_file = os.path.join(output_dir, f"{date}.gpx")
        create_gpx_file(points, output_file)
        print(f"Created: {output_file}")


if __name__ == "__main__":
    main()
