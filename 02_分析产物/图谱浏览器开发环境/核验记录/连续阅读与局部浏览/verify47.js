async (page) => {
 const checks=[],errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const check=(name,pass,detail)=>{checks.push({name,pass:!!pass,detail});if(!pass)throw Error(name+' '+JSON.stringify(detail));};
 const state=()=>page.evaluate(()=>atlasUI.getState());
 await page.setViewportSize({width:390,height:844});await page.goto('http://127.0.0.1:41839/atlas.html?view=explore#4-03');await page.reload();await page.waitForTimeout(900);
 check('页面身份与真实内容',await page.title()==='大语言模型 · 银河AI知识图册'&&await page.locator('#definition').textContent()!=='',await page.title());
 check('无错误遮罩或加载失败',await page.locator('vite-error-overlay').count()===0&&await page.locator('#graph-error').isHidden(),null);
 const geometry=await page.evaluate(()=>{const g=atlasUI.graph(),d=g.graphData(),f=g.d3Force('link').distance(),dist=d.links.map(e=>f(e)),length=d.links.map(e=>Math.hypot(e.source.x-e.target.x,e.source.y-e.target.y,e.source.z-e.target.z));return {nodes:d.nodes.length,edges:d.links.length,targetMin:Math.min(...dist),targetMax:Math.max(...dist),lengthMin:Math.min(...length),lengthMax:Math.max(...length),fixed:d.nodes.filter(n=>n.fx!==undefined||n.fy!==undefined||n.fz!==undefined).length};});
 check('真实子图与可变空间排布',geometry.nodes===42&&geometry.edges===266&&geometry.targetMax-geometry.targetMin>10&&geometry.lengthMax>geometry.lengthMin*2&&geometry.fixed===0,geometry);
 const initial=await state();check('默认局部视角显示直接邻居',!initial.overview&&initial.labelBoxes.filter(b=>initial.preferredLabels.includes(b.id)).length>=3,initial);
 await page.screenshot({path:'output/playwright/atlas47/local-390.png'});
 const baseline=await page.evaluate(()=>{const g=atlasUI.graph();return {distance:g.camera().position.distanceTo(g.controls().target),boxes:atlasUI.getState().labelBoxes,attenuation:g.graphData().nodes.every(n=>n.__threeObj.children.find(c=>c.isSprite).material.sizeAttenuation===false)};});
 await page.locator('[data-action="zoom-in"]').click();await page.locator('[data-action="zoom-in"]').click();await page.waitForTimeout(100);
 const zoom=await page.evaluate(()=>{const g=atlasUI.graph();return {distance:g.camera().position.distanceTo(g.controls().target),boxes:atlasUI.getState().labelBoxes};});
 const b0=baseline.boxes.find(b=>b.id==='4-03'),b1=zoom.boxes.find(b=>b.id==='4-03');
 check('放大空间且标签字号不变',baseline.attenuation&&zoom.distance<baseline.distance*.65&&b0.height===b1?.height&&b0.width===b1?.width,{before:baseline.distance,after:zoom.distance,labelBefore:b0,labelAfter:b1});
 await page.screenshot({path:'output/playwright/atlas47/zoom-in.png'});
 const canvas=await page.locator('#webgl canvas').boundingBox();await page.mouse.move(canvas.x+20,canvas.y+80);await page.mouse.wheel(0,360);await page.waitForTimeout(160);check('滚轮缩放可用',(await page.evaluate(()=>{const g=atlasUI.graph();return g.camera().position.distanceTo(g.controls().target)}))>zoom.distance,null);
 await page.locator('[data-action="overview"]').click();await page.waitForTimeout(120);check('全景单独可用、字号仍可读',(await state()).overview&&(await state()).labelBoxes.find(b=>b.id==='4-03')?.height===b0.height,await state());await page.screenshot({path:'output/playwright/atlas47/overview.png'});
 await page.locator('[data-action="locate"]').click();await page.waitForTimeout(550);
 const click=await page.evaluate(()=>{const s=atlasUI.getState(),r=document.querySelector('#graph-surface').getBoundingClientRect();const b=s.labelBoxes.find(b=>b.id==='4-01')??s.labelBoxes.find(b=>b.id!==s.selected&&s.preferredLabels.includes(b.id));return {id:b.id,x:r.x+(b.left+b.right)/2,y:r.y+(b.top+b.bottom)/2};});
 await page.mouse.click(click.x,click.y);await page.waitForTimeout(600);
 const centered=await page.evaluate(()=>{const g=atlasUI.graph(),s=atlasUI.getState(),n=g.graphData().nodes.find(n=>n.id===s.selected),p=g.graph2ScreenCoords(n.x,n.y,n.z),adj=new Set(Object.values(atlasUI.getNeighbors(s.selected)).flat().map(n=>n.id));return {selected:s.selected,target:g.controls().target,node:{x:n.x,y:n.y,z:n.z},screen:p,size:{w:g.width(),h:g.height()},labels:s.labelBoxes.map(b=>b.id),direct:s.labelBoxes.filter(b=>adj.has(b.id)).length,preferred:s.preferredLabels};});
 check('真实名称点击后节点居中并显示直接邻居',centered.selected===click.id&&Math.abs(centered.screen.x-centered.size.w/2)<2&&Math.abs(centered.screen.y-centered.size.h/2)<2&&centered.direct>=3,centered);
 await page.screenshot({path:'output/playwright/atlas47/click-centered.png'});
 const dragBefore=(await state()).selected;await page.mouse.move(canvas.x+12,canvas.y+85);await page.mouse.down();await page.mouse.move(canvas.x+75,canvas.y+110,{steps:6});await page.mouse.up();await page.waitForTimeout(220);check('旋转不误选节点',(await state()).selected===dragBefore,null);
 // Inline reading must leave the current document and graph in place.
 const explanation=page.locator('#explanation');if(await explanation.getAttribute('open')!==null)await explanation.locator('summary').click();
 await explanation.locator('summary').scrollIntoViewIfNeeded();await page.waitForTimeout(80);
 const before=await page.evaluate(()=>({scroll:scrollY,height:document.documentElement.scrollHeight,graph:document.querySelector('#expanded-graph').getBoundingClientRect().top,title:document.querySelector('#concept-title').getBoundingClientRect().top,mode:atlasUI.getState().mode}));
 await explanation.locator('summary').click();await page.waitForTimeout(100);
 const after=await page.evaluate(()=>({scroll:scrollY,height:document.documentElement.scrollHeight,graph:document.querySelector('#expanded-graph').getBoundingClientRect().top,title:document.querySelector('#concept-title').getBoundingClientRect().top,mode:atlasUI.getState().mode}));
 check('正文当前位置展开，仅页面向下增长',after.height>before.height&&Math.abs(after.scroll-before.scroll)<=2&&Math.abs(after.title-before.title)<=2&&after.mode===before.mode,{before,after});
 const copy=await page.evaluate(()=>{const c=atlasUI.readCard(atlasUI.getState().selected),f=c.fields,keys=['教学类比','典型案例','常见误解','反例','安全与伦理边界'];return {titles:[...document.querySelectorAll('#detail>.content-section h2')].map(n=>n.textContent),definition:document.querySelector('#definition').textContent===f['精确定义'],all:keys.filter(k=>f[k]&&f[k]!=='—').every(k=>[...document.querySelectorAll('#explanation-copy p')].some(p=>p.dataset.field===k&&p.lastElementChild.textContent===f[k])),sources:!!document.querySelector('#sources'),range:!!document.querySelector('#source-copy')};});
 check('只保留定义与解释说明，实际字段完整合并',copy.titles.join('/')==='定义/解释说明'&&copy.definition&&copy.all&&!copy.sources&&!copy.range,copy);
 await page.locator('#neighbors>summary').click();const neighbor=page.locator('.neighbor-card').first();await neighbor.locator('summary').scrollIntoViewIfNeeded();
 const nb=await page.evaluate(()=>({scroll:scrollY,height:document.documentElement.scrollHeight,selected:atlasUI.getState().selected,url:location.href}));
 await neighbor.locator('summary').click();await page.waitForTimeout(100);
 const na=await page.evaluate(()=>({scroll:scrollY,height:document.documentElement.scrollHeight,selected:atlasUI.getState().selected,url:location.href,text:document.querySelector('.neighbor-card[open] .neighbor-reading').textContent}));
 check('相邻概念原地伸展且不跳页（缺项不造解释）',na.height>nb.height&&Math.abs(na.scroll-nb.scroll)<=2&&na.selected===nb.selected&&na.url===nb.url&&na.text.includes('定义'),{before:nb,after:na});
 await page.screenshot({path:'output/playwright/atlas47/neighbor-inline.png'});
 for(const width of [320,430,960]){await page.setViewportSize({width,height:844});await page.goto('http://127.0.0.1:41839/atlas.html?view=explore#4-01');await page.reload();await page.waitForTimeout(750);const s=await state();const direct=Object.values(await page.evaluate(()=>atlasUI.getNeighbors('4-01'))).flat().map(n=>n.id);check(width+'px定位与可读邻居',s.selected==='4-01'&&s.labelBoxes.filter(b=>direct.includes(b.id)).length>=3&&await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),{selected:s.selected,labels:s.labelBoxes.map(b=>b.id),neighbors:s.visible.length});await page.screenshot({path:'output/playwright/atlas47/local-'+width+'.png'});}
 await page.setViewportSize({width:390,height:844});await page.goto('http://127.0.0.1:41839/atlas.html#4-01');await page.waitForTimeout(650);await page.screenshot({path:'output/playwright/atlas47/reading-390.png'});check('首屏正文与缩略入口',await page.locator('.graph-thumbnail').isVisible()&&await page.locator('#explanation').getAttribute('open')!==null,null);
 check('无未捕获异常',errors.length===0,errors);
 return {checks,errors};
}
