"""Privileged writer. Never evaluates external text. Never checks out a PR branch."""
import argparse,base64,json,os,re,urllib.request,urllib.error
from scripts.validate.content import ROOT,safe_proposal,validate_item
BRANCH='automation/content-updates';STATE_BRANCH='automation/collector-state';STATE_PATH='content/updates/collector-state.json'
class GitHub:
 def __init__(self,repo,token):
  assert re.fullmatch(r'[\w.-]+/[\w.-]+',repo);self.base='https://api.github.com/repos/'+repo;self.token=token;self.repo=repo
 def call(self,path,method='GET',data=None,optional=False):
  req=urllib.request.Request(self.base+path,method=method,data=json.dumps(data).encode() if data is not None else None,headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2026-03-10','User-Agent':'SupplyChainSkillsLab'})
  try:
   with urllib.request.urlopen(req,timeout=25) as r:return json.load(r) if r.status!=204 else None
  except urllib.error.HTTPError as e:
   if optional and e.code==404:return None
   raise RuntimeError(f'GitHub request failed with status {e.code}') from None
 def read_file(self,path,ref):
  d=self.call('/contents/'+path+'?ref='+urllib.parse.quote(ref,safe=''),optional=True)
  if not d:return None
  assert d['type']=='file' and d.get('encoding')=='base64'
  return json.loads(base64.b64decode(d['content']))
 def ref(self,branch):return self.call('/git/ref/heads/'+branch,optional=True)
 def write_tree(self,base_sha,files,message,branch):
  base=self.call('/git/commits/'+base_sha)
  tree=self.call('/git/trees','POST',{'base_tree':base['tree']['sha'],'tree':[{'path':path,'mode':'100644','type':'blob','content':json.dumps(data,ensure_ascii=False,indent=2)+'\n'} for path,data in files.items()]})
  if tree['sha']==base['tree']['sha']:return base_sha
  commit=self.call('/git/commits','POST',{'message':message,'tree':tree['sha'],'parents':[base_sha]})
  current=self.ref(branch)
  if current:
   if current['object']['sha']!=base_sha:raise RuntimeError('Branch changed during write; no overwrite')
   self.call('/git/refs/heads/'+branch,'PATCH',{'sha':commit['sha'],'force':False})
  else:self.call('/git/refs','POST',{'ref':'refs/heads/'+branch,'sha':commit['sha']})
  return commit['sha']
def validate_proposal(p):
 assert p['schema_version']==1 and isinstance(p['drafts'],list) and len(p['drafts'])<=3
 assert isinstance(p['state'],dict) and p['state'].get('schema_version')==1
 for d in p['drafts']:
  assert set(d)=={'path','data','fingerprint','before_hash','after_hash'}
  safe_proposal(d['path'],d['data']);assert re.fullmatch('[a-f0-9]{64}',d['fingerprint'])
  for key in ['before_hash','after_hash']:assert re.fullmatch('[a-f0-9]{64}',d[key])
 return p

def sync(gh,p,base_branch):
 validate_proposal(p);base=gh.ref(base_branch)['object']['sha'];remote_state=gh.read_file(STATE_PATH,STATE_BRANCH) or {}
 if p.get('expected_state_sha')!=((gh.ref(STATE_BRANCH) or {}).get('object',{}).get('sha')):raise RuntimeError('Checkpoint changed; rerun collection')
 prs=gh.call('/pulls?state=open&head='+urllib.parse.quote(gh.repo.split('/')[0]+':'+BRANCH,safe=''))
 if len(prs)>1:raise RuntimeError('More than one open automatic PR')
 pr=prs[0] if prs else None;content_ref=gh.ref(BRANCH);last_head=remote_state.get('pr_head')
 if pr:
  # Human edits or reviews freeze the pending branch. No silent overwrite.
  if content_ref['object']['sha']!=last_head:raise RuntimeError('Human or unknown edits detected; preserve pending PR')
  if gh.call(f"/pulls/{pr['number']}/reviews") or gh.call(f"/issues/{pr['number']}/comments"):raise RuntimeError('PR is under human review; preserve it')
 elif content_ref:
  closed=gh.call('/pulls?state=closed&head='+urllib.parse.quote(gh.repo.split('/')[0]+':'+BRANCH,safe='')+'&per_page=1')
  if closed and not closed[0].get('merged_at'):
   p['state']['rejected']=list(set(p['state'].get('rejected',[])+remote_state.get('pending_fingerprints',[])))
  if content_ref['object']['sha']!=last_head:raise RuntimeError('Unknown changes on automation branch')
  # Reuse branch only by fast-forward; never rewrite an unmerged/rejected branch.
  if p['drafts']:raise RuntimeError('Previous PR closed; maintainer must archive/remove the old automation branch before new proposals')
 drafts=[d for d in p['drafts'] if d['fingerprint'] not in p['state'].get('rejected',[])]
 if drafts:
  head=content_ref['object']['sha'] if content_ref else base
  files={d['path']:d['data'] for d in drafts}
  for path,data in files.items():
   if gh.read_file(path,BRANCH if content_ref else base_branch) is not None:raise RuntimeError('Draft already exists; never overwrite human text')
  head=gh.write_tree(head,files,'Propose reviewed-source content changes',BRANCH)
  if not pr:
   body='新增结构化证据更新草稿；尚未发布，也不改写现有课程。\n\n'+''.join('### '+d['data']['title']+'\n- 原始来源：'+', '.join(d['data']['original_urls'])+'\n- 支持结论：'+d['data']['source_claim']+'\n- 适合技能：'+', '.join(d['data']['skill_ids'])+'\n- 局限：'+d['data']['uncertainty']+'\n- 检查：schema、路径白名单、去重、来源访问与正文指纹。\n- 待人工核查：专业结论、定位、岗位/地区与是否为厂商主张。\n- 影响：不改变课程或个人记录。\n\n' for d in drafts)
   pr=gh.call('/pulls','POST',{'title':'供应链内容更新 · 待人工核查','head':BRANCH,'base':base_branch,'body':body,'draft':True})
  p['state']['pr_head']=head;p['state']['pending_fingerprints']=list(set(remote_state.get('pending_fingerprints',[])+[d['fingerprint'] for d in drafts]))
 else:
  for key in ['pr_head','pending_fingerprints']:
   if key in remote_state:p['state'][key]=remote_state[key]
 state_ref=gh.ref(STATE_BRANCH);gh.write_tree(state_ref['object']['sha'] if state_ref else base,{STATE_PATH:p['state']},'Checkpoint collection progress',STATE_BRANCH)
 return {'pull_request':pr['html_url'] if pr else None,'substantive_updates':len(drafts)}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--proposal',default='work/collection/proposal.json');p.add_argument('--publish',action='store_true');args=p.parse_args();proposal=validate_proposal(json.load(open(args.proposal)))
 if not args.publish:print(json.dumps({'dry_run':True,'proposed_files':[d['path'] for d in proposal['drafts']],'no_pr':not proposal['drafts']},ensure_ascii=False))
 else:
  gh=GitHub(os.environ['GITHUB_REPOSITORY'],os.environ['GITHUB_TOKEN']);base=gh.call('')['default_branch'];print(json.dumps(sync(gh,proposal,base)))
