async page => {
 await page.goto('http://127.0.0.1:41838/index.html');
 const resources=await page.evaluate(async()=>await Promise.all([...new Set([...document.querySelectorAll('a')].map(a=>a.href))].map(async url=>({url,status:(await fetch(url)).status}))));
 const views=[];
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:width===1440?1000:844});
  await page.locator('img').first().waitFor();
  views.push(await page.evaluate(()=>({width:innerWidth,noOverflow:document.documentElement.scrollWidth<=innerWidth,images:[...document.images].every(i=>i.complete&&i.naturalWidth>0)})));
  await page.screenshot({path:'03_交付物/图谱浏览器双路线对照-v2-20261002/comparison-'+width+'.png',fullPage:true});
 }
 await page.evaluate(r=>window.entryReport=r,{resources,views});
}