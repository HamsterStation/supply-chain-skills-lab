import {hash,random,seal,unseal,b64,unb64,validateState,ensureNoLoss,ownPrivateRepo} from './security.mjs';
const API='https://api.github.com';const FILE='learning/state.json';const BRANCH='supply-chain-learning';const now=()=>Math.floor(Date.now()/1000);
class Fault extends Error{constructor(status,message){super(message);this.status=status}}
const fail=(status,message)=>{throw new Fault(status,message)};
async function body(request,max=800000){const len=Number(request.headers.get('content-length')||0);if(len>max)fail(413,'内容太大，请先导出归档');if(!request.headers.get('content-type')?.startsWith('application/json'))fail(415,'仅接受 JSON');const reader=request.body?.getReader();let chunks=[],size=0;while(reader){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>max){await reader.cancel();fail(413,'内容太大，请先导出归档')}chunks.push(value)}const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length}try{return JSON.parse(new TextDecoder().decode(bytes))}catch{fail(400,'JSON 格式错误')}}
async function github(token,path,method='GET',data,optional=false){
 const response=await fetch(API+path,{method,headers:{Authorization:'Bearer '+token,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2026-03-10','User-Agent':'SupplyChainSkillsLab','Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data),signal:AbortSignal.timeout(15000),redirect:'manual'});
 if(optional&&response.status===404)return null;
 if(!response.ok){if(response.status===401)fail(401,'GitHub 授权已失效，请重新登录');if(response.status===409||response.status===422)fail(409,'仓库已变化或存在分支冲突，请先重新读取');if(response.status===403)fail(403,'请检查 GitHub App 的所选仓库权限或请求额度');fail(502,'GitHub 请求失败，请稍后重试')}
 return response.status===204?null:response.json();
}
async function limit(env,key,max,seconds){const bucket=key+':'+Math.floor(now()/seconds);const result=await env.DB.prepare('INSERT INTO rate_limits(bucket,count,expires) VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1 RETURNING count').bind(bucket,now()+seconds).first();if(result.count>max)fail(429,'请求过于频繁，请稍后再试')}
async function session(request,env){const auth=request.headers.get('authorization')??'';if(!/^Bearer [A-Za-z0-9_-]{43}$/.test(auth))fail(401,'请先用 GitHub 登录');const s=await env.DB.prepare('SELECT * FROM sessions WHERE id=? AND expires>?').bind(await hash(auth.slice(7)),now()).first();if(!s)fail(401,'登录已过期，请重新登录');s.token=await unseal(s.token_cipher,env.TOKEN_ENCRYPTION_KEY);return s;}
async function accountRepo(env,s){const a=await env.DB.prepare('SELECT * FROM accounts WHERE user_id=?').bind(s.user_id).first();if(!a?.repository)fail(409,'请先选择自己的私有学习记录仓库');const repo=await github(s.token,'/repos/'+a.repository);if(!ownPrivateRepo(repo,s.user_id))fail(403,'仓库必须是本人拥有、可写的私有仓库');return repo}
async function pending(token,repo){const list=await github(token,`/repos/${repo.full_name}/pulls?state=open&head=${encodeURIComponent(repo.owner.login+':'+BRANCH)}&base=${encodeURIComponent(repo.default_branch)}&per_page=10`);if(list.length>1)fail(409,'发现多个学习记录 PR，请先处理');return list[0]??null}
async function readRemote(s,repo){
 const pr=await pending(s.token,repo);const ref=pr?BRANCH:repo.default_branch;const data=await github(s.token,`/repos/${repo.full_name}/contents/${FILE}?ref=${encodeURIComponent(ref)}`,'GET',undefined,true);
 if(data&&(data.type!=='file'||data.encoding!=='base64'||data.size>750000))fail(409,'远程记录格式或大小不受支持');
 let state=null;if(data){try{state=validateState(JSON.parse(new TextDecoder().decode(unb64(data.content.replaceAll('\n','')))))}catch{fail(409,'远程记录校验失败；未覆盖任何记录')}}
 return {state,sha:data?.sha??null,pr_url:pr?.html_url??null,ref};
}
export default {async fetch(request,env){
 const url=new URL(request.url);const allowed=new URL(env.SITE_URL).origin;const origin=request.headers.get('origin');const cors={'Access-Control-Allow-Origin':allowed,'Access-Control-Allow-Headers':'Authorization, Content-Type','Access-Control-Allow-Methods':'GET, POST, OPTIONS','Vary':'Origin','Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff'};
 let phase='request';
 const json=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{...cors,'Content-Type':'application/json'}});
 try{
  if(url.pathname==='/health')return json({ready:!!env.GITHUB_CLIENT_SECRET&&!!env.TOKEN_ENCRYPTION_KEY&&!env.GITHUB_CLIENT_ID.startsWith('CONFIGURE')});
  if(request.method==='OPTIONS'){if(origin!==allowed)fail(403,'来源不允许');return new Response(null,{status:204,headers:cors})}
  if(url.pathname.startsWith('/api/')&&origin!==allowed)fail(403,'来源不允许');
  if(!env.GITHUB_CLIENT_SECRET||!env.TOKEN_ENCRYPTION_KEY||env.GITHUB_CLIENT_ID.startsWith('CONFIGURE'))fail(503,'登录服务尚未配置');
  if(url.pathname==='/auth/start'&&request.method==='GET'){
   const challenge=url.searchParams.get('challenge');if(!/^[A-Za-z0-9_-]{43}$/.test(challenge??''))fail(400,'缺少登录请求校验信息');
   await limit(env,'login:'+await hash(request.headers.get('cf-connecting-ip')??'unknown'),20,600);
   const state=random(),binding=random(),verifier=random();await env.DB.prepare('INSERT INTO oauth_states(id,verifier,binding,app_challenge,expires) VALUES(?,?,?,?,?)').bind(await hash(state),verifier,await hash(binding),challenge,now()+600).run();
   const target=new URL('https://github.com/login/oauth/authorize');for(const[k,v]of Object.entries({client_id:env.GITHUB_CLIENT_ID,redirect_uri:url.origin+'/auth/callback',state,code_challenge:await hash(verifier),code_challenge_method:'S256',prompt:'select_account'}))target.searchParams.set(k,v);
   return new Response(null,{status:302,headers:{Location:target.href,'Set-Cookie':`__Host-scsl-oauth=${binding}; Secure; HttpOnly; SameSite=Lax; Path=/; Max-Age=600`,'Cache-Control':'no-store','Referrer-Policy':'no-referrer'}});
  }
  if(url.pathname==='/auth/callback'&&request.method==='GET'){
   const state=url.searchParams.get('state'),code=url.searchParams.get('code');const binding=(request.headers.get('cookie')??'').split('; ').find(x=>x.startsWith('__Host-scsl-oauth='))?.split('=')[1];if(!state||!code||!binding)fail(400,'登录回调无效，请重新开始');
   phase='login_state';const stored=await env.DB.prepare('DELETE FROM oauth_states WHERE id=? AND binding=? AND expires>? RETURNING *').bind(await hash(state),await hash(binding),now()).first();if(!stored)fail(400,'登录请求已失效或不属于此浏览器');
   phase='login_token_request';const tokenResponse=await fetch('https://github.com/login/oauth/access_token',{method:'POST',headers:{Accept:'application/json','Content-Type':'application/json','User-Agent':'SupplyChainSkillsLab'},body:JSON.stringify({client_id:env.GITHUB_CLIENT_ID,client_secret:env.GITHUB_CLIENT_SECRET,code,code_verifier:stored.verifier,redirect_uri:url.origin+'/auth/callback'}),signal:AbortSignal.timeout(15000),redirect:'manual'});phase='login_token_response';if(tokenResponse.status>=300&&tokenResponse.status<400)fail(502,'GitHub 登录服务返回了未预期的跳转，请稍后重试');const tokens=await tokenResponse.json().catch(()=>fail(502,'GitHub 登录服务返回了异常响应，请从网站重新登录'));if(!tokenResponse.ok||!tokens.access_token)fail(401,'GitHub 登录未完成');
   phase='login_user';const user=await github(tokens.access_token,'/user');const opaque=random(),ticket=random();const expires=now()+Math.min(Number(tokens.expires_in)||28800,28800);
   phase='login_session';await env.DB.prepare('INSERT INTO sessions(id,user_id,login,token_cipher,expires) VALUES(?,?,?,?,?)').bind(await hash(opaque),user.id,user.login,await seal(tokens.access_token,env.TOKEN_ENCRYPTION_KEY),expires).run();
   phase='login_account';await env.DB.prepare('INSERT INTO accounts(user_id) VALUES(?) ON CONFLICT(user_id) DO NOTHING').bind(user.id).run();
   phase='login_handoff';await env.DB.prepare('INSERT INTO handoffs(id,session_id,app_challenge,expires) VALUES(?,?,?,?)').bind(await hash(ticket),await seal(opaque,env.TOKEN_ENCRYPTION_KEY),stored.app_challenge,now()+60).run();
   // GitHub credentials never reach the browser. A one-use, PKCE-bound ticket travels in the fragment.
   return new Response(null,{status:302,headers:{Location:env.SITE_URL+'#auth/'+ticket,'Set-Cookie':'__Host-scsl-oauth=; Secure; HttpOnly; SameSite=Lax; Path=/; Max-Age=0','Cache-Control':'no-store','Referrer-Policy':'no-referrer'}});
  }
  if(url.pathname==='/api/exchange'&&request.method==='POST'){
   const data=await body(request,2000);if(typeof data.ticket!=='string'||typeof data.verifier!=='string')fail(400,'无效登录凭证');
   const row=await env.DB.prepare('DELETE FROM handoffs WHERE id=? AND app_challenge=? AND expires>? RETURNING *').bind(await hash(data.ticket),await hash(data.verifier),now()).first();if(!row)fail(401,'登录凭证已过期或已使用');return json({session:await unseal(row.session_id,env.TOKEN_ENCRYPTION_KEY)});
  }
  const s=await session(request,env);await limit(env,'api:'+s.user_id,120,60);
  if(url.pathname==='/api/me'&&request.method==='GET'){const a=await env.DB.prepare('SELECT repository,last_sync_at FROM accounts WHERE user_id=?').bind(s.user_id).first();return json({user:{id:s.user_id,login:s.login},repository:a?.repository??null,last_sync_at:a?.last_sync_at??null,install_url:`https://github.com/apps/${encodeURIComponent(env.GITHUB_APP_SLUG)}/installations/new`})}
  if(url.pathname==='/api/logout'&&request.method==='POST'){await env.DB.prepare('DELETE FROM sessions WHERE id=?').bind(s.id).run();return json({ok:true})}
  if(url.pathname==='/api/repos'&&request.method==='GET'){
   const repos=[];for(let p=1;p<=10;p++){const installations=await github(s.token,`/user/installations?per_page=100&page=${p}`);for(const installation of installations.installations??[]){for(let page=1;page<=10;page++){const data=await github(s.token,`/user/installations/${installation.id}/repositories?per_page=100&page=${page}`);repos.push(...data.repositories.filter(r=>ownPrivateRepo(r,s.user_id)).map(r=>({full_name:r.full_name,id:r.id})));if(data.repositories.length<100)break}}if((installations.installations??[]).length<100)break}return json({repositories:[...new Map(repos.map(r=>[r.id,r])).values()]})
  }
  if(url.pathname==='/api/repository'&&request.method==='POST'){
   const data=await body(request,1000);if(typeof data.repository!=='string'||!/^[-\w.]+\/[-\w.]+$/.test(data.repository))fail(400,'仓库名无效');const repo=await github(s.token,'/repos/'+data.repository);if(!ownPrivateRepo(repo,s.user_id))fail(403,'请选择本人拥有、可写的私有仓库');
   const branch=await github(s.token,`/repos/${repo.full_name}/branches/${encodeURIComponent(repo.default_branch)}`,'GET',undefined,true);if(!branch)fail(409,'请先在 GitHub 仓库添加 README，初始化默认分支');await env.DB.prepare('UPDATE accounts SET repository=?,last_sync_at=NULL WHERE user_id=?').bind(repo.full_name,s.user_id).run();return json({repository:repo.full_name})
  }
  if(url.pathname==='/api/state'&&request.method==='GET'){const repo=await accountRepo(env,s);return json(await readRemote(s,repo))}
  if(url.pathname==='/api/sync'&&request.method==='POST'){
   await limit(env,'sync:'+s.user_id,20,3600);const data=await body(request);try{validateState(data.state)}catch{fail(400,'学习记录格式不正确或超过 750 KB，请导出备份归档')}
   const repo=await accountRepo(env,s);const remote=await readRemote(s,repo);if(data.expected_sha!==remote.sha)fail(409,'远程版本已变化，请先拉取并合并，未覆盖远程记录');
   try{ensureNoLoss(remote.state,data.state)}catch{fail(409,'尚未合并全部远程记录；先拉取，再同步')}
   if(remote.state&&JSON.stringify(remote.state)===JSON.stringify(data.state))return json({...remote,unchanged:true});
   if(!remote.pr_url){
    const branch=await github(s.token,`/repos/${repo.full_name}/git/ref/heads/${BRANCH}`,'GET',undefined,true);
    if(branch){const previous=await github(s.token,`/repos/${repo.full_name}/pulls?state=closed&head=${encodeURIComponent(repo.owner.login+':'+BRANCH)}&per_page=1`);if(!previous[0]?.merged_at)fail(409,'此前同步分支仍在或 PR 已被关闭；请在 GitHub 审核处理后重试');const base=await github(s.token,`/repos/${repo.full_name}/git/ref/heads/${encodeURIComponent(repo.default_branch)}`);await github(s.token,`/repos/${repo.full_name}/git/refs/heads/${BRANCH}`,'PATCH',{sha:base.object.sha,force:false});}
    else{const base=await github(s.token,`/repos/${repo.full_name}/git/ref/heads/${encodeURIComponent(repo.default_branch)}`);await github(s.token,`/repos/${repo.full_name}/git/refs`,'POST',{ref:'refs/heads/'+BRANCH,sha:base.object.sha});}
   }
   const content=b64(new TextEncoder().encode(JSON.stringify(data.state)+'\n'));
   const saved=await github(s.token,`/repos/${repo.full_name}/contents/${FILE}`,'PUT',{message:'Save personal learning records',content,branch:BRANCH,...(remote.sha?{sha:remote.sha}:{})});
   let pr_url=remote.pr_url;if(!pr_url){const pr=await github(s.token,`/repos/${repo.full_name}/pulls`,'POST',{title:'保存我的供应链学习记录',head:BRANCH,base:repo.default_branch,body:'此 PR 仅更新 learning/state.json 中的个人学习设置、进度、笔记与题目版本快照。\n\n记录仓库为本人私有仓库；不修改公开课程或执行记录中的文字。请自行审核并合并。'});pr_url=pr.html_url}
   await env.DB.prepare('UPDATE accounts SET last_sync_at=? WHERE user_id=?').bind(new Date().toISOString(),s.user_id).run();return json({sha:saved.content.sha,pr_url,saved:true});
  }
  fail(404,'没有此接口');
 }catch(e){return json({error:e instanceof Fault?e.message:'服务暂时无法完成请求，请重试；现有记录未清空',code:e instanceof Fault&&e.status<500?'request_rejected':phase},e instanceof Fault?e.status:500)}
},async scheduled(_event,env){for(const table of ['oauth_states','handoffs','sessions','rate_limits'])await env.DB.prepare(`DELETE FROM ${table} WHERE expires < ?`).bind(now()).run()}};
