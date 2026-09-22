"""Deterministic reference calculations; no network and no model."""
import math,json,csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def mean(values):
 if not values or any(v is None or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in values):raise ValueError('Need finite nonnegative observations; missing is not zero')
 return sum(values)/len(values)
def percent(n,d):
 if d==0:return None
 return n/d*100

def inventory(row,multiplier=1):
 d=mean(row['demand_28_days'])*multiplier
 for key in ['on_hand','on_order','backlog','lead_days','review_days','buffer_units']:
  if row[key]<0:raise ValueError(key)
 ip=row['on_hand']+row['on_order']-row['backlog'];target=d*(row['lead_days']+row['review_days'])+row['buffer_units']
 days=(row['on_hand']-row['backlog'])/d if d else None
 return {'sku':row['sku'],'daily_demand':round(d,6),'ip':ip,'target':round(target,6),'quantity':math.ceil(max(0,target-ip)),'days_on_hand':round(days,3) if days is not None else None,'prearrival_risk':bool(row['on_order'] and days is not None and days<row['arrival_day']),'sample_value':round(sum(row['demand_28_days'])*row['unit_cost_cny'],2)}
def supplier(row,demand=100):
 if demand<0 or row['moq_units']<0 or row['unit_price_cny']<0 or row['freight_cny']<0:raise ValueError('Negative inputs')
 q=max(demand,row['moq_units'])
 return {'supplier':row['supplier'],'quantity':q,'known_cash_cost':q*row['unit_price_cny']+row['freight_cny'],'excess':q-demand,'within_deadline':row['lead_days']<=10}
def references():
 a=json.loads((ROOT/'content/cases/case-inventory.json').read_text());b=json.loads((ROOT/'content/cases/case-supplier.json').read_text())
 return {'case-inventory':{'baseline':[inventory(r) for r in a['rows']],'demand_plus_20_percent':[inventory(r,1.2) for r in a['rows']]},'case-supplier':[supplier(r) for r in b['rows']]}
def export():
 target=ROOT/'frontend/public/data';target.mkdir(parents=True,exist_ok=True)
 refs=references();(target/'references.json').write_text(json.dumps(refs,ensure_ascii=False,indent=2))
 for case in ['case-inventory','case-supplier']:
  data=json.loads((ROOT/f'content/cases/{case}.json').read_text());rows=[]
  for row in data['rows']:
   copy={k:v for k,v in row.items() if k!='demand_28_days'}
   for i,v in enumerate(row.get('demand_28_days',[])):copy[f'demand_day_{i+1}']=v
   rows.append(copy)
  with (target/f'{case}.csv').open('w',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
  (target/f'{case}-dictionary.json').write_text(json.dumps({'synthetic':True,'seed':data['seed'],'version':data['version'],'dictionary':data['dictionary'],'limitations':data['limitations']},ensure_ascii=False,indent=2))
 if __name__=='__main__':print(json.dumps(refs,ensure_ascii=False))
if __name__=='__main__':export()
