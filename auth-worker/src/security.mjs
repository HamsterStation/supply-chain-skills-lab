const encoder=new TextEncoder();
export const b64=(bytes)=>{let out='';for(let i=0;i<bytes.length;i+=8192)out+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(out)};
export const unb64=(s)=>Uint8Array.from(atob(s),x=>x.charCodeAt(0));
export const base64url=(bytes)=>b64(bytes).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');
export const random=()=>base64url(crypto.getRandomValues(new Uint8Array(32)));
export async function hash(text){return base64url(new Uint8Array(await crypto.subtle.digest('SHA-256',encoder.encode(text))));}
export async function seal(value,secret){const key=await crypto.subtle.importKey('raw',unb64(secret),{name:'AES-GCM'},false,['encrypt']);const iv=crypto.getRandomValues(new Uint8Array(12));return b64(iv)+'.'+b64(new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv},key,encoder.encode(value))));}
export async function unseal(value,secret){const [iv,data]=value.split('.');const key=await crypto.subtle.importKey('raw',unb64(secret),{name:'AES-GCM'},false,['decrypt']);return new TextDecoder().decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:unb64(iv)},key,unb64(data)));}
export function validateState(s){
 if(!s||s.schema_version!==1||!Number.isInteger(s.revision))throw Error('invalid_state');
 const arrays=['progress','exposures','attempts','notes','submissions','plan','bookmarks'];
 if(Object.keys(s).some(k=>!['schema_version','revision','profile',...arrays].includes(k))||arrays.some(k=>!Array.isArray(s[k])||s[k].length>20000))throw Error('invalid_state');
 if(new TextEncoder().encode(JSON.stringify(s)).length>750000)throw Error('state_too_large');
 const validId=x=>typeof x==='string'&&/^[a-zA-Z0-9-]{1,100}$/.test(x);
 for(const k of ['progress','exposures','attempts','notes','submissions'])for(const r of s[k]){
  if(!r||!validId(r.id)||!Number.isInteger(r.content_version)||typeof r.updated_at!=='string'||!Number.isFinite(Date.parse(r.updated_at)))throw Error('invalid_record');
  if(k==='notes'&&(typeof r.body!=='string'||r.body.length>12000))throw Error('invalid_note');
  if(k==='submissions'&&(typeof r.memo!=='string'||r.memo.length>12000||!r.snapshot||!Array.isArray(r.feedback)||!Array.isArray(r.rubric)))throw Error('invalid_submission');
  if(k==='attempts'&&(!r.question||!Number.isFinite(r.value)||typeof r.correct!=='boolean'))throw Error('invalid_attempt');
 }
 for(const k of ['plan','bookmarks'])if(s[k].some(x=>!validId(x)))throw Error('invalid_plan');
 return s;
}
export function ensureNoLoss(previous,next){
 validateState(next);
 if(!previous)return;
 for(const k of ['progress','exposures','attempts','notes','submissions']){
  const records=new Map(next[k].map(x=>[x.id,JSON.stringify(x)]));
  for(const item of previous[k])if(records.get(item.id)!==JSON.stringify(item))throw Error('remote_records_not_merged');
 }
}
export function ownPrivateRepo(repo,userId){return repo?.private===true&&repo.owner?.id===userId&&repo.permissions?.push===true&&!repo.archived&&!repo.disabled;}
