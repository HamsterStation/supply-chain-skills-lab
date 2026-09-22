import {test,expect} from '@playwright/test';
test.use({baseURL:'http://127.0.0.1:5188'});
test('MOCK one-time login callback opens the learning home and removes its ticket',async({page})=>{
 let exchanges=0;
 await page.addInitScript(()=>sessionStorage.setItem('scsl:signin-verifier','test-verifier'));
 await page.route('https://auth.example.test/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path==='/api/exchange'){
   exchanges++;expect(route.request().postDataJSON()).toEqual({ticket:'test-one-use-ticket',verifier:'test-verifier'});
   await route.fulfill({json:{session:'z'.repeat(43)}});
  }else await route.fulfill({json:{user:{id:1003,login:'callback-test'},repository:null,last_sync_at:null,install_url:'https://github.com/apps/test/installations/new'}});
 });
 await page.goto('/#auth/test-one-use-ticket');
 await expect(page.getByRole('button',{name:'退出 callback-test'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'没有找到这项内容'})).toHaveCount(0);
 await expect(page).toHaveURL(/#home$/);expect(exchanges).toBe(1);
});
test('MOCK GitHub sign-in isolates Alice/Bob, logout hides records, remote sync is explicit',async({page})=>{
 let who={id:1001,login:'alice-test'};let syncCalls=0;let writes:unknown[]=[];
 await page.addInitScript(()=>sessionStorage.setItem('scsl:application-session','x'.repeat(43)));
 await page.route('https://auth.example.test/api/**',async route=>{const path=new URL(route.request().url()).pathname;const payload=path==='/api/me'?{user:who,repository:who.login+'/private-learning',last_sync_at:null,install_url:'https://github.com/apps/test/installations/new'}:path==='/api/repos'?{repositories:[{full_name:who.login+'/private-learning',id:1}]}:path==='/api/state'?{state:null,sha:null,pr_url:null}:path==='/api/sync'?(syncCalls++,writes.push(route.request().postDataJSON()),{sha:'new-sha',pr_url:'https://github.com/'+who.login+'/private-learning/pull/1'}):{ok:true};await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(payload)})});
 await page.goto('/#lesson/lesson-flow');await expect(page.getByRole('button',{name:'退出 alice-test'})).toBeVisible();await page.getByLabel('我的笔记',{exact:true}).fill('Alice private note');await page.getByRole('button',{name:'保存笔记',exact:true}).click();await expect(page.getByText('已保存在本机浏览器')).toBeVisible();expect(syncCalls).toBe(0);
 await page.getByRole('button',{name:'退出 alice-test'}).click();await expect(page.getByRole('button',{name:'使用 GitHub 登录'})).toBeVisible();await expect(page.getByText('Alice private note')).toHaveCount(0);
 who={id:1002,login:'bob-test'};await page.reload();await page.goto('/#lesson/lesson-flow');await expect(page.getByRole('button',{name:'退出 bob-test'})).toBeVisible();await expect(page.getByLabel('我的笔记',{exact:true})).toHaveValue('');
 who={id:1001,login:'alice-test'};await page.reload();await expect(page.getByLabel('我的笔记',{exact:true})).toHaveValue('Alice private note');
 await page.goto('/#space');await page.getByRole('button',{name:'拉取并合并记录'}).click();await expect(page.getByRole('button',{name:'保存到我的仓库 PR'})).toBeEnabled();await page.getByRole('button',{name:'保存到我的仓库 PR'}).click();await expect(page.getByRole('link',{name:'打开我的学习记录 PR'})).toBeVisible();expect(syncCalls).toBe(1);expect(JSON.stringify(writes)).toContain('Alice private note');
});
