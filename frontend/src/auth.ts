export type Identity={user:{id:number;login:string};repository:string|null;last_sync_at:string|null;install_url:string};
let root=(import.meta.env.VITE_AUTH_URL as string|undefined)?.replace(/\/$/,'')??'';
export const authConfigured=()=>!!root;
export const localMode=()=>!root&&import.meta.env.DEV;
const sessionKey='scsl:application-session';
const verifierKey='scsl:signin-verifier';
let token=sessionStorage.getItem(sessionKey)??'';
export async function api(path:string,body?:unknown){if(!root)throw Error('GitHub 登录服务尚未配置');const r=await fetch(root+'/api'+path,{method:body===undefined?'GET':'POST',headers:{...(token?{Authorization:'Bearer '+token}:{}),...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store',signal:AbortSignal.timeout(25000)});const data=await r.json();if(!r.ok){if(r.status===401){token='';sessionStorage.removeItem(sessionKey);window.dispatchEvent(new Event('scsl-session-expired'))}throw Error(data.error??'同步失败，当前本机记录仍保留')}return data;}
export async function beginLogin(){if(!root)return;const v=crypto.getRandomValues(new Uint8Array(32));const verifier=btoa(String.fromCharCode(...v)).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');sessionStorage.setItem(verifierKey,verifier);const challenge=btoa(String.fromCharCode(...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier))))).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');location.href=root+'/auth/start?challenge='+challenge;}
export async function authenticate():Promise<Identity|null>{if(!root)return null;if(location.hash.startsWith('#auth/')){const ticket=location.hash.slice(6);history.replaceState(null,'',location.pathname+location.search+'#home');const verifier=sessionStorage.getItem(verifierKey);sessionStorage.removeItem(verifierKey);if(!verifier)throw Error('登录请求已失效，请重新登录');const result=await api('/exchange',{ticket,verifier});token=result.session;sessionStorage.setItem(sessionKey,token)}if(!token)return null;return api('/me');}
export async function logout(){try{await api('/logout',{})}finally{token='';sessionStorage.removeItem(sessionKey)}}
