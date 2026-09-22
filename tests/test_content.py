import json,math,copy
from pathlib import Path
import pytest
from scripts.validate.content import validate,ROOT,safe_proposal,validate_item
from scripts.generate.reference import inventory,supplier,mean,percent,references

def test_full_content_has_verified_evidence():
 counts=validate();assert counts['skills']>=15 and counts['lessons']==8 and counts['cases']==2
 evidence=[json.loads(p.read_text()) for p in (ROOT/'content/evidence').glob('*.json')]
 assert len({e['source_id'] for e in evidence})>=8
 assert len({e['publisher'] for e in evidence})>=4
 assert all(e['source_claim']!=e['editorial_recommendation'] for e in evidence)
def test_case_calculations_units_and_missing():
 r=references();assert r['case-supplier'][0]['known_cash_cost']==1100;assert r['case-supplier'][1]['known_cash_cost']==1430
 assert r['case-inventory']['baseline'][0]['ip']==45
 a=json.loads((ROOT/'content/cases/case-inventory.json').read_text())['rows'][0]
 d=sum(a['demand_28_days'])/28;assert inventory(a)['quantity']==math.ceil(max(0,d*10+20-45))
 for inp in [[],[None,1],[float('nan')],[-1]]:
  with pytest.raises(ValueError):mean(inp)
 assert mean([0,0])==0;assert percent(0,0) is None
 assert supplier({'moq_units':150,'unit_price_cny':9,'freight_cny':80,'lead_days':14,'supplier':'乙'})['excess']==50

def test_original_lessons_avoid_future_and_service_confusion():
 f=json.loads((ROOT/'content/lessons/lesson-forecast.json').read_text());assert f['question']['answer']==3
 assert any('最终测试' in s['body'] for s in f['sections']);m=json.loads((ROOT/'content/lessons/lesson-metrics.json').read_text());assert any('周期服务水平' in s['body'] for s in m['sections'])

def sample():
 u=json.loads((ROOT/'content/updates/release-initial.json').read_text());u['status']='draft';return u
@pytest.mark.parametrize('path',['../out.json','/tmp/out.json','frontend/src/x.json','.github/workflows/test.yml','content/updates/../../x.json','content/lessons/release-initial.json'])
def test_reject_updater_paths(path):
 with pytest.raises((AssertionError,ValueError)):safe_proposal(path,sample())
def test_reject_script_and_schema_and_symlink(tmp_path):
 u=sample();u['summary']='<script>alert(1)</script>'
 with pytest.raises(ValueError):safe_proposal('content/updates/release-initial.json',u)
 u=sample();u['arbitrary_code']='attack'
 with pytest.raises(ValueError):validate_item('updates',u)
 (tmp_path/'content').mkdir();(tmp_path/'content/updates').symlink_to(tmp_path/'outside')
 with pytest.raises(AssertionError):safe_proposal('content/updates/release-initial.json',sample(),tmp_path)
def test_vendor_and_job_scope():
 e=json.loads((ROOT/'content/evidence/ev-flow.json').read_text());e['claim_scope']='global_consensus'
 with pytest.raises(ValueError):validate_item('evidence',e)
 e['claim_scope']='source_specific';e['source_type']='job'
 with pytest.raises(AssertionError):validate_item('evidence',e)
