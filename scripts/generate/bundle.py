import json,datetime,os
from pathlib import Path
import yaml
from scripts.validate.content import validate,load,ROOT
from scripts.generate.reference import export,references
if __name__=='__main__':
 validate();export();data=load();data['tracks']=yaml.safe_load((ROOT/'config/learning-tracks.yaml').read_text());data['references']=references()
 success_at=None
 checkpoint=ROOT/'state/collector.json'
 if checkpoint.exists():
  stamp=json.loads(checkpoint.read_text()).get('last_success_at')
  if stamp:
   checked=datetime.datetime.fromisoformat(stamp)
   if checked.tzinfo and checked<=datetime.datetime.now(datetime.timezone.utc):success_at=checked.isoformat()
 data['release']={'built_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'revision':os.environ.get('GITHUB_SHA','local'),'collector_success_at':success_at}
 data['updates']=[x for x in data['updates'] if x['status']=='published']
 target=ROOT/'frontend/public/content.json';target.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
 print('Public content bundle created; no personal state included.')
