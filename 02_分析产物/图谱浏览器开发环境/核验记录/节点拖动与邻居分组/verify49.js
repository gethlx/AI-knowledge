async (page)=>{
 const checks=[],errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
 const check=(name,pass,detail)=>{checks.push({name,pass:!!pass,detail});if(!pass)throw Error(name+': '+JSON.stringify(detail));};
 const dist=(a,b)=>Math.hypot(...a.map((n,i)=>n-b[i]));
 const state=()=>page.evaluate(()=>{const s=atlasUI.getState(),g=atlasUI.graph(),r=document.querySelector('#graph-surface').getBoundingClientRect(),n=g.graphData().nodes.find(n=>n.id===s.selected);return {selected:s.selected,boxes:s.labelBoxes,rect:r.toJSON(),camera:g.camera().position.toArray(),target:g.controls().target.toArray(),point:g.graph2ScreenCoords(n.x,n.y,n.z),distance:g.camera().position.distanceTo(g.controls().target),nodes:g.graphData().nodes.map(n=>({id:n.id,p:[n.x,n.y,n.z],fixed:[n.fx,n.fy,n.fz]})),links:g.graphData().links.map(e=>({a:e.source.id,b:e.target.id,p:Array.from(e.__lineObj.geometry.attributes.position.array)}))}});
 await page.mouse.up();await page.setViewportSize({width:390,height:844});await page.goto('http://127.0.0.1:41839/atlas.html?view=explore#5-21');await page.reload();await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(2100);
 check('页面身份、正文、错误遮罩',await page.title()==='算力 · 银河AI知识图册'&&await page.locator('#definition').textContent()!==''&&await page.locator('vite-error-overlay').count()===0,null);
 const nav=await page.evaluate(()=>({open:document.querySelector('#neighbors').open,groups:[...document.querySelectorAll('.neighbor-group')].map(d=>({key:d.dataset.group,open:d.open,count:d.querySelectorAll('.neighbor-card').length})),count:document.querySelectorAll('.neighbor-card').length,expected:+document.querySelector('#neighbor-count').textContent}));
 check('相邻导航默认展开，基础后续直接展示、其他关联收起且完整',nav.open&&nav.groups.find(g=>g.key==='after')?.open&&nav.groups.find(g=>g.key==='related')?.open===false&&nav.count===nav.expected,nav);
 const before=await state(),label=before.boxes.find(b=>b.id===before.selected),x=before.rect.x+(label.left+label.right)/2,y=before.rect.y+(label.top+label.bottom)/2;
 await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+65,y+35,{steps:12});await page.waitForTimeout(280);const held=await state();
 const delta=held.nodes.map(n=>({id:n.id,distance:dist(n.p,before.nodes.find(m=>m.id===n.id).p)}));
 check('真实鼠标拖名称：节点变形、镜头不平移、不误选',delta.find(d=>d.id===before.selected).distance>30&&dist(before.camera,held.camera)<.01&&dist(before.target,held.target)<.01&&held.selected===before.selected,delta);
 check('拖动期间其他节点分别响应，连线几何更新',delta.filter(d=>d.id!==before.selected&&d.distance>1).length>=3&&held.links.some((e,i)=>dist(e.p,before.links[i].p)>2),{reacted:delta.filter(d=>d.id!==before.selected&&d.distance>1).length});
 await page.screenshot({path:'output/playwright/atlas49/drag-held-390.png'});await page.mouse.up();await page.waitForTimeout(1600);const released=await state();
 check('松手解除节点固定，相机不自动追随',released.nodes.every(n=>n.fixed.every(f=>f==null))&&dist(before.camera,released.camera)<.01&&dist(before.target,released.target)<.01,null);
 // Blank area has no label or node at the top left; dragging it rotates the camera.
 const rect=released.rect;await page.mouse.move(rect.x+14,rect.y+15);await page.mouse.down();await page.mouse.move(rect.x+65,rect.y+35,{steps:10});await page.mouse.up();await page.waitForTimeout(180);const rotated=await state();
 check('左键空白拖动旋转，图中节点坐标保持',dist(rotated.camera,released.camera)>10&&dist(rotated.target,released.target)<.01&&rotated.nodes.every(n=>dist(n.p,released.nodes.find(m=>m.id===n.id).p)<.01)&&rotated.selected===released.selected,{camera:dist(rotated.camera,released.camera),target:dist(rotated.target,released.target),nodes:Math.max(...rotated.nodes.map(n=>dist(n.p,released.nodes.find(m=>m.id===n.id).p))),selected:rotated.selected});
 await page.mouse.move(rect.x+14,rect.y+15);await page.mouse.down({button:'right'});await page.mouse.move(rect.x+55,rect.y+45,{steps:8});await page.mouse.up({button:'right'});await page.waitForTimeout(160);const panned=await state();
 check('右键空白拖动平移且不拉回中心',dist(panned.target,rotated.target)>5&&panned.selected===rotated.selected,null);
 await page.mouse.move(rect.x+rect.width*.8,rect.y+rect.height*.55);await page.mouse.wheel(0,-220);await page.waitForTimeout(170);const zoomed=await state();
 const common=zoomed.boxes.find(b=>panned.boxes.some(a=>a.id===b.id)),old=panned.boxes.find(b=>b.id===common?.id);
 check('滚轮自由缩放，标签保持屏幕字号',zoomed.distance<panned.distance&&common&&Math.abs(common.height-old.height)<.01,null);
 await page.locator('[data-action="locate"]').click();await page.waitForTimeout(530);const located=await state();
 check('主动定位仅一次居中',Math.abs(located.point.x-located.rect.width/2)<2&&Math.abs(located.point.y-located.rect.height/2)<2,null);
 const lb=located.boxes.find(b=>b.id!==located.selected),cx=located.rect.x+(lb.left+lb.right)/2,cy=located.rect.y+(lb.top+lb.bottom)/2;
 await page.mouse.click(cx,cy);await page.waitForTimeout(560);const clicked=await state();
 check('无拖动点击名称：切换正文并单次定位',clicked.selected===lb.id&&Math.abs(clicked.point.x-clicked.rect.width/2)<2&&Math.abs(clicked.point.y-clicked.rect.height/2)<2,{selected:clicked.selected});
 // Actual Chromium touch events drag the selected label without moving the camera.
 const client=await page.context().newCDPSession(page),box=clicked.boxes.find(b=>b.id===clicked.selected),tx=clicked.rect.x+(box.left+box.right)/2,ty=clicked.rect.y+(box.top+box.bottom)/2;
 await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{id:0,x:tx,y:ty}]});
 for(let i=1;i<=8;i++){await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{id:0,x:tx+i*6,y:ty+i*3}]});await page.waitForTimeout(20)}
 const touchHeld=await state();await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(1500);
 check('真实单指触摸拖名称：节点变形、镜头不动',dist(touchHeld.nodes.find(n=>n.id===clicked.selected).p,clicked.nodes.find(n=>n.id===clicked.selected).p)>20&&dist(touchHeld.camera,clicked.camera)<.01&&touchHeld.selected===clicked.selected,null);
 const touchBefore=await state(),br=touchBefore.rect;await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{id:0,x:br.x+15,y:br.y+15}]});await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{id:0,x:br.x+65,y:br.y+42}]});await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(180);const touchRotate=await state();
 check('单指空白旋转',dist(touchBefore.camera,touchRotate.camera)>10&&touchBefore.selected===touchRotate.selected,null);
 const p0={id:0,x:br.x+110,y:br.y+br.height-30},p1={id:1,x:br.x+180,y:br.y+br.height-30};
 await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[p0,p1]});await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{...p0,x:p0.x-25},{...p1,x:p1.x+25}]});await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(160);const pinch=await state();await client.detach();check('双指缩放且不误选',pinch.distance<touchRotate.distance*.85&&pinch.selected===touchRotate.selected,{before:touchRotate.distance,after:pinch.distance});
 // Return to the user's original card to verify disclosure and inline reading.
 await page.goto('http://127.0.0.1:41839/atlas.html?view=explore#5-21');await page.waitForTimeout(2000);await page.locator('[data-group="after"]>summary').scrollIntoViewIfNeeded();
 const afterCard=page.locator('[data-group="after"] .neighbor-card').first();check('基础后续名称直接可见、内容按需展开',await afterCard.locator('summary').isVisible()&&await afterCard.getAttribute('open')===null,null);
 await page.screenshot({path:'output/playwright/atlas49/neighbors-default-390.png'});await afterCard.locator('summary').click();await page.waitForTimeout(80);
 check('相邻定义原地展开，主概念与URL保持',await afterCard.locator('.neighbor-reading p').first().isVisible()&&(await state()).selected==='5-21'&&page.url().endsWith('#5-21'),null);
 const related=page.locator('[data-group="related"]');await related.locator(':scope>summary').click();check('其他关联可展开完整清单',await related.locator('.neighbor-card').count()===11&&await related.locator('.neighbor-card').first().isVisible(),null);
 await related.locator(':scope>summary').click();
 for(const width of [320,430,980]){await page.setViewportSize({width,height:844});await page.locator('#neighbors>summary').scrollIntoViewIfNeeded();check(width+'px无横向溢出',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),null);await page.screenshot({path:'output/playwright/atlas49/navigation-'+width+'.png'});}
 await page.mouse.up();await page.setViewportSize({width:390,height:844});await page.goto('http://127.0.0.1:41839/atlas.html?view=explore#4-03');await page.reload();await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(2000);
 const grouped=await page.evaluate(()=>Object.fromEntries([...document.querySelectorAll('.neighbor-group')].map(d=>[d.dataset.group,d.open])));check('前置与以它为基础默认展开，其他关联默认收起',grouped.before&&grouped.after&&grouped.related===false,grouped);
 await page.screenshot({path:'output/playwright/atlas49/graph-390.png'});
 check('无应用控制台错误或未捕获异常',errors.length===0&&await page.locator('vite-error-overlay').count()===0,errors);
 return {checks,errors,environment:{url:page.url(),viewports:[320,390,430,980],browser:'Chromium Playwright CLI; Browser plugin not available'},drag:{before,held,released}};
}
