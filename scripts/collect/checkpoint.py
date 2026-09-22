import json,os
from pathlib import Path
from scripts.collect.github_pr import GitHub,STATE_BRANCH,STATE_PATH
if __name__=='__main__':
 gh=GitHub(os.environ['GITHUB_REPOSITORY'],os.environ['GITHUB_TOKEN']);ref=gh.ref(STATE_BRANCH);state=gh.read_file(STATE_PATH,STATE_BRANCH) if ref else {}
 Path('state').mkdir(exist_ok=True);Path('state/collector.json').write_text(json.dumps(state or {}));Path('state/expected.json').write_text(json.dumps(ref['object']['sha'] if ref else None))
