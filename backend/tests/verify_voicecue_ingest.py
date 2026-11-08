"""Validate the real uploaded recording; no synthetic ASR/frame API responses."""
import hashlib
import json
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPLOAD = ROOT / 'tasks/overnight/evidence/voicecue-upload.json'
PROJECT = json.loads(UPLOAD.read_text())['project_id']
detail = json.load(urllib.request.urlopen(f'http://127.0.0.1:8787/api/projects/{PROJECT}', timeout=10))
media = detail['media']
assert media and media['has_audio'] and media['has_video']
assert media['source_sha256'] == hashlib.sha256((ROOT/'deliverables/VoiceCue-demo.mp4').read_bytes()).hexdigest()
assert len(media['frames']) == len(media['observations']) > 0
assert all(not frame.get('error') for frame in media['observations'])
assert detail['transcripts'] and any(source['source_type']=='video' and source['relevant'] is True for source in detail['sources'])
assert detail['status']=='failed' and detail['outcome']['evaluation']['verdict']=='Incomplete', 'A stopped GUI attempt must leave the overall assessment Incomplete, while retaining recording knowledge'
assert all(cap['verification_status'] != 'verified' for cap in detail['capabilities'])
report = urllib.request.urlopen(f'http://127.0.0.1:8787/api/projects/{PROJECT}/report', timeout=10).read().decode()
assert 'Not ready for approval' in report and 'Evidence verdict: Incomplete' in report
summary = {'project_id':PROJECT, 'status':detail['status'], 'verdict':detail['outcome']['evaluation']['verdict'], 'transcript_segments':len(detail['transcripts']), 'frames_analyzed':len(media['observations']), 'capabilities_by_level':dict(Counter(c['verification_status'] for c in detail['capabilities'])), 'same_recording_sha256':True, 'report_verified':True}
(ROOT/'tasks/overnight/evidence/voicecue-ingestion-final.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary))
