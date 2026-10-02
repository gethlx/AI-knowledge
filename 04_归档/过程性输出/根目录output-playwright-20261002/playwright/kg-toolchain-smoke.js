async page=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.reload();
 await page.waitForFunction(()=>window.toolchainSmoke?.ready);
 await page.setViewportSize({width:1280,height:900});
 await page.evaluate(()=>document.fonts.ready);
 const initial=await page.evaluate(()=>({nodes:smokeGraph.graphData().nodes.length,links:smokeGraph.graphData().links.length,renderCalls:smokeGraph.renderer().info.render.calls,webgl:smokeGraph.renderer().domElement instanceof HTMLCanvasElement,iconFont:document.fonts.check('24px Phosphor'),iconGlyph:getComputedStyle(document.querySelector('.ph-pause'),'::before').content,noOverflow:document.documentElement.scrollWidth<=innerWidth}));
 await page.getByRole('button',{name:'暂停布局'}).click();const paused=await page.evaluate(()=>toolchainSmoke.paused);
 await page.getByRole('button',{name:'继续布局'}).click();const resumed=await page.evaluate(()=>!toolchainSmoke.paused);
 await page.getByRole('button',{name:'定位节点'}).click();const focused=await page.evaluate(()=>toolchainSmoke.selected==='a');
 const before=await page.evaluate(()=>smokeGraph.camera().quaternion.toArray());
 const box=await page.locator('#graph').boundingBox();
 await page.mouse.move(box.x+80,box.y+65);await page.mouse.down();await page.mouse.move(box.x+180,box.y+105,{steps:8});await page.mouse.up();
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 const orbit=await page.evaluate(q=>smokeGraph.camera().quaternion.toArray().some((x,i)=>Math.abs(x-q[i])>0.0001),before);
 await page.screenshot({path:'output/playwright/kg-toolchain-desktop.png'});
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 const mobile=await page.evaluate(()=>({noOverflow:document.documentElement.scrollWidth<=innerWidth,canvasWidth:smokeGraph.renderer().domElement.getBoundingClientRect().width}));
 await page.screenshot({path:'output/playwright/kg-toolchain-mobile.png'});
 await page.evaluate(r=>window.smokeReport=r,{initial,paused,resumed,focused,orbit,mobile,errors});
}