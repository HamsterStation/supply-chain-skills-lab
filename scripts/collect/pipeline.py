"""Controlled collection: fixed allowlisted URLs, durable checkpoints, no model/tool execution."""
import argparse,hashlib,ipaddress,json,re,socket,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from urllib.robotparser import RobotFileParser
import httpx,yaml
from bs4 import BeautifulSoup
from scripts.validate.content import ROOT,safe_proposal
AGENT='SupplyChainSkillsLab/1.0'
def stamp():return datetime.now(timezone.utc).isoformat()
def canonical(url):
 u=urlsplit(url);return urlunsplit((u.scheme,u.netloc.lower(),u.path.rstrip('/') or '/',urlencode([(k,v) for k,v in parse_qsl(u.query) if not k.startswith('utm_') and k not in ['ref','source']]),''))
def digest(text):return hashlib.sha256(text.encode()).hexdigest()
def public_url(url,allowed_hosts):
 u=urlsplit(url)
 if u.scheme!='https' or u.hostname not in allowed_hosts or u.username or u.port not in [None,443]:raise ValueError('URL outside source allowlist')
 for x in socket.getaddrinfo(u.hostname,443,type=socket.SOCK_STREAM):
  if not ipaddress.ip_address(x[4][0]).is_global:raise ValueError('Non-public source address')
def fetch(url,allowed_hosts):
 public_url(url,allowed_hosts)
 with httpx.Client(timeout=20,follow_redirects=False,headers={'User-Agent':AGENT}) as client:
  with client.stream('GET',url) as r:
   r.raise_for_status()
   if r.is_redirect:raise ValueError('Redirect requires manual source reconfiguration')
   chunks=[];size=0
   for chunk in r.iter_bytes():
    size+=len(chunk)
    if size>2_000_000:raise ValueError('Source response exceeds limit')
    chunks.append(chunk)
   return b''.join(chunks).decode('utf-8',errors='replace')
def normalize(html,selector):
 soup=BeautifulSoup(html,'html.parser')
 for tag in soup.select('script,style,nav,header,footer,aside,time,[role=navigation],.advertisement,.cookie-banner,.last-updated'):
  tag.decompose()
 nodes=soup.select(selector)
 if not nodes:raise ValueError('Configured main-content selector missing')
 text=' '.join(' '.join(n.stripped_strings) for n in nodes)
 text=re.sub(r'\s+',' ',text).strip()
 if len(text)<80:raise ValueError('Missing or unexpectedly short source content')
 return text

def process(config,state,loader=fetch):
 state=json.loads(json.dumps(state));state.setdefault('schema_version',1);state.setdefault('sources',{});state.setdefault('rejected',[]);state.setdefault('proposed',[]);state.setdefault('failures',{});state['last_attempt_at']=stamp()
 drafts=[];report=[];seen=set();successful=0;limit=min(max(int(config.get('max_updates',3)),0),10)
 for source in config['sources'][:min(config.get('max_sources',20),100)]:
  sid=source['id'];request_url=source['url'];url=canonical(request_url)
  if url in seen:report.append({'source':sid,'status':'duplicate_url'});continue
  seen.add(url)
  if not source.get('enabled') or not source.get('terms_reviewed'):
   report.append({'source':sid,'status':'disabled','reason':source.get('reason','使用条件尚未确认')});continue
  try:
   robots_url=urlsplit(url)._replace(path='/robots.txt',query='',fragment='').geturl()
   robots=RobotFileParser();robots.parse(loader(robots_url,source['allowed_hosts']).splitlines())
   if not robots.can_fetch(AGENT,request_url):raise ValueError('robots policy does not allow collection')
   if source.get('provider','public_page')!='public_page':raise ValueError('Provider disabled until API/RSS endpoint and usage terms are verified')
   text=normalize(loader(request_url,source['allowed_hosts']),source.get('selector','main'));content_hash=digest(text);old=state['sources'].get(sid);fingerprint=digest(url+'\n'+content_hash)
   if old and old['content_hash']==content_hash:
    state['sources'][sid]['checked_at']=stamp();report.append({'source':sid,'status':'unchanged'});successful+=1;state['failures'].pop(sid,None);continue
   if fingerprint in state['rejected'] or fingerprint in state['proposed']:
    state['sources'][sid]={'url':url,'content_hash':content_hash,'checked_at':stamp()};report.append({'source':sid,'status':'already_handled'});successful+=1;continue
   # First allowed observation establishes a baseline; it is not a fabricated new publication.
   if not old:
    state['sources'][sid]={'url':url,'content_hash':content_hash,'checked_at':stamp()};report.append({'source':sid,'status':'baseline_created'});successful+=1;state['failures'].pop(sid,None);continue
   if len(drafts)>=limit:report.append({'source':sid,'status':'deferred_by_limit'});continue
   item={'id':'update-'+fingerprint[:20],'version':1,'status':'draft','update_type':'evidence','title':source['title']+'：正文变化待核查','created_at':datetime.now(timezone.utc).date().isoformat(),'summary':'受控页面的正文指纹发生变化。此草稿不推断变化原因，也不声称出现了新的行业共识。','source_ids':[sid],'skill_ids':source['skill_ids'],'source_claim':'页面经过允许的公开访问；正文发生变化，专业结论尚待逐条人工提取与核查。','editorial_recommendation':'复核下列技能是否需要补充解释、练习或证据；现有课程正文不自动改写。','uncertainty':'页面变化不等于知识更新。仍需核查原文、适用对象、发布日期、地区及是否仅为宣传。','original_urls':[url],'impact':'仅增加草稿，不改变基础路线、已发布课程或个人学习记录。','checks':['来源域名白名单','robots 与配置的使用条件','正文去噪与 SHA-256 去重','结构化数据 schema'],'human_review':['比对原页面并定位实质变化','补充明确的 source_claim 与必要短摘录','确认适用岗位与地区','审核后自行决定是否发布']}
   safe_proposal('content/updates/'+item['id']+'.json',item)
   drafts.append({'path':'content/updates/'+item['id']+'.json','data':item,'fingerprint':fingerprint,'before_hash':old['content_hash'],'after_hash':content_hash})
   state['sources'][sid]={'url':url,'content_hash':content_hash,'checked_at':stamp()};state['proposed'].append(fingerprint);state['failures'].pop(sid,None);successful+=1;report.append({'source':sid,'status':'draft_created'})
  except Exception as e:
   previous=state['failures'].get(sid,{});state['failures'][sid]={'attempts':previous.get('attempts',0)+1,'last_at':stamp(),'error':type(e).__name__,'reason':str(e)[:160]};report.append({'source':sid,'status':'failed','reason':str(e)[:160]})
 if successful:state['last_success_at']=stamp()
 return {'schema_version':1,'drafts':drafts,'state':state,'report':report,'dry_run':True,'generated_at':stamp()}
def run():
 p=argparse.ArgumentParser();p.add_argument('--config',default='config/sources.yaml');p.add_argument('--state',default='state/collector.json');p.add_argument('--out',default='work/collection');p.add_argument('--commit-local-state',action='store_true');args=p.parse_args()
 state_path=Path(args.state);state=json.loads(state_path.read_text()) if state_path.exists() else {};config=yaml.safe_load(Path(args.config).read_text());result=process(config,state)
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True);(out/'proposal.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));(out/'report.json').write_text(json.dumps({'dry_run':True,'generated_at':result['generated_at'],'draft_count':len(result['drafts']),'sources':result['report']},ensure_ascii=False,indent=2))
 if args.commit_local_state:state_path.parent.mkdir(parents=True,exist_ok=True);temp=state_path.with_suffix('.tmp');temp.write_text(json.dumps(result['state'],ensure_ascii=False,indent=2));temp.replace(state_path)
 print(json.dumps({'dry_run':True,'drafts':len(result['drafts']),'report':str(out/'report.json'),'checkpoint_written':args.commit_local_state},ensure_ascii=False))
if __name__=='__main__':run()
