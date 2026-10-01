async (page) => {
  const errors=[];page.on('pageerror', e=>errors.push(e.message));
  const pre=page.locator('#fPre'), rel=page.locator('#fRel'), axis=page.locator('#axisSel');
  await axis.selectOption('');await pre.check();await rel.check();
  const read=()=>page.evaluate(()=>({nodes:nodeG.children.length,edges:edgeG.children.length,arrows:[...edgeG.children].filter(x=>x.hasAttribute('marker-end')).length}));
  const all=await read();
  const arrows=await page.evaluate(()=>EDGES.flatMap((e,i)=>{
    if(e.relation_type!=='prerequisite')return [];
    const p=edgeG.children[i],end=p.getPointAtLength(p.getTotalLength()),center=pos(byId[e.effective_target]);
    return [{edge_id:e.edge_id,source:e.effective_source,target:e.effective_target,marker:p.getAttribute('marker-end'),target_center_distance:Math.hypot(end.x-center.x,end.y-center.y)}];
  }));
  await rel.uncheck();const onlyPre=await read();
  await pre.uncheck();await rel.check();const onlyRel=await read();
  await rel.uncheck();const none=await read();
  await pre.check();await rel.check();
  const axes=[];
  for(const a of ['1','2','3','4','5','6']){
    await axis.selectOption(a);
    axes.push(await page.evaluate(()=>{
      const a=document.getElementById('axisSel').value;
      return {axis:a,actual_nodes:nodeG.children.length,expected_nodes:NODES.filter(n=>n.axis===a).length,actual_edges:edgeG.children.length,expected_edges:EDGES.filter(e=>byId[e.effective_source].axis===a&&byId[e.effective_target].axis===a).length};
    }));
  }
  await axis.selectOption('1');await rel.uncheck();
  const k1Pre=await read();
  const path=page.locator('#g > g').first().locator('path').first();await path.scrollIntoViewIfNeeded();
  const xy=await path.evaluate(p=>{const q=p.getPointAtLength(p.getTotalLength()/2),r=p.ownerSVGElement.getBoundingClientRect();return {x:r.x+q.x,y:r.y+q.y};});
  await page.mouse.move(xy.x,xy.y);
  const tooltip=await page.locator('#tipbox').innerText();
  await page.screenshot({path:'output/playwright/G_v2-先修悬停-修正后.png'});
  const samples=[];
  for(const id of ['1-02','1-03','1-07','1-11','1-13','1-14']){
    const close=page.locator('#panel button');if(await close.isVisible())await close.click();
    await page.getByText(id,{exact:true}).click();
    samples.push({id,title:await page.locator('#panel-title').innerText(),body:await page.locator('#panel-body').innerText()});
  }
  await page.locator('#panel button').click();await page.getByText('1-02',{exact:true}).click();
  await page.locator('#panel-body a[data-card="1-01"]').click();
  const navigationTitle=await page.locator('#panel-title').innerText();
  await page.screenshot({path:'output/playwright/G_v2-详情跳转-修正后.png'});
  const allPanelConsistency=await page.evaluate(()=>NODES.map(n=>{
    openPanel(n);const r=relsOf(n.card_id);
    const d=document.getElementById('panel-body').innerText;
    return {card_id:n.card_id,degree:r.degree,links:document.getElementById('panel-body').querySelectorAll('a[data-card]').length,definition_present:d.includes(DEFS[n.card_id])};
  }));
  await page.locator('#panel button').click();await axis.selectOption('');await rel.check();
  await page.screenshot({path:'output/playwright/G_v2-全图-修正后.png',fullPage:true});
  return {checked_at:'2026-10-01',all,onlyPre,onlyRel,none,axes,k1Pre,arrows,tooltip,node_click_samples:samples,link_navigation_title:navigationTitle,all_panel_consistency:allPanelConsistency,page_errors:errors};
}
