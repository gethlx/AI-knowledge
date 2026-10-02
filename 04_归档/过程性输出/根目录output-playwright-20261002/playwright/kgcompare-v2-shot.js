async page => {
 await page.setViewportSize({width:390,height:844});
 await page.goto('http://127.0.0.1:41838/index.html');
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 await page.screenshot({path:'03_交付物/图谱浏览器双路线对照-v2-20261002/comparison-390.png'});
}