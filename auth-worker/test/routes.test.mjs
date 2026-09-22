import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import worker from '../src/index.mjs';
import {random,hash,seal} from '../src/security.mjs';

const origin='https://learner.example';
function environment(t){
 const db=new DatabaseSync(':memory:');
 db.exec(readFileSync(new URL('../migrations/0001_sessions.sql',import.meta.url),'utf8'));
 t.after(()=>db.close());
 return {db,env:{SITE_URL:origin+'/lab/',GITHUB_CLIENT_ID:'test-client',GITHUB_APP_SLUG:'test-app',GITHUB_CLIENT_SECRET:'test-secret',
 TOKEN_ENCRYPTION_KEY:Buffer.from(crypto.getRandomValues(new Uint8Array(32))).toString('base64'),
 DB:{prepare(sql){const query=db.prepare(sql);let values=[];const wrapper={bind(...args){values=args;return wrapper},async first(){return query.get(...values)??null},async run(){return query.run(...values)}};return wrapper}}}};
}
function request(path,{token,body,headers={},method}={}){
 return new Request('https://auth.example'+path,{method:method??(body===undefined?'GET':'POST'),
 headers:{Origin:origin,...(token?{Authorization:'Bearer '+token}:{}),...(body===undefined?{}:{'Content-Type':'application/json'}),...headers},
 body:body===undefined?undefined:JSON.stringify(body)});
}
async function loginSession(env,userId=11){
 const opaque=random();
 await env.DB.prepare('INSERT INTO sessions(id,user_id,login,token_cipher,expires) VALUES(?,?,?,?,?)').bind(await hash(opaque),userId,'alice',await seal('github-test-token',env.TOKEN_ENCRYPTION_KEY),Math.floor(Date.now()/1000)+600).run();
 await env.DB.prepare('INSERT INTO accounts(user_id) VALUES(?)').bind(userId).run();
 return opaque;
}

test('all personal endpoints reject anonymous calls and wrong origins',async t=>{
 const {env}=environment(t);
 for(const path of ['/api/me','/api/repos','/api/state','/api/repository','/api/sync','/api/logout']){
  const r=await worker.fetch(request(path),env);assert.equal(r.status,401,path);
 }
 const token=await loginSession(env);
 const r=await worker.fetch(request('/api/me',{token,headers:{Origin:'https://other.example'}}),env);
 assert.equal(r.status,403);
 assert.equal((await worker.fetch(request('/api/me',{token}),env)).status,200);
});

test('OAuth browser binding, PKCE handoff, one-time exchange and logout',async t=>{
 const {env,db}=environment(t);const verifier=random();const challenge=await hash(verifier);
 const realFetch=globalThis.fetch;let githubVerifier;
 globalThis.fetch=async(url,options)=>{
  if(url==='https://github.com/login/oauth/access_token'){
   const payload=JSON.parse(options.body);githubVerifier=payload.code_verifier;
   assert.equal(payload.client_secret,'test-secret');
   return Response.json({access_token:'never-send-to-browser',expires_in:28800});
  }
  assert.equal(url,'https://api.github.com/user');return Response.json({id:11,login:'alice'});
 };t.after(()=>{globalThis.fetch=realFetch});
 const start=await worker.fetch(request('/auth/start?challenge='+challenge),env);
 assert.equal(start.status,302);
 const target=new URL(start.headers.get('location'));
 assert.equal(target.origin,'https://github.com');
 assert.equal(target.searchParams.get('code_challenge_method'),'S256');
 const cookie=start.headers.get('set-cookie').split(';')[0];
 const callback='/auth/callback?code=test-code&state='+target.searchParams.get('state');
 assert.equal((await worker.fetch(request(callback),env)).status,400);
 const result=await worker.fetch(request(callback,{headers:{Cookie:cookie}}),env);
 assert.equal(result.status,302);
 assert.equal(await hash(githubVerifier),target.searchParams.get('code_challenge'));
 const location=result.headers.get('location');assert(!location.includes('never-send-to-browser'));
 const ticket=new URL(location).hash.slice(6);
 assert.equal((await worker.fetch(request(callback,{headers:{Cookie:cookie}}),env)).status,400);
 assert.equal((await worker.fetch(request('/api/exchange',{body:{ticket,verifier:random()}}),env)).status,401);
 const exchanged=await worker.fetch(request('/api/exchange',{body:{ticket,verifier}}),env);
 assert.equal(exchanged.status,200);const {session}=await exchanged.json();assert.match(session,/^[\w-]{43}$/);
 assert.equal((await worker.fetch(request('/api/exchange',{body:{ticket,verifier}}),env)).status,401);
 const saved=db.prepare('SELECT token_cipher FROM sessions').get();assert(!saved.token_cipher.includes('never-send-to-browser'));
 assert.equal((await worker.fetch(request('/api/me',{token:session}),env)).status,200);
 assert.equal((await worker.fetch(request('/api/logout',{token:session,body:{}}),env)).status,200);
 assert.equal((await worker.fetch(request('/api/me',{token:session}),env)).status,401);
});

test('repository selection rejects another owner and a public repository before writes',async t=>{
 const {env,db}=environment(t);const token=await loginSession(env);const realFetch=globalThis.fetch;
 const calls=[];let response={full_name:'bob/notes',private:true,owner:{id:22},permissions:{push:true}};
 globalThis.fetch=async(url,options)=>{calls.push({url,method:options.method});return Response.json(response)};
 t.after(()=>{globalThis.fetch=realFetch});
 assert.equal((await worker.fetch(request('/api/repository',{token,body:{repository:'bob/notes'}}),env)).status,403);
 response={...response,full_name:'alice/public',private:false,owner:{id:11}};
 assert.equal((await worker.fetch(request('/api/repository',{token,body:{repository:'alice/public'}}),env)).status,403);
 assert.equal(db.prepare('SELECT repository FROM accounts WHERE user_id=11').get().repository,null);
 assert(calls.every(c=>c.method==='GET'));
});

test('sync refuses stale versions before writing any GitHub data',async t=>{
 const {env}=environment(t);const token=await loginSession(env);
 await env.DB.prepare('UPDATE accounts SET repository=? WHERE user_id=?').bind('alice/notes',11).run();
 const state={schema_version:1,revision:0,profile:null,progress:[],exposures:[],attempts:[],notes:[],submissions:[],plan:[],bookmarks:[]};
 const realFetch=globalThis.fetch;const methods=[];
 globalThis.fetch=async(url,options)=>{
  methods.push(options.method);
  if(url==='https://api.github.com/repos/alice/notes')return Response.json({private:true,owner:{id:11,login:'alice'},permissions:{push:true},full_name:'alice/notes',default_branch:'main'});
  if(url.includes('/pulls?'))return Response.json([]);
  if(url.includes('/contents/'))return Response.json({type:'file',encoding:'base64',size:150,sha:'remote-current-sha',content:Buffer.from(JSON.stringify(state)).toString('base64')});
  throw Error('Unexpected request');
 };t.after(()=>{globalThis.fetch=realFetch});
 const r=await worker.fetch(request('/api/sync',{token,body:{state,expected_sha:'old-sha'}}),env);
 assert.equal(r.status,409);assert(methods.every(m=>m==='GET'));
});
