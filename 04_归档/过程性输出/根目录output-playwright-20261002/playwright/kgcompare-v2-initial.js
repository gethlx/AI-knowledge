async page => {
 await page.setViewportSize({width:390,height:844});
 await page.goto('http://127.0.0.1:41838/route-a.html');
 await page.evaluate(()=>document.activeElement.blur());
 await page.screenshot({path:'03_交付物/图谱浏览器双路线对照-v2-20261002/route-a-mobile.png'});
 await page.goto('http://127.0.0.1:41838/index.html');
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:width===1440?1000:844});
  await page.screenshot({path:'03_交付物/图谱浏览器双路线对照-v2-20261002/comparison-'+width+'.png',fullPage:true});
 }
}