import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {Miniflare,convertV4MiniflareOptions} from 'miniflare';
import {random,hash} from '../src/security.mjs';

test('real workerd and D1 complete login with mocked GitHub upstream',async()=>{
 const origin='https://learner.example';let tokenRequests=0;
 const mf=new Miniflare(convertV4MiniflareOptions({
  modules:['index.mjs','security.mjs'].map(name=>({type:'ESModule',path:name,contents:readFileSync(new URL('../src/'+name,import.meta.url),'utf8')})),
  compatibilityDate:'2026-09-22',d1Databases:{DB:'local-auth-test'},
  bindings:{SITE_URL:origin+'/',GITHUB_CLIENT_ID:'test-client',GITHUB_APP_SLUG:'test-app',GITHUB_CLIENT_SECRET:'test-secret',TOKEN_ENCRYPTION_KEY:Buffer.alloc(32,7).toString('base64')},
  outboundService:async request=>{
   if(request.url==='https://github.com/login/oauth/access_token'){
    tokenRequests++;assert.equal(request.method,'POST');
    const data=await request.json();assert.equal(data.client_secret,'test-secret');
    return Response.json({access_token:'runtime-test-token',expires_in:28800});
   }
   assert.equal(request.url,'https://api.github.com/user');
   return Response.json({id:11,login:'runtime-test'});
  }
 }));
 try{
  const db=await mf.getD1Database('DB');
  for(const statement of readFileSync(new URL('../migrations/0001_sessions.sql',import.meta.url),'utf8').split(';').filter(x=>x.trim()))await db.prepare(statement).run();
  const verifier=random();
  const start=await mf.dispatchFetch('https://auth.example/auth/start?challenge='+await hash(verifier),{redirect:'manual'});
  assert.equal(start.status,302);
  const cookie=start.headers.get('set-cookie').split(';')[0];
  const state=new URL(start.headers.get('location')).searchParams.get('state');
  const callback=await mf.dispatchFetch('https://auth.example/auth/callback?code=test-code&state='+state,{headers:{Cookie:cookie},redirect:'manual'});
  assert.equal(callback.status,302,await callback.text());assert.equal(tokenRequests,1);
  const ticket=new URL(callback.headers.get('location')).hash.slice(6);
  const exchanged=await mf.dispatchFetch('https://auth.example/api/exchange',{method:'POST',headers:{Origin:origin,'Content-Type':'application/json'},body:JSON.stringify({ticket,verifier})});
  assert.equal(exchanged.status,200);const {session}=await exchanged.json();
  const me=await mf.dispatchFetch('https://auth.example/api/me',{headers:{Origin:origin,Authorization:'Bearer '+session}});
  assert.equal(me.status,200);assert.equal((await me.json()).user.login,'runtime-test');
 }finally{await mf.dispose()}
});
