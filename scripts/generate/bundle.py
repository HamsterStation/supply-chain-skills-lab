import json,datetime,os
from pathlib import Path
import yaml
from scripts.validate.content import validate,load,ROOT
from scripts.generate.reference import export,references
if __name__=='__main__':
 validate();export();data=load();data['tracks']=yaml.safe_load((ROOT/'config/learning-tracks.yaml').read_text());data['references']=references()
 data['release']={'built_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'revision':os.environ.get('GITHUB_SHA','local'),'collector_success_at':None}
 status=ROOT/'content/updates/collector-status.json'
 data['updates']=[x for x in data['updates'] if x['status']=='published']
 target=ROOT/'frontend/public/content.json';target.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
 print('Public content bundle created; no personal state included.')
