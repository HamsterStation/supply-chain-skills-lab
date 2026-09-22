import type {State} from './types';
let account='local-preview';
let generation=0;
export const getAccount=()=>account;
export function selectAccount(id:string){account=id;generation++;dbPromise=undefined as unknown as Promise<IDBDatabase>;}
const dbName=()=>'supply-chain-skills-lab-v1-'+account;
export const emptyState=():State=>({schema_version:1,revision:0,profile:null,progress:[],exposures:[],attempts:[],notes:[],submissions:[],plan:[],bookmarks:[]});
let dbPromise:Promise<IDBDatabase>;
function db(){return dbPromise??=(new Promise((resolve,reject)=>{const r=indexedDB.open(dbName(),1);r.onupgradeneeded=()=>r.result.createObjectStore('local',{keyPath:'key'});r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(Error('浏览器无法打开本机学习记录。请检查存储权限。'));}));}
export async function read():Promise<State>{const d=await db();return new Promise((resolve,reject)=>{const tx=d.transaction('local');const r=tx.objectStore('local').get('state');r.onsuccess=()=>resolve(r.result?.value??emptyState());r.onerror=()=>reject(Error('读取学习记录失败，请保留当前页面并重试。'));});}
export async function mutate(fn:(s:State)=>void):Promise<State>{const epoch=generation;const d=await db();if(epoch!==generation)throw Error('账号已切换，请重新保存');return new Promise((resolve,reject)=>{const tx=d.transaction('local','readwrite');const store=tx.objectStore('local');const r=store.get('state');let next:State;r.onsuccess=()=>{try{if(epoch!==generation)throw Error('账号已切换');next=r.result?.value??emptyState();fn(next);next.revision++;store.put({key:'state',value:next});}catch(e){tx.abort();reject(e);}};tx.oncomplete=()=>resolve(next);tx.onerror=()=>reject(Error('保存失败：请检查浏览器可用空间，当前输入尚未保存。'));});}
export function download(name:string,value:unknown){const data=typeof value==='string'?value:JSON.stringify(value,null,2);const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([data],{type:'application/json;charset=utf-8'}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),5000);}
const listKeys=['progress','exposures','attempts','notes','submissions','plan','bookmarks'] as const;
export function validateBackup(v:unknown):State{
 if(!v||typeof v!=='object')throw Error('备份格式不正确');const s=v as State;
 if(s.schema_version!==1||!Number.isInteger(s.revision)||listKeys.some(k=>!Array.isArray(s[k])))throw Error('不支持的备份版本或格式');
 if(Object.keys(s).some(k=>!['schema_version','revision','profile',...listKeys].includes(k)))throw Error('备份包含未知字段');
 if(JSON.stringify(s).length>10_000_000)throw Error('备份超过 10 MB 上限');
 const isString=(x:unknown)=>typeof x==='string'&&x.length<=24000;
 const validId=(x:unknown)=>typeof x==='string'&&/^[a-zA-Z0-9-]{1,100}$/.test(x);
 if(s.plan.some(x=>!validId(x))||s.bookmarks.some(x=>!validId(x)))throw Error('备份路线格式有误');
 for(const k of ['progress','exposures','attempts','notes','submissions'] as const){
  if(s[k].length>20000)throw Error('单类记录数量超限');
  for(const r of s[k])if(!r||!validId(r.id)||!isString(r.updated_at)||!Number.isFinite(Date.parse(r.updated_at))||!Number.isInteger(r.content_version))throw Error('备份记录缺少有效 ID、版本或时间');
 }
 for(const r of s.notes)if(!validId(r.entity_id)||!isString(r.body))throw Error('笔记格式错误');
 for(const r of s.progress)if(!validId(r.lesson_id)||!['read','attempted','assisted','independent','mastered','review','skipped'].includes(r.status)||(r.review_at!==null&&!Number.isFinite(Date.parse(r.review_at))))throw Error('进度格式错误');
 for(const r of s.exposures)if(!validId(r.question_id)||!['hint','answer'].includes(r.kind))throw Error('提示记录格式错误');
 for(const r of s.attempts)if(!validId(r.lesson_id)||!r.question||!validId(r.question.id)||!isString(r.question.prompt)||!Number.isFinite(r.value)||!Number.isFinite(r.question.answer)||typeof r.correct!=='boolean'||typeof r.assisted!=='boolean')throw Error('作答格式错误');
 for(const r of s.submissions)if(!validId(r.case_id)||!isString(r.memo)||!r.snapshot||r.snapshot.id!==r.case_id||!Array.isArray(r.feedback)||!Array.isArray(r.rubric)||!r.values||Object.values(r.values).some(x=>!Number.isFinite(x))||r.feedback.some(x=>!isString(x.label)||!Number.isFinite(x.expected)||!Number.isFinite(x.actual)||typeof x.correct!=='boolean')||r.rubric.some(x=>!isString(x)))throw Error('作品记录格式错误');
 if(s.profile!==null){if(!s.profile||typeof s.profile!=='object'||!Number.isFinite(s.profile.reviewDays)||s.profile.reviewDays<1||s.profile.reviewDays>365)throw Error('学习设置格式错误');for(const k of ['direction','industry','region','experience','basics','problem','tools','weeklyHours','updated_at'] as const)if(!isString(s.profile[k]))throw Error('学习设置格式错误');}
 return s;
}
export function mergeBackup(current:State,incoming:State){
 for(const k of ['progress','exposures','attempts','notes','submissions'] as const){
  const target=current[k] as {id:string}[];const ids=new Map(target.map(x=>[x.id,JSON.stringify(x)]));
  for(const row of incoming[k]){if(ids.has(row.id)&&ids.get(row.id)!==JSON.stringify(row))throw Error('同一记录 ID 存在冲突；未恢复，当前记录未改变。');if(!ids.has(row.id))target.push(row);}
 }
 current.plan=[...new Set([...current.plan,...incoming.plan])];current.bookmarks=[...new Set([...current.bookmarks,...incoming.bookmarks])];if(!current.profile)current.profile=incoming.profile;
}
