import {chromium} from '/Users/larry/.workbuddy/binaries/node/workspace/node_modules/playwright/index.mjs';import fs from 'node:fs';
const url=process.argv[2]??'http://127.0.0.1:41843/AI-knowledge/',prefix=process.argv[3]??'/tmp/atlas-responsive';
const browser=await chromium.launch({executablePath:'/Users/larry/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell'});const page=await(await browser.newContext({viewport:{width:390,height:844}})).newPage();const errors=[],resources=[],checks=[];page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)resources.push(r.url()+':'+r.status())});
await page.goto(url+'?view=explore#4-03',{waitUntil:'networkidle'});await page.waitForTimeout(1800);
for(const width of [320,390,640,768,1024,1440,1920,390]){
 await page.setViewportSize({width,height:844});await page.waitForTimeout(180);
 const view=await page.evaluate(()=>{const s=document.querySelector('#graph-surface').getBoundingClientRect(),a=document.querySelector('#atlas').getBoundingClientRect();return {viewport:innerWidth,atlas:a.width,surface:s.width,canvas:document.querySelector('canvas').getBoundingClientRect().width,graph:atlasUI.graph().width(),selected:atlasUI.getState().selected,overflow:document.documentElement.scrollWidth>innerWidth,nodes:atlasUI.graph().graphData().nodes.length,edges:atlasUI.graph().graphData().links.length}});
 checks.push({name:width+'px shell/canvas/data',pass:!view.overflow&&Math.abs(view.atlas-width)<2&&Math.abs(view.surface-width)<2&&Math.abs(view.canvas-view.surface)<2&&Math.abs(view.graph-view.surface)<2&&view.selected==='4-03'&&view.nodes===197&&view.edges===1562,detail:view});
 if([390,1440].includes(width))await page.screenshot({path:prefix+'-explore-'+width+'.png'});
}
for(const width of [320,390,768,1440]){
 await page.setViewportSize({width,height:844});await page.click('[data-action="directory"]');await page.waitForTimeout(100);
 const layout=await page.evaluate(()=>({width:innerWidth,controls:document.querySelector('.search-controls').getBoundingClientRect().width,overflow:document.querySelector('#browser-panel').scrollWidth>innerWidth,results:document.querySelectorAll('.concept-result').length}));
 checks.push({name:width+'px directory',pass:!layout.overflow&&layout.controls>width*.8&&layout.results===197,detail:layout});
 await page.keyboard.press('Escape');
}
await page.setViewportSize({width:1440,height:900});await page.click('[data-action="mode"]');await page.waitForTimeout(200);await page.screenshot({path:prefix+'-reading-1440.png'});const thumb=await page.evaluate(()=>{const s=document.querySelector('#graph-surface').getBoundingClientRect(),c=document.querySelector('canvas').getBoundingClientRect();return {surface:s.width,canvas:c.width,detail:document.querySelector('#detail').getBoundingClientRect().width,viewport:innerWidth}});checks.push({name:'wide reading thumbnail resizes',pass:Math.abs(thumb.surface-thumb.canvas)<2&&thumb.detail>480,detail:thumb});
await page.click('[data-action="search"]');await page.fill('#search-input','监督学习');await page.locator('.concept-result').first().click();await page.waitForTimeout(550);const next=await page.locator('#concept-title').innerText();await page.goBack();await page.waitForTimeout(550);checks.push({name:'search selection and browser back',pass:next.includes('监督学习')&&await page.evaluate(()=>atlasUI.getState().selected==='4-03')});
checks.push({name:'page and resource errors',pass:!errors.length&&!resources.length,errors,resources});
await browser.close();const result={url,checks,passed:checks.filter(x=>x.pass).length,total:checks.length};fs.writeFileSync(prefix+'.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));if(checks.some(x=>!x.pass))process.exitCode=1;
