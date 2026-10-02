import '@phosphor-icons/web/regular';
import '../styles/atlas.css';
import input from './preview-data.json';
import ForceGraph3D from '3d-force-graph';
import SpriteText from 'three-spritetext';
import { Vector3, Fog, MOUSE, TOUCH } from 'three';

// This read-only preview adapter can be replaced by WorkBuddy's production adapter.
const cards=new Map(input.cards.map(c=>[c.card_id,c]));
const nodes=new Map(input.graph.nodes.map(n=>[n.card_id,n]));
const edges=input.graph.edges;
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const name=id=>nodes.get(id)?.name??id;
const meaningful=s=>typeof s==='string'&&s.trim()!==''&&s.trim()!=='—';
const params=new URLSearchParams(location.search);
let selected=cards.has(location.hash.slice(1))?location.hash.slice(1):'4-03';
let focus=selected, mode=params.get('view')==='explore'?'explore':'reading';
let graph=null, rotating=false, graphReady=false, historyStack=[], searchMode='search', lastBrowserTrigger=null;
const saved=new Map();
const surface=$('#graph-surface'), labels=$('#node-labels');
const palette=['#708472','#b69962','#85949b','#9b8077','#688775'];
let visibleNodes=[], visibleEdges=[];
let moving=false, interacting=false, pendingFit=false, settleTimer;
let preferredLabels=[], overview=false;
const adjacent=new Map([...nodes.keys()].map(id=>[id,new Set()]));
for(const e of edges){adjacent.get(e.effective_source).add(e.effective_target);adjacent.get(e.effective_target).add(e.effective_source)}
function linkSpacing(e){
  const a=adjacent.get(e.effective_source),b=adjacent.get(e.effective_target);
  const common=[...a].filter(id=>b.has(id)).length;
  const overlap=common/Math.max(1,a.size+b.size-common);
  return 34+90*(1-overlap)+Math.log2(1+Math.max(a.size,b.size))*5;
}
const textSprites=new Map();
let labelHitBoxes=[], graphClickMoved=false, draggingNode=null, pauseAfterTap=false;
function hitLabel(x,y){const b=surface.getBoundingClientRect();return labelHitBoxes.find(r=>x-b.x>=r.left&&x-b.x<=r.right&&y-b.y>=r.top&&y-b.y<=r.bottom)?.id}
const endpoint=x=>typeof x==='object'?x.id:x;
const nodeMaterials=new Map(),lineMaterials=new Map();
const isActiveLink=e=>endpoint(e.source)===selected||endpoint(e.target)===selected;
function refreshLinks(){
  if(!graph)return;
  // Change the rendered materials without resetting the force simulation.
  for(const e of graph.graphData().links){
    const object=e.__lineObj;if(!object?.isLine)continue;
    const active=isActiveLink(e),key=active?'selected':'normal';
    if(!lineMaterials.has(key)){
      const material=object.material.clone();
      material.color.set(active?'#2f4d37':'#496250');material.opacity=active?0.92:0.8;
      lineMaterials.set(key,material);
    }
    object.material=lineMaterials.get(key);
  }
}
function refreshNodeColors(){
  for(const [id,sprite] of textSprites){
    const anchor=sprite.parent;if(!anchor?.isMesh)continue;
    const color=id===selected?'#ba914d':graph.graphData().nodes.find(n=>n.id===id)?.color;
    if(!nodeMaterials.has(color)){
      const material=anchor.material.clone();material.color.set(color);nodeMaterials.set(color,material);
    }
    anchor.material=nodeMaterials.get(color);
  }
}
function wrapName(text){return text.length>8?text.match(/.{1,8}/gu).join('\n'):text}
function makeLabel(n){
  let sprite=textSprites.get(n.id);
  if(!sprite){
    sprite=new SpriteText(wrapName(n.name),9,'#253d35');
    sprite.fontFace='AtlasSerif, serif';sprite.fontSize=56;sprite.fontWeight=600;
    sprite.backgroundColor='rgba(248,246,241,0.94)';sprite.padding=[1.7,.8];sprite.borderRadius=1;
    sprite.material.fog=false;sprite.material.depthTest=false;sprite.material.depthWrite=false;sprite.material.sizeAttenuation=false;sprite.renderOrder=30;
    sprite.userData.aspect=sprite.scale.x/sprite.scale.y;sprite.userData.lines=sprite.text.split('\n').length;
    sprite.center.set(.5,-.25);sprite.position.y=0;
    // Hidden labels must not intercept clicks or node drags.
    const raycast=sprite.raycast;
    sprite.raycast=function(raycaster,hits){if(this.visible)raycast.call(this,raycaster,hits)};
    textSprites.set(n.id,sprite);
  }
  return sprite;
}
function beginMotion(){moving=true;clearTimeout(settleTimer);syncLabels()}
function endMotion(){clearTimeout(settleTimer);settleTimer=setTimeout(()=>{moving=false;syncLabels()},160)}
function neighbors(id){
  const groups={before:[],after:[],related:[]};
  for(const e of edges){
    const a=e.effective_source,b=e.effective_target;
    if(a!==id&&b!==id)continue;
    const other=a===id?b:a;
    const kind=e.relation_type==='prerequisite'?(b===id?'before':'after'):'related';
    groups[kind].push({id:other,edge:e});
  }
  return groups;
}
function neighborTotal(id){return Object.values(neighbors(id)).reduce((n,a)=>n+a.length,0)}
function cameraState(){return graph?{position:{...graph.cameraPosition()},target:{...graph.controls().target}}:null}
function restoreCamera(c){if(c&&graph){graph.cameraPosition(c.position,c.target,0);syncLabels()}}
function saveReading(){saved.set(selected,{scroll:window.scrollY,explanation:$('#explanation').open,neighbors:$('#neighbors').open})}
function snapshot(){return {selected,focus,mode,camera:cameraState(),reading:{...saved.get(selected)}}}
const explanationKeys=['教学类比','典型案例','常见误解','反例','安全与伦理边界'];
function explanationHTML(id){
  const f=cards.get(id).fields;
  const prefixes={'教学类比':'','典型案例':'例如：','常见误解':'常见误解：','反例':'反例：','安全与伦理边界':'使用时留意：'};
  return explanationKeys.filter(k=>meaningful(f[k])).map(k=>'<p data-field="'+k+'">'+(prefixes[k]?'<span class="explanation-prefix">'+prefixes[k]+'</span>':'')+'<span>'+esc(f[k])+'</span></p>').join('');
}
function notify(text){$('#notice').textContent=text;$('#notice').hidden=false;clearTimeout(notify.timer);notify.timer=setTimeout(()=>$('#notice').hidden=true,4200)}
function renderCard(){
  const c=cards.get(selected),f=c.fields;
  $('#concept-title').textContent=name(selected);$('#english').textContent=c.en;
  $('#definition').textContent=f['精确定义'];
  $('#explanation-copy').innerHTML=explanationHTML(selected);
  $('#explanation').hidden=!$('#explanation-copy').textContent.trim();
  $('#explanation').open=saved.get(selected)?.explanation??mode==='reading';
  $('#neighbor-count').textContent=neighborTotal(selected);
  renderNeighbors();
  $('#neighbors').open=saved.get(selected)?.neighbors??true;
  renderContext();document.title=name(selected)+' · 银河AI知识图册';
  if(graph){refreshNodeColors();refreshLinks()}
  syncLabels();document.dispatchEvent(new CustomEvent('atlas:selection',{detail:{id:selected}}));
}
function renderNeighbors(){
  const groups=neighbors(selected);
  $('#neighbor-list').innerHTML=Object.entries(groups).map(([key,items])=>{
    const rows=items;
    if(!rows.length)return '';
    const heading={before:'先了解这些概念',after:'以它为基础',related:'其他关联'}[key];
    const content=rows.map(n=>'<details class="neighbor-card" data-neighbor="'+esc(n.id)+'"><summary class="neighbor-item"><i class="ph ph-file-text" aria-hidden="true"></i><span>'+esc(name(n.id))+'</span><i class="ph ph-caret-down disclosure" aria-hidden="true"></i></summary><div class="neighbor-reading"></div></details>').join('');
    return '<details class="neighbor-group" data-group="'+key+'"'+(key==='related'?'':' open')+'><summary class="neighbor-group-heading"><h3>'+heading+' · '+rows.length+'</h3><i class="ph ph-caret-down disclosure" aria-hidden="true"></i></summary>'+content+'</details>';
  }).join('')||'<p class="empty">暂无相邻概念。</p>';
}
function selectConcept(id){
  if(!cards.has(id))return false;
  if(id!==selected){
    saveReading();historyStack.push(snapshot());selected=id;
    renderCard();history.pushState({atlas:true},'', '#'+id);
  }
  closeBrowser();
  if(graphReady){
    if(!graph.graphData().nodes.some(n=>n.id===id)){focus=id;renderGraphData()}
    else centerSelected();
  }
  return true;
}
window.addEventListener('popstate',()=>{
  if(!historyStack.length)return;
  saveReading();const previous=historyStack.pop();
  selected=previous.selected;
  if(focus!==previous.focus){focus=previous.focus;renderGraphData()}
  renderCard();setMode(previous.mode,false);
  restoreCamera(previous.camera);preferredLabels=localNeighbors();syncLabels();window.scrollTo(0,previous.reading?.scroll??0);
});
history.replaceState({atlas:true},'',location.pathname+location.search+'#'+selected);
function setMode(next){
  // Only the graph changes size; reading always expands in the same document.
  const y=window.scrollY;mode=next;
  $('#atlas').className='atlas'+(next==='explore'?' graph-open':'');
  (next==='reading'?$('#thumbnail-graph'):$('#expanded-graph')).append(surface);
  if(graph){rotating=false;graph.controls().autoRotate=false;$('#pause').setAttribute('aria-pressed','false');$('#pause').innerHTML='<i class="ph ph-play" aria-hidden="true"></i>'}
  resizeGraph();renderContext();
  if(graphReady)centerSelected(false);
  window.scrollTo(0,y);document.dispatchEvent(new CustomEvent('atlas:mode',{detail:{mode}}));
}
function renderContext(){
  $('#focus-label').textContent='当前概念：'+name(selected);
  $('#thumbnail-focus').hidden=true;
  for(const b of labels.children)b.tabIndex=mode==='explore'?0:-1;
}
function graphDataForFocus(){
  // Exploration needs the full dataset; selecting a concept never clips the scene.
  visibleNodes=input.graph.nodes.map((n,i)=>({id:n.card_id,name:n.name,color:palette[i%palette.length]}));
  visibleEdges=edges.map(e=>({...e,source:e.effective_source,target:e.effective_target}));
  return {nodes:visibleNodes.map(n=>({...n})),links:visibleEdges.map(e=>({...e}))};
}
function localNeighbors(){
  if(!graph)return [];
  const n=graph.graphData().nodes.find(n=>n.id===selected);if(!n)return [];
  return graph.graphData().nodes.filter(m=>m.id!==selected&&adjacent.get(selected).has(m.id))
    .sort((a,b)=>Math.hypot(a.x-n.x,a.y-n.y,a.z-n.z)-Math.hypot(b.x-n.x,b.y-n.y,b.z-n.z)).slice(0,6).map(n=>n.id);
}
function syncLabels(){
  if(!graphReady)return;
  const camera=graph.camera(),w=surface.clientWidth,h=surface.clientHeight,occupied=[];
  if(!h)return;
  const tangent=Math.tan(camera.fov*Math.PI/360);
  // Ordinary 3D depth cue, independent of the selected concept or edge type.
  const viewDistance=camera.position.distanceTo(graph.controls().target);
  const fog=graph.scene().fog;
  if(fog){fog.near=viewDistance*.65;fog.far=viewDistance*1.35;}
  const limit=mode==='reading'?1:Infinity;
  graph.scene().updateMatrixWorld(true);labelHitBoxes=[];
  const candidates=graph.graphData().nodes.map(n=>{
    const sprite=textSprites.get(n.id);if(!sprite)return null;sprite.visible=false;
    const pixelHeight=(mode==='reading'?9:14)*sprite.userData.lines+6;
    sprite.scale.set(pixelHeight*2*tangent/h*sprite.userData.aspect,pixelHeight*2*tangent/h,1);
    const point=new Vector3(n.x,n.y,n.z);
    const eyeDepth=-point.clone().applyMatrix4(camera.matrixWorldInverse).z;
    const v=point.project(camera);
    const width=pixelHeight*sprite.userData.aspect,height=pixelHeight;
    const x=(v.x+1)*w/2,y=(1-v.y)*h/2;
    return {n,sprite,depth:v.z,x,y,width,height,priority:n.id===draggingNode?0:1,distance:Math.hypot(x-w/2,y-h/2)/(Math.min(w,h)/2)+.8*Math.log(Math.max(1,eyeDepth)),eyeDepth};
  }).filter(Boolean).sort((a,b)=>a.priority-b.priority||a.distance-b.distance||a.n.id.localeCompare(b.n.id));
  let count=0;
  for(const c of candidates){
    const box={left:c.x-c.width/2-3,right:c.x+c.width/2+3,top:c.y-1.25*c.height-3,bottom:c.y-.25*c.height+3};
    if(c.depth<-1||c.depth>1||box.left<2||box.right>w-2||box.top<2||box.bottom>h-2)continue;
    // Every visible region can reveal names, including during movement.
    if(mode==='reading'&&c.n.id!==selected)continue;
    if(count>=limit||occupied.some(b=>box.left<b.right&&box.right>b.left&&box.top<b.bottom&&box.bottom>b.top))continue;
    c.sprite.visible=true;c.sprite.material.opacity=1;
    occupied.push(box);labelHitBoxes.push({...box,id:c.n.id,width:c.width,height:c.height});count++;
  }
  surface.dataset.labelCount=count;surface.dataset.moving=String(moving||rotating);
}
function viewAt(target,distance,animated=false){
  const controls=graph.controls(),camera=graph.camera();
  const direction=camera.position.clone().sub(controls.target).normalize();
  if(!Number.isFinite(direction.x))direction.set(0,0,1);
  const to=new Vector3(target.x,target.y,target.z),position=to.clone().addScaledVector(direction,distance);
  graph.cameraPosition(position,to,animated&&!matchMedia('(prefers-reduced-motion: reduce)').matches?420:0);
  syncLabels();
}
function centerSelected(animated=true){
  if(!graph)return;
  const n=graph.graphData().nodes.find(n=>n.id===selected);if(!n)return;
  overview=false;preferredLabels=localNeighbors();
  const ns=graph.graphData().nodes.filter(n=>preferredLabels.includes(n.id));
  const distances=ns.map(m=>Math.hypot(m.x-n.x,m.y-n.y,m.z-n.z)).sort((a,b)=>a-b);
  const radius=Math.max(35,distances[Math.min(3,distances.length-1)]??50);
  const tangent=Math.tan(graph.camera().fov*Math.PI/360)*Math.min(1,surface.clientWidth/surface.clientHeight);
  viewAt(n,Math.max(70,radius/tangent*1.2),animated);
}
function fitGraph(){
  if(!graph)return;
  const ns=graph.graphData().nodes;if(!ns.length)return;overview=true;preferredLabels=localNeighbors();
  const lo=new Vector3(...['x','y','z'].map(k=>Math.min(...ns.map(n=>n[k]??0)))),hi=new Vector3(...['x','y','z'].map(k=>Math.max(...ns.map(n=>n[k]??0))));
  const center=lo.clone().add(hi).multiplyScalar(.5),radius=Math.max(...ns.map(n=>center.distanceTo(new Vector3(n.x,n.y,n.z))));
  const tangent=Math.tan(graph.camera().fov*Math.PI/360)*Math.min(1,surface.clientWidth/surface.clientHeight);
  viewAt(center,radius/tangent*1.12+radius*.3);syncLabels();
}
function zoomGraph(factor){
  if(!graph)return;const camera=graph.camera(),target=graph.controls().target;
  const distance=Math.max(35,Math.min(2000,camera.position.distanceTo(target)*factor));
  viewAt(target,distance);syncLabels();
}
function renderGraphData(){
  const data=graphDataForFocus();pendingFit=true;
  // Keyboard users can read every node; visual text lives inside the WebGL scene.
  labels.innerHTML=data.nodes.map(n=>'<button class="graph-a11y-node" data-concept="'+esc(n.id)+'" aria-label="阅读'+esc(n.name)+'">'+esc(n.name)+'</button>').join('');
  if(graph)graph.graphData(data);
  $('#graph-count').textContent=data.nodes.length;
  $('#edge-count').textContent=data.links.length;
  renderContext();requestAnimationFrame(syncLabels);
}
function resizeGraph(){
  if(!graph)return;
  const w=surface.clientWidth,h=surface.clientHeight;if(!w||!h)return;
  graph.width(w).height(h);syncLabels();
}
function focusSelected(){if(graphReady)centerSelected()}
function highlight(text,q){
  if(!q)return esc(text);
  const t=String(text),index=t.toLowerCase().indexOf(q.toLowerCase());
  if(index<0)return esc(t);
  return esc(t.slice(0,index))+'<mark>'+esc(t.slice(index,index+q.length))+'</mark>'+esc(t.slice(index+q.length));
}
function renderResults(){
  const q=$('#search-input').value.trim(), level=$('#level-filter').value;
  const matching=input.cards.filter(c=>(name(c.card_id)+' '+c.en).toLowerCase().includes(q.toLowerCase())&&(!level||c.fields['认知层级']===level));
  $('#browser-subtitle').textContent=searchMode==='directory'?'共197个概念':'';
  if(searchMode==='search'&&!q){$('#results').innerHTML='<p class="empty">输入中文或英文概念名称，查找你想了解的内容。</p>';return}
  const iconList=['brain','lightbulb','users','tree-structure','crosshair','globe'];
  $('#results').innerHTML='<p class="result-count">匹配概念名称（中文或英文） · '+matching.length+'个</p>'+matching.map((c,i)=>'<button class="concept-result" data-concept="'+esc(c.card_id)+'"><span class="result-icon"><i class="ph ph-'+iconList[i%iconList.length]+'" aria-hidden="true"></i></span><span class="result-copy"><strong>'+highlight(name(c.card_id),q)+'</strong><small>'+highlight(c.en,q)+'</small>'+(searchMode==='directory'?'<span class="level">'+esc(c.fields['认知层级'])+'</span>':'')+'</span><i class="ph ph-caret-right" aria-hidden="true"></i></button>').join('')+(matching.length?'':'<p class="empty">没有匹配的概念。试试更短的词，或浏览全部概念。</p>');
}
function openBrowser(type,trigger){
  lastBrowserTrigger=trigger??lastBrowserTrigger;searchMode=type;
  $('#browser-panel').hidden=false;$('#browser-panel').className='browser-panel '+type;
  $('#atlas').inert=true;document.body.style.overflow='hidden';
  $('#browser-title').textContent=type==='directory'?'概念目录':'查找概念';
  $('#search-input').value='';$('#level-filter').value='';renderResults();
  $('#search-input').focus();
}
function closeBrowser(){
  if($('#browser-panel').hidden)return;
  $('#browser-panel').hidden=true;$('#atlas').inert=false;document.body.style.overflow='';
  lastBrowserTrigger?.focus();
}
document.addEventListener('click',e=>{
  const concept=e.target.closest('[data-concept]');
  if(concept){selectConcept(concept.dataset.concept);return}
  const b=e.target.closest('[data-action]');if(!b)return;
  const action=b.dataset.action;
  if(action==='search'||action==='directory')openBrowser(action,b);
  else if(action==='close-browser')closeBrowser();
  else if(action==='read')$('#explanation').open=true;
  else if(action==='explore')setMode('explore');
  else if(action==='mode')setMode(mode==='reading'?'explore':'reading');
  else if(action==='focus')focusSelected();
  else if(action==='help')$('#help-dialog').showModal();
  else if(action==='locate')centerSelected();
  else if(action==='overview')fitGraph();
  else if(action==='zoom-in')zoomGraph(.75);
  else if(action==='zoom-out')zoomGraph(1.33);
  else if(action==='pause'){
    rotating=!rotating;if(graph){graph.controls().autoRotate=rotating;graph.controls().autoRotateSpeed=.35}
    b.setAttribute('aria-pressed',String(rotating));b.setAttribute('aria-label',rotating?'暂停旋转':'开始缓慢旋转');
    b.innerHTML='<i class="ph ph-'+(rotating?'pause':'play')+'" aria-hidden="true"></i>';syncLabels();
  }
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeBrowser()});
$('#search-input').addEventListener('input',renderResults);
$('#level-filter').addEventListener('change',renderResults);
$('#explanation').addEventListener('toggle',()=>{$('#explanation-toggle').textContent=$('#explanation').open?'收起说明':'展开阅读'});
document.addEventListener('toggle',e=>{
  const d=e.target;if(!d.matches?.('.neighbor-card')||!d.open)return;
  const body=d.querySelector('.neighbor-reading');if(body.childElementCount)return;
  const id=d.dataset.neighbor,f=cards.get(id).fields,explanation=explanationHTML(id);
  body.innerHTML='<h3>定义</h3><p>'+esc(f['精确定义'])+'</p>'+(explanation?'<h3>解释说明</h3>'+explanation:'');
},true);
renderCard();setMode(mode,false);
await document.fonts.ready;
try{
  graph=new ForceGraph3D($('#webgl'),{controlType:'orbit',rendererConfig:{antialias:true,alpha:true}});
  graph.backgroundColor('rgba(0,0,0,0)').showNavInfo(false).nodeLabel(n=>esc(n.name)).nodeRelSize(1.2).nodeVal(.65).nodeThreeObject(makeLabel).nodeThreeObjectExtend(true).nodeColor(n=>n.id===selected?'#ba914d':n.color)
    .linkColor(e=>isActiveLink(e)?'rgba(47,77,55,0.92)':'rgba(73,98,80,0.80)').linkOpacity(1).linkWidth(0)
    .linkDirectionalArrowLength(e=>e.relation_type==='prerequisite'?2.5:0).linkDirectionalArrowRelPos(.96).linkDirectionalArrowColor('#75846e')
    .enableNodeDrag(true).warmupTicks(200).cooldownTicks(75).cooldownTime(1200)
    .onNodeDrag(n=>{
      pauseAfterTap=false;graph.cooldownTicks(75);
      draggingNode=n.id;graphClickMoved=true;beginMotion();
      const position=graph.camera().position.clone(),target=graph.controls().target.clone();
      graph.cameraPosition(position,target,0);
      rotating=false;graph.controls().autoRotate=false;
      $('#pause').setAttribute('aria-pressed','false');$('#pause').setAttribute('aria-label','开始缓慢旋转');$('#pause').innerHTML='<i class="ph ph-play" aria-hidden="true"></i>';
    })
    .onNodeDragEnd(()=>{draggingNode=null;graphClickMoved=true;interacting=false}).onNodeClick((n,e)=>{if(!graphClickMoved)selectConcept(hitLabel(e.clientX,e.clientY)??n.id)}).onEngineStop(()=>{
      if(pendingFit){pendingFit=false;preferredLabels=localNeighbors();centerSelected(false)}
      if(pauseAfterTap){pauseAfterTap=false;graph.cooldownTicks(75)}
      if(!interacting&&!draggingNode)endMotion();
      syncLabels();
    })
    .onLinkClick(e=>{if(graphClickMoved)return;notify(e.relation_type==='prerequisite'?'学习'+name(e.effective_target)+'前，先了解“'+name(e.effective_source)+'”。':name(e.effective_source)+'与'+name(e.effective_target)+'存在关联。')});
  graph.scene().fog=new Fog('#f8f6f1',1,2000);
  graph.d3Force('charge').strength(-125);graph.d3Force('link').distance(linkSpacing).strength(.14);
  const controls=graph.controls();
  controls.minDistance=35;controls.maxDistance=2000;controls.zoomSpeed=.7;
  controls.enablePan=true;controls.screenSpacePanning=true;controls.zoomToCursor=true;
  controls.mouseButtons={LEFT:MOUSE.ROTATE,MIDDLE:MOUSE.DOLLY,RIGHT:MOUSE.PAN};
  controls.touches={ONE:TOUCH.ROTATE,TWO:TOUCH.DOLLY_PAN};
  graph.controls().addEventListener('change',()=>{if(interacting)beginMotion();else syncLabels()});
  graph.controls().addEventListener('start',()=>{
    // Cancel the one-shot camera tween at its current position, before user input.
    const position=graph.camera().position.clone(),target=graph.controls().target.clone();
    graph.cameraPosition(position,target,0);
    rotating=false;graph.controls().autoRotate=false;
    $('#pause').setAttribute('aria-pressed','false');$('#pause').setAttribute('aria-label','开始缓慢旋转');$('#pause').innerHTML='<i class="ph ph-play" aria-hidden="true"></i>';
    interacting=true;
  });
  graph.controls().addEventListener('end',()=>{interacting=false;endMotion()});
  let canvasStart=null;
  const canvas=graph.renderer().domElement;
  // This library emits a synthetic pointerup without the original pointer id.
  // Clear OrbitControls' active gesture before that event; use its public lifecycle.
  const finishNodeGesture=()=>{
    const controls=graph.controls();
    if(!controls.enabled){
      // DragControls restarts physics even for a stationary tap. Keep tap selection stable.
      if(!graphClickMoved&&!draggingNode){pauseAfterTap=true;graph.cooldownTicks(0)}
      controls.disconnect();controls.connect(canvas);
    }
  };
  canvas.addEventListener('pointerup',finishNodeGesture,true);
  canvas.addEventListener('pointercancel',finishNodeGesture,true);
  canvas.addEventListener('pointerdown',e=>{graphClickMoved=false;canvasStart={x:e.clientX,y:e.clientY}});
  canvas.addEventListener('pointermove',e=>{if(canvasStart&&Math.hypot(e.clientX-canvasStart.x,e.clientY-canvasStart.y)>6)graphClickMoved=true});
  canvas.addEventListener('pointercancel',()=>canvasStart=null);
  canvas.addEventListener('pointerup',e=>{
    const start=canvasStart;canvasStart=null;
    if((e.pointerType==='mouse'&&e.button!==0)||mode!=='explore'||!start||graphClickMoved||Math.hypot(e.clientX-start.x,e.clientY-start.y)>6)return;
    const labelId=hitLabel(e.clientX,e.clientY);if(labelId){selectConcept(labelId);return}
    const bounds=surface.getBoundingClientRect();
    const hit=graph.graphData().nodes.map(n=>{
      const p=graph.graph2ScreenCoords(n.x,n.y,n.z);
      return {id:n.id,distance:Math.hypot(p.x+bounds.x-e.clientX,p.y+bounds.y-e.clientY)};
    }).sort((a,b)=>a.distance-b.distance)[0];
    // A small visible sphere still needs a forgiving touch target.
    if(hit?.distance<=16)selectConcept(hit.id);
  });
  graphReady=true;renderGraphData();resizeGraph();
  graph.cameraPosition({x:0,y:0,z:220},{x:0,y:0,z:0},0);
  new ResizeObserver(resizeGraph).observe(surface);
  const updateSceneLabels=()=>{syncLabels();requestAnimationFrame(updateSceneLabels)};
  requestAnimationFrame(updateSceneLabels);
}catch(error){
  $('#graph-error').hidden=false;$('#graph-error').textContent='三维视图暂时无法加载。你仍可阅读正文，并在相邻概念清单中继续浏览。';
  console.error(error);
}
// Stable UI entry points for the production scene/state adapter; no source writes.
window.atlasUI={
  selectConcept,setMode,focusSelected,
  getState:()=>({selected,focus,mode,overview,scope:'full',labelPolicy:'viewport',preferredLabels:[...preferredLabels],labelBoxes:labelHitBoxes.map(b=>({...b})),graphReady,visible:visibleNodes.map(n=>n.id),edgeCount:visibleEdges.length,labelCount:Number(surface.dataset.labelCount??0),moving:surface.dataset.moving==='true',camera:cameraState()}),
  readCard:id=>cards.get(id),
  getNeighbors:neighbors,
  graph:()=>graph
};
