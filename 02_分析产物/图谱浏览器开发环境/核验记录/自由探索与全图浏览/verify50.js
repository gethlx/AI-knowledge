async(page)=>{
 const checks=[],errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
 const check=(name,pass,detail)=>{checks.push({name,pass:!!pass,detail});if(!pass)throw Error(name+JSON.stringify(detail));};
 const dist=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
 const read=()=>page.evaluate(()=>{const g=atlasUI.graph(),s=atlasUI.getState(),r=document.querySelector('#graph-surface').getBoundingClientRect(),direct=Object.values(atlasUI.getNeighbors(s.selected)).flat().map(n=>n.id);return {selected:s.selected,scope:s.scope,rect:r.toJSON(),boxes:s.labelBoxes,nonadj:s.labelBoxes.filter(b=>b.id!==s.selected&&!direct.includes(b.id)).map(b=>b.id),camera:g.camera().position.toArray(),target:g.controls().target.toArray(),distance:g.camera().position.distanceTo(g.controls().target),nodes:g.graphData().nodes.map(n=>({id:n.id,p:[n.x,n.y,n.z],point:g.graph2ScreenCoords(n.x,n.y,n.z)})),links:g.graphData().links.map(e=>({source:e.source.id,target:e.target.id,kind:e.relation_type,color:g.linkColor()(e)}))}});
 const blank=s=>{let best;for(const x of [15,30,s.rect.width-30,s.rect.width-15])for(const y of [15,35,s.rect.height-35,s.rect.height-15]){if(s.boxes.some(b=>x>=b.left&&x<=b.right&&y>=b.top&&y<=b.bottom))continue;const nearest=Math.min(...s.nodes.map(n=>Math.hypot(n.point.x-x,n.point.y-y)));if(!best||nearest>best.score)best={x:s.rect.x+x,y:s.rect.y+y,score:nearest};}return best;};
 await page.mouse.up();await page.setViewportSize({width:390,height:844});await page.goto('http://127.0.0.1:41839/atlas.html?view=explore#3-04');await page.reload();await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(2100);const entry=await read();
 check('完整197节点/1562边，全景不再裁一跳',entry.scope==='full'&&entry.nodes.length===197&&entry.links.length===1562,null);
 check('真实边类型与有效方向保留',entry.links.filter(e=>e.kind==='prerequisite').length===78&&entry.links.filter(e=>e.kind==='related').length===1484,null);
 check('非相邻连线不再18%透明',entry.links.filter(e=>e.source!==entry.selected&&e.target!==entry.selected).every(e=>e.color==='rgba(73,98,80,0.80)'),null);
 check('初始画面也可显示非直接邻居',entry.nonadj.length>0,entry.nonadj);
 // Find a remote visible name outside the original one-hop graph and drag it physically.
 const remote=entry.boxes.find(b=>entry.nonadj.includes(b.id)),rx=entry.rect.x+(remote.left+remote.right)/2,ry=entry.rect.y+(remote.top+remote.bottom)/2;
 await page.mouse.move(rx,ry);await page.mouse.down();await page.mouse.move(rx+35,ry+26,{steps:8});await page.waitForTimeout(250);const held=await read();
 check('非直接邻居名称可真实拖动，阅读概念不变',dist(held.nodes.find(n=>n.id===remote.id).p,entry.nodes.find(n=>n.id===remote.id).p)>10&&held.selected===entry.selected&&dist(entry.camera,held.camera)<.01,{id:remote.id});
 check('移动过程中非邻居标签仍可见',held.nonadj.length>0,held.nonadj);
 await page.screenshot({path:'output/playwright/atlas50/drag-nonadjacent-390.png'});await page.mouse.up();await page.waitForTimeout(1500);
 // Right pan towards an actually visible remote concept; then zoom under its new location.
 const panBefore=await read(),remotePoint=panBefore.nodes.find(n=>n.id===remote.id).point,start=blank(panBefore),dx=panBefore.rect.width/2-remotePoint.x,dy=panBefore.rect.height/2-remotePoint.y;
 await page.mouse.move(start.x,start.y);await page.mouse.down({button:'right'});await page.mouse.move(start.x+dx,start.y+dy,{steps:12});const panHeld=await read();await page.mouse.up({button:'right'});await page.waitForTimeout(180);const panAfter=await read();
 check('将非邻居移入眼前：视点平移，不绑定阅读节点',dist(panBefore.target,panAfter.target)>1&&panAfter.selected===entry.selected&&panAfter.nodes.every(n=>dist(n.p,panBefore.nodes.find(m=>m.id===n.id).p)<.01),{targetBefore:panBefore.target,targetAfter:panAfter.target});
 const selectedPoint=panAfter.nodes.find(n=>n.id===panAfter.selected).point;
 check('阅读节点不强制保留在视图中心',Math.hypot(selectedPoint.x-panAfter.rect.width/2,selectedPoint.y-panAfter.rect.height/2)>10,selectedPoint);
 check('平移中显示当前视野的非邻居',panHeld.nonadj.length>0,panHeld.nonadj);
 const rp=panAfter.nodes.find(n=>n.id===remote.id).point;await page.mouse.move(panAfter.rect.x+rp.x,panAfter.rect.y+rp.y);await page.mouse.wheel(0,-360);await page.waitForTimeout(220);const zoomed=await read();
 check('局部放大跟随当前区域，选择与完整节点集不变',zoomed.distance<panAfter.distance&&zoomed.selected===entry.selected&&zoomed.nodes.length===197,{before:panAfter.distance,after:zoomed.distance});
 check('平移和局部放大发现新名称',zoomed.boxes.some(b=>!entry.boxes.some(a=>a.id===b.id))&&zoomed.nonadj.length>0,{entry:entry.boxes.map(b=>b.id),zoomed:zoomed.boxes.map(b=>b.id),nonadj:zoomed.nonadj});
 const common=zoomed.boxes.find(b=>entry.boxes.some(a=>a.id===b.id));if(common){const old=entry.boxes.find(b=>b.id===common.id);check('局部放大时名称保持屏幕字号',Math.abs(common.height-old.height)<.01,null);}
 await page.screenshot({path:'output/playwright/atlas50/pan-zoom-discovery-390.png'});
 // Rotation refreshes the shown region too, without only six favored neighbor names.
 const orbitStart=blank(zoomed);await page.mouse.move(orbitStart.x,orbitStart.y);await page.mouse.down();await page.mouse.move(orbitStart.x+40,orbitStart.y+20,{steps:8});const rotatedHeld=await read();await page.mouse.up();await page.waitForTimeout(180);const rotated=await read();
 check('空白旋转及运动中的非邻居信息可发现',dist(zoomed.camera,rotated.camera)>1&&rotatedHeld.nonadj.length>0&&rotated.selected===entry.selected,null);
 await page.locator('[data-action="overview"]').click();await page.waitForTimeout(100);const overview=await read();check('全景包含完整节点和全部真实边',overview.nodes.length===197&&overview.links.length===1562,null);await page.screenshot({path:'output/playwright/atlas50/overview-390.png'});
 const pick=overview.boxes.find(b=>b.id!==overview.selected),px=overview.rect.x+(pick.left+pick.right)/2,py=overview.rect.y+(pick.top+pick.bottom)/2;
 await page.mouse.click(px,py);await page.waitForTimeout(540);const clicked=await read();check('点击发现的概念更新详情，不重新裁剪或重排全图',clicked.selected===pick.id&&clicked.nodes.length===197&&clicked.nodes.every(n=>dist(n.p,overview.nodes.find(m=>m.id===n.id).p)<.01),{pick:pick.id,selected:clicked.selected,maxDisplacement:Math.max(...clicked.nodes.map(n=>dist(n.p,overview.nodes.find(m=>m.id===n.id).p)))});
 const center=clicked.nodes.find(n=>n.id===clicked.selected).point;check('点击仅一次定位',Math.abs(center.x-clicked.rect.width/2)<2&&Math.abs(center.y-clicked.rect.height/2)<2,null);
 // Native Chromium touch drag on the current visible name.
 const client=await page.context().newCDPSession(page),tb=clicked.boxes.find(b=>b.id===clicked.selected),tx=clicked.rect.x+(tb.left+tb.right)/2,ty=clicked.rect.y+(tb.top+tb.bottom)/2;
 await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{id:0,x:tx,y:ty}]});for(let i=1;i<=6;i++){await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{id:0,x:tx+i*4,y:ty+i*3}]});await page.waitForTimeout(20)}const touchHeld=await read();await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(1450);check('单指拖动保持原生力学变形且镜头不移动',dist(touchHeld.nodes.find(n=>n.id===clicked.selected).p,clicked.nodes.find(n=>n.id===clicked.selected).p)>5&&dist(touchHeld.camera,clicked.camera)<.01,null);
 const pinBefore=await read(),pblank=blank(pinBefore),py0=Math.min(pinBefore.rect.y+pinBefore.rect.height-30,pblank.y),x0=pinBefore.rect.x+100,x1=pinBefore.rect.x+180;
 await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{id:0,x:x0,y:py0},{id:1,x:x1,y:py0}]});await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{id:0,x:x0-25,y:py0},{id:1,x:x1+25,y:py0}]});await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(180);const pinAfter=await read();await client.detach();check('双指局部缩放保持可用',pinAfter.distance<pinBefore.distance*.85&&pinAfter.selected===pinBefore.selected,null);
 const group=await page.evaluate(()=>({open:document.querySelector('#neighbors').open,groups:[...document.querySelectorAll('.neighbor-group')].map(d=>({key:d.dataset.group,open:d.open})),count:document.querySelectorAll('.neighbor-card').length,expected:+document.querySelector('#neighbor-count').textContent}));check('上一轮相邻默认分组与完整清单保持',group.open&&group.count===group.expected&&group.groups.every(g=>g.open===(g.key!=='related')),group);
 for(const width of [320,430,980]){await page.setViewportSize({width,height:844});await page.evaluate(()=>scrollTo(0,0));check(width+'px无横向溢出',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),null);await page.screenshot({path:'output/playwright/atlas50/graph-'+width+'.png'});}
 await page.setViewportSize({width:390,height:844});await page.goto('http://127.0.0.1:41839/atlas.html?view=explore#3-04');await page.reload();await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(2100);await page.screenshot({path:'output/playwright/atlas50/entry-390.png'});
 check('文字不受远处雾色淡化',await page.evaluate(()=>atlasUI.graph().graphData().nodes.every(n=>n.__threeObj.children.filter(c=>c.isSprite).every(c=>c.material.fog===false))),null);
 check('页面身份、正常内容、无错误遮罩或应用异常',await page.title()==='模型 · 银河AI知识图册'&&!!await page.locator('#definition').textContent()&&await page.locator('vite-error-overlay').count()===0&&errors.length===0,errors);
 return {checks,errors,environment:{url:page.url(),viewports:[320,390,430,980],browser:'Playwright Chromium'},evidence:{entry,remote:remote.id,held,panBefore,panAfter,zoomed,rotatedHeld,overview,clicked}};
}
