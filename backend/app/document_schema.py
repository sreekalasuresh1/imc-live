"""Strict server boundary for the desktop v1 finite document format.

The browser uses shared/document.mjs. Keep parity fixtures when extending this schema.
"""
import json
import math
import re
from datetime import datetime, date


def check(ok):
    if not ok:
        raise ValueError('Invalid finite document')


def number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def ident(value):
    return isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9-]{1,80}', value)


def exact(obj, keys):
    return isinstance(obj, dict) and not (set(obj) - set(keys.split()))


def validate_document(doc):
    check(exact(doc, 'schemaVersion id kind visibility title createdAt creationDate updatedAt revision activePageId pages topic subject student batch'))
    check(type(doc.get('schemaVersion')) is int and doc['schemaVersion'] == 1 and ident(doc.get('id')) and doc.get('kind') == 'lesson' and doc.get('visibility') == 'private')
    check(isinstance(doc.get('title'), str) and 0 < len(doc['title'].strip()) <= 200 and len(doc['title']) <= 200)
    check(type(doc.get('revision')) is int and 0 <= doc['revision'] <= 9007199254740991)
    for key in ('createdAt', 'updatedAt'):
        check(isinstance(doc.get(key), str)); datetime.fromisoformat(doc[key].replace('Z', '+00:00'))
    check(isinstance(doc.get('creationDate'), str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', doc['creationDate'])); date.fromisoformat(doc['creationDate'])
    for key in ('topic', 'subject', 'student', 'batch'):
        if key in doc:
            check(isinstance(doc[key], str) and len(doc[key]) <= 200)
    check(isinstance(doc.get('pages'), list) and 1 <= len(doc['pages']) <= 1000)
    ids = set()
    for page in doc['pages']:
        check(exact(page, 'id width height objects') and ident(page.get('id')) and page['id'] not in ids and page.get('width') == 900 and page.get('height') == 1273 and isinstance(page.get('objects'), list))
        ids.add(page['id'])
        for obj in page['objects']:
            validate_object(obj)
            check(obj['id'] not in ids); ids.add(obj['id'])
    check(doc.get('activePageId') in [p['id'] for p in doc['pages']])
    check(len(json.dumps(doc, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')) <= 16 * 1024 * 1024)
    return doc


def validate_object(o):
    check(isinstance(o, dict) and ident(o.get('id')))
    kind = o.get('type')
    if kind == 'image':
        check(exact(o, 'id type assetId x y width height rotation masks') and ident(o.get('assetId')))
        for key, lo, hi in [('x', -1800, 1800), ('y', -2546, 2546), ('width', 5, 1800), ('height', 5, 2546), ('rotation', 0, 360)]:
            check(number(o.get(key), lo, hi))
        if 'masks' in o:
            check(isinstance(o['masks'], list) and len(o['masks']) <= 256)
            for mask in o['masks']:
                check(exact(mask, 'id points') and ident(mask.get('id')) and isinstance(mask.get('points'), list) and 3 <= len(mask['points']) <= 2048)
                check(all(isinstance(p, list) and len(p) == 2 and all(number(v, -1000, 1000) for v in p) for p in mask['points']))
        return
    check(isinstance(o.get('color'), str) and re.fullmatch(r'#[0-9a-fA-F]{6}', o['color']))
    if kind == 'grid':
        check(exact(o, 'id type protected x y rows columns cellSize color size axes numbers') and o.get('protected') is True)
        check(all(type(o.get(k)) is int and 1 <= o[k] <= 50 for k in ('rows', 'columns')))
        check(number(o.get('cellSize'), 4, 120) and number(o.get('size'), .5, 4) and number(o.get('x'), 0, 900) and number(o.get('y'), 0, 1273))
        check(o['x'] + o['columns'] * o['cellSize'] <= 900 and o['y'] + o['rows'] * o['cellSize'] <= 1273)
        check(type(o.get('axes')) is bool and type(o.get('numbers')) is bool)
        return
    check(exact(o, 'id type color size points x y width height text pressureCurve pressureEnabled inputType sampleTimes matrix') and number(o.get('size'), .1, 100))
    if 'matrix' in o:
        m = o['matrix']; check(isinstance(m, list) and len(m) == 6 and all(number(v, -100000, 100000) for v in m))
        check(abs(m[0] * m[3] - m[1] * m[2]) >= 1e-8)
    if kind in ('stroke', 'highlighter'):
        check(isinstance(o.get('points'), list) and 1 <= len(o['points']) <= 50000)
        check(all(isinstance(p, list) and len(p) == 3 and number(p[0], 0, 900) and number(p[1], 0, 1273) and number(p[2], 0, 1) for p in o['points']))
        if 'pressureCurve' in o: check(number(o['pressureCurve'], .3, 2.5))
        if 'pressureEnabled' in o: check(type(o['pressureEnabled']) is bool)
        if 'inputType' in o: check(o['inputType'] in ('pen', 'mouse'))
        if 'sampleTimes' in o:
            times = o['sampleTimes']; check(isinstance(times, list) and len(times) == len(o['points']) and all(number(v, 0, 86400000) for v in times))
            check(all(a <= b for a, b in zip(times, times[1:])))
    else:
        check(kind in ('text', 'line', 'rectangle', 'ellipse'))
        check(number(o.get('x'), 0, 900) and number(o.get('y'), 0, 1273) and number(o.get('width'), -900, 900) and number(o.get('height'), -1273, 1273))
        if kind == 'text': check(isinstance(o.get('text'), str) and bool(o['text'].strip()) and len(o['text']) <= 2000)
