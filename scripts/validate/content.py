"""Fail closed for structured teaching content and automatic update proposals."""
import json,re,sys,hashlib
from pathlib import Path
from urllib.parse import urlsplit
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal,Any
ROOT=Path(__file__).resolve().parents[2]
class Strict(BaseModel):
 model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
class Record(Strict):
 id:str=Field(pattern=r'^[a-z][a-z0-9-]{1,79}$')
 version:int=Field(ge=1)
class Source(Record):
 title:str;url:str;publisher:str;source_type:Literal['framework','course','job','named_research','public_method','enterprise_case','tool_documentation','vendor_claim'];access_status:Literal['accessible','restricted','unavailable'];checked_at:str;published_at:str|None;date_precision:str;content_hash:str|None;hash_basis:str|None;verified_excerpt:str|None;verification_method:str;terms_url:str;usage:str;expert:dict|None
class Evidence(Record):
 source_id:str;original_url:str;publisher:str;source_type:str;published_at:str|None;date_precision:str;discovered_at:str;checked_at:str;roles:list[str];regions:list[str];source_claim:str;editorial_recommendation:str;uncertainty:str;locator:str;excerpt:str|None;access_status:Literal['accessible','restricted','unavailable'];content_hash:str|None;hash_basis:str;independence_key:str;claim_scope:Literal['source_specific'];job:dict|None;case_metrics:dict|None
class Skill(Record):
 title:str;status:Literal['published','draft','planned'];review_status:str;english_term:str;aliases:list[str];domain:Literal['A','B','C','D','E','F','G','H'];roles:list[str];industries:list[str];experience:list[str];level:str;kind:Literal['business','software','communication','experimental'];business_problem:str;prerequisites:list[str];objectives:list[str];tools:list[str];lessons:list[str];course_status:Literal['available','planned'];exercises:list[str];deliverable:str;rubric:list[str];evidence:list[str];limitations:list[str];case_ids:list[str]
class Section(Strict):
 id:str;title:str;body:str
class Question(Strict):
 id:str;prompt:str;answer:float;unit:str;tolerance:float=Field(ge=0);hint:str;explanation:str
class Lesson(Record):
 title:str;status:Literal['published','draft','planned'];review_status:str;subtitle:str;estimated_minutes:int;goals:list[str];prerequisites:list[str];evidence:list[str];sections:list[Section]=Field(min_length=5);question:Question;variant:Question;open_task:str;rubric:list[str];misconceptions:list[str];limitations:list[str];synthetic:Literal[True]
class Case(Record):
 title:str;status:Literal['published','draft','planned'];review_status:str;synthetic:Literal[True];seed:int;description:str;goals:list[str];prerequisites:list[str];evidence:list[str];rows:list[dict];dictionary:dict[str,str];steps:list[str];answer_fields:list[dict[str,str]];rubric:list[str];limitations:list[str];reference_note:str
class Update(Record):
 status:Literal['published','draft'];update_type:Literal['evidence','course_suggestion','route_proposal'];title:str;created_at:str;summary:str;source_ids:list[str];skill_ids:list[str];source_claim:str;editorial_recommendation:str;uncertainty:str;original_urls:list[str];impact:str;checks:list[str];human_review:list[str]
MODELS={'sources':Source,'evidence':Evidence,'skills':Skill,'lessons':Lesson,'cases':Case,'updates':Update}
def safe_text(value):
 if isinstance(value,str):
  if len(value)>24000 or re.search(r'<\s*(?:/?[a-zA-Z]|!)|javascript\s*:|data\s*:text/html|\x00',value,re.I):raise ValueError('Unsafe or oversized text')
 elif isinstance(value,dict):
  for k,v in value.items():safe_text(k);safe_text(v)
 elif isinstance(value,list):
  for v in value:safe_text(v)
def validate_item(kind,obj):
 safe_text(obj);MODELS[kind].model_validate(obj)
 for key in ['url','original_url','terms_url']:
  if key in obj:
   u=urlsplit(obj[key]);assert u.scheme=='https' and u.hostname and not u.username and u.hostname not in ['localhost','127.0.0.1'],'Non-public HTTPS URL'
 for url in obj.get('original_urls',[]):
  u=urlsplit(url);assert u.scheme=='https' and u.hostname and not u.username
 if kind=='evidence':
  assert obj['source_claim'] and obj['uncertainty'] and obj['editorial_recommendation']
  if obj['source_type']=='job':
   assert obj['job'] and all(k in obj['job'] for k in ['role','region','experience','required','preferred','responsibilities','posted_at','checked_at','expires_at','canonical_job_id'])
  if obj['access_status']=='accessible':assert re.fullmatch('[a-f0-9]{64}',obj['content_hash'] or '')
  assert obj['source_type']!='vendor_claim' or '厂商' in obj['uncertainty']
 return obj
def load(root=ROOT):
 all={}
 for kind in MODELS:
  records=[]
  for p in sorted((root/'content'/kind).glob('*')):
   assert not p.is_symlink() and p.suffix=='.json' and p.is_file(),f'Unsafe content path: {p}'
   assert p.stat().st_size<500_000
   obj=json.loads(p.read_text());validate_item(kind,obj);assert p.stem==obj['id'];records.append(obj)
  assert len({x['id'] for x in records})==len(records)
  all[kind]=records
 return all
def validate(root=ROOT):
 data=load(root);index={k:{v['id']:v for v in vs} for k,vs in data.items()}
 for kind in ['skills','lessons','cases']:
  for v in data[kind]:
   assert v['evidence'] or v['status']!='published',v['id']
   for e in v['evidence']:assert e in index['evidence']
   for p in v['prerequisites']:assert p in index['skills' if kind=='skills' else 'lessons']
   if kind=='skills':
    for l in v['lessons']:assert l in index['lessons']
    if v['status']=='published':assert any(index['evidence'][e]['access_status']=='accessible' for e in v['evidence'])
 for e in data['evidence']:
  s=index['sources'][e['source_id']];assert e['original_url']==s['url'];assert e['content_hash']==s['content_hash'];assert e['source_type']==s['source_type']
 for kind in ['skills','lessons']:
  def visit(id,stack):
   assert id not in stack,f'Prerequisite cycle: {id}'
   for p in index[kind][id]['prerequisites']:visit(p,stack+[id])
  for id in index[kind]:visit(id,[])
 for u in data['updates']:
  for s in u['source_ids']:assert s in index['sources']
  for s in u['skill_ids']:assert s in index['skills']
 assert len(data['skills'])>=15 and len(data['lessons'])>=8 and len(data['cases'])>=2
 return {k:len(v) for k,v in data.items()}
def safe_proposal(path,obj,root=ROOT):
 # The writer is more restrictive than the content library: additive, draft-only updates.
 p=Path(path)
 assert not p.is_absolute() and len(p.parts)==3 and p.parts[0]=='content' and p.parts[1]=='updates' and p.suffix=='.json','Outside updater allowlist'
 assert p.stem==obj.get('id') and obj.get('status')=='draft'
 target=root/p
 for ancestor in [target,*target.parents]:
  if ancestor==root.parent:break
  assert not ancestor.is_symlink(),'Symlink not permitted'
 assert target.resolve().is_relative_to(root.resolve())
 validate_item('updates',obj)
 for field,kind in [('source_ids','sources'),('skill_ids','skills')]:
  for id in obj[field]:
   assert re.fullmatch(r'[a-z][a-z0-9-]{1,79}',id) and (root/'content'/kind/(id+'.json')).is_file(),'Unknown proposal reference'
 return target
if __name__=='__main__':
 print(json.dumps(validate(),ensure_ascii=False))
