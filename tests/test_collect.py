import copy,json
from scripts.collect.pipeline import process,normalize,canonical
from scripts.collect.github_pr import validate_proposal
TEXT='This is an original mock source used only in automated tests. It contains a long stable body for checking duplicate fingerprints and content changes. '
def config():return {'max_updates':3,'sources':[{'id':'mit-scm','title':'Mock source','url':'https://example.org/page','allowed_hosts':['example.org'],'enabled':True,'terms_reviewed':True,'selector':'main','skill_ids':['flow']}]}
def loader(url,hosts):return 'User-agent: *\nAllow: /' if url.endswith('robots.txt') else '<main>'+TEXT+'</main><nav>old menu</nav>'
def test_initial_baseline_then_unchanged_no_pr():
 a=process(config(),{},loader);assert a['drafts']==[]
 b=process(config(),a['state'],loader);assert b['drafts']==[];assert b['report'][0]['status']=='unchanged'
def test_changed_once_and_rejection_survives():
 a=process(config(),{},loader)
 def changed(url,h):return loader(url,h).replace('long stable body','different substantive body')
 b=process(config(),a['state'],changed);assert len(b['drafts'])==1;validate_proposal(b)
 c=process(config(),b['state'],changed);assert c['drafts']==[]
 a['state']['rejected']=[b['drafts'][0]['fingerprint']]
 assert process(config(),a['state'],changed)['drafts']==[]
def test_noise_and_duplicates_and_failure():
 a=process(config(),{},loader)
 def noisy(url,h):return loader(url,h).replace('old menu','new menu at 2026-01-01')
 assert process(config(),a['state'],noisy)['drafts']==[]
 cfg=config();cfg['sources']+=copy.deepcopy(cfg['sources']);r=process(cfg,a['state'],loader);assert r['report'][1]['status']=='duplicate_url'
 def fail(url,h):raise TimeoutError('test timeout')
 r=process(config(),a['state'],fail);assert r['state']['sources']==a['state']['sources'];assert r['state']['failures'];assert not r['drafts']
def test_limit_retry_and_disabled():
 cfg=config();cfg['sources'][0]['enabled']=False;assert process(cfg,{},loader)['report'][0]['status']=='disabled'
 assert canonical('https://EXAMPLE.org/page/?utm_source=x#frag')=='https://example.org/page'
 def denied(url,h):return 'User-agent: *\nDisallow: /'
 r=process(config(),{},denied);assert r['report'][0]['status']=='failed';assert not r['drafts']
