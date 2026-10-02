import '@phosphor-icons/web/regular';
import '../styles/atlas.css';
import input from './preview-data.json';
import ForceGraph3D from '3d-force-graph';

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
let focus='4-03', mode=params.get('view')==='explore'?'explore':'reading';
let graph=null, rotating=false, graphReady=false, historyStack=[], searchMode='search', lastBrowserTrigger=null;
const saved=new Map();
const surface=$('#graph-surface'), labels=$('#node-labels');
const palette=['#708472','#b69962','#85949b','#9b8077','#688775'];
let visibleNodes=[], visibleEdges=[];
const positions=[{fx:0,fy:0,fz:6},{fx:-44,fy:42,fz:0},{fx:43,fy:43,fz:-7},{fx:-47,fy:-34,fz:9},{fx:0,fy:-52,fz:-5},{fx:43,fy:-25,fz:3}];
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
function saveReading(){
  saved.set(selected,{scroll:mode==='reading'?window.scrollY:(saved.get(selected)?.scroll??0),more:$('#more').open,sources:$('#sources').open,neighbors:$('#neighbors').open});
}
function snapshot(){return {selected,focus,mode,camera:cameraState(),reading:{...saved.get(selected)}}}
function notify(text){$('#notice').textContent=text;$('#notice').hidden=false;clearTimeout(notify.timer);notify.timer=setTimeout(()=>$('#notice').hidden=true,4200)}
function renderCard(){
  const c=cards.get(selected), f=c.fields;
  $('#concept-title').textContent=name(selected);$('#english').textContent=c.en;
  $('#level').textContent='认知层级：'+f['认知层级'];
  $('#definition').textContent=f['精确定义'];
  $('#case').textContent=f['典型案例'];$('#case-section').hidden=!meaningful(f['典型案例']);
  $('#safety').textContent=f['安全与伦理边界'];$('#safety-section').hidden=!meaningful(f['安全与伦理边界']);
  const more=['教学类比','常见误解','反例'].filter(k=>meaningful(f[k]));
  $('#more').hidden=more.length===0;
  $('#more-copy').innerHTML=more.map(k=>'<p>'+esc(f[k])+'</p>').join('');
  $('#source-copy').innerHTML=['来源依据','深度上限'].filter(k=>meaningful(f[k])).map(k=>'<p><span class="meta-label">'+(k==='深度上限'?'阅读范围':'来源')+'</span>'+esc(f[k])+'</p>').join('');
  $('#sources').hidden=!$('#source-copy').textContent.trim();
  $('#neighbor-count').textContent=neighborTotal(selected);
  $('#neighbor-filter').value='';renderNeighbors();
  const prev=saved.get(selected);
  $('#more').open=prev?.more??false;$('#sources').open=prev?.sources??false;$('#neighbors').open=prev?.neighbors??false;
  $('#back').disabled=historyStack.length===0;
  renderContext();
  document.title=name(selected)+' · 银河AI知识图册';
  if(graph)graph.nodeColor(n=>n.id===selected?'#ba914d':n.color);
  syncLabels();
  document.dispatchEvent(new CustomEvent('atlas:selection',{detail:{id:selected}}));
}
function renderNeighbors(){
  const q=$('#neighbor-filter').value.trim().toLowerCase();
  const groups=neighbors(selected);
  $('#neighbor-list').innerHTML=Object.entries(groups).map(([key,items])=>{
    const rows=items.filter(n=>(name(n.id)+' '+cards.get(n.id).en).toLowerCase().includes(q));
    if(!rows.length)return '';
    const heading={before:'先了解这些概念',after:'以它为基础',related:'其他关联'}[key];
    return '<section class="neighbor-group"><h3>'+heading+' · '+rows.length+'</h3>'+rows.map(n=>'<button class="neighbor-item" data-concept="'+esc(n.id)+'"><i class="ph ph-file-text" aria-hidden="true"></i><span>'+esc(name(n.id))+'</span><i class="ph ph-caret-right" aria-hidden="true"></i></button>').join('')+'</section>';
  }).join('')||'<p class="empty">没有匹配的相邻概念，试试其他名称。</p>';
}
function selectConcept(id){
  if(!cards.has(id))return false;
  if(id===selected){closeBrowser();return true}
  saveReading();historyStack.push(snapshot());
  selected=id;closeBrowser();renderCard();
  history.pushState({atlas:true},'', '#'+id);
  window.scrollTo(0,saved.get(id)?.scroll??0);
  return true;
}
function goBack(){
  if(!historyStack.length)return;
  history.back();
}
window.addEventListener('popstate',()=>{
  if(!historyStack.length)return;
  saveReading();const previous=historyStack.pop();
  selected=previous.selected;
  if(focus!==previous.focus){focus=previous.focus;renderGraphData()}
  renderCard();setMode(previous.mode,false);
  restoreCamera(previous.camera);window.scrollTo(0,previous.reading?.scroll??0);
});
history.replaceState({atlas:true},'',location.pathname+location.search+'#'+selected);
function setMode(next,remember=true){
  if(remember&&mode==='reading')saveReading();
  mode=next;$('#atlas').className='atlas '+mode;
  (mode==='reading'?$('#thumbnail-graph'):$('#expanded-graph')).append(surface);
  if(graph){rotating=false;graph.controls().autoRotate=false;$('#pause').setAttribute('aria-pressed','false');$('#pause').setAttribute('aria-label','开始缓慢旋转');$('#pause').innerHTML='<i class="ph ph-play" aria-hidden="true"></i>'}
  resizeGraph();renderContext();
  window.scrollTo(0,mode==='reading'?(saved.get(selected)?.scroll??0):0);
  document.dispatchEvent(new CustomEvent('atlas:mode',{detail:{mode}}));
}
function renderContext(){
  $('#focus-label').textContent=name(focus)+'的关系';
  $('#context-name').textContent=selected!==focus?'图谱聚焦：'+name(focus):'';
  $('#thumbnail-focus').hidden=selected===focus;
  $('#thumbnail-focus').textContent='聚焦：'+name(focus);
}
function graphDataForFocus(){
  const grouped=neighbors(focus);
  // Six real concepts form the visual preview. Full neighbor rows are never truncated.
  let items=[...grouped.before,...grouped.after,...grouped.related];
  if(focus==='4-03'){
    const order=['3-04','3-21','4-04','4-02','4-05'];
    items=order.map(id=>items.find(n=>n.id===id)).filter(Boolean);
  }else items=items.slice(0,5);
  visibleNodes=[focus,...items.map(x=>x.id)].map((id,i)=>({id,name:name(id),...positions[i],color:i===0?'#ba914d':palette[i-1]}));
  visibleEdges=items.map(x=>({...x.edge,source:x.edge.effective_source,target:x.edge.effective_target}));
  return {nodes:visibleNodes.map(n=>({...n})),links:visibleEdges.map(e=>({...e}))};
}
function syncLabels(){
  if(!graphReady)return;
  for(const b of labels.children){
    const n=graph.graphData().nodes.find(x=>x.id===b.dataset.concept);if(!n)continue;
    const p=graph.graph2ScreenCoords(n.x??n.fx,n.y??n.fy,n.z??n.fz);
    b.style.left=p.x+'px';b.style.top=(p.y-(n.id===focus?0:8))+'px';
    b.classList.toggle('selected',n.id===selected);b.classList.toggle('current',n.id===focus);
    b.tabIndex=mode==='reading'?-1:0;
    b.hidden=mode==='reading'&&!['4-03','3-04','4-04',focus].includes(n.id);
  }
}
function renderGraphData(){
  const data=graphDataForFocus();
  labels.innerHTML=data.nodes.map(n=>'<button class="node-label" data-concept="'+esc(n.id)+'" aria-label="阅读'+esc(n.name)+'">'+esc(n.name)+'</button>').join('');
  if(graph)graph.graphData(data);
  $('#graph-count').textContent=data.nodes.length;
  renderContext();requestAnimationFrame(syncLabels);
}
function resizeGraph(){
  if(!graph)return;
  const w=surface.clientWidth,h=surface.clientHeight;if(!w||!h)return;
  graph.width(w).height(h);syncLabels();
}
function focusSelected(){
  saveReading();
  focus=selected;renderGraphData();setMode('explore');
  // Fitting is an explicit operation. Node selection never calls this.
  graph?.cameraPosition({x:0,y:0,z:180},{x:0,y:0,z:0},0);
  syncLabels();
  notify('已聚焦'+name(focus)+'的关系；当前三维样式展示'+visibleNodes.length+'个概念，完整关联在下方清单。');
}
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
  if(suppressHandleClick&&e.target.closest('.sheet-handle')){suppressHandleClick=false;return}
  const concept=e.target.closest('[data-concept]');
  if(concept){selectConcept(concept.dataset.concept);return}
  const b=e.target.closest('[data-action]');if(!b)return;
  const action=b.dataset.action;
  if(action==='search'||action==='directory')openBrowser(action,b);
  else if(action==='close-browser')closeBrowser();
  else if(action==='back')goBack();
  else if(action==='read')setMode('reading');
  else if(action==='explore')setMode('explore');
  else if(action==='mode')setMode(mode==='reading'?'explore':'reading');
  else if(action==='focus')focusSelected();
  else if(action==='help')$('#help-dialog').showModal();
  else if(action==='locate'){graph?.cameraPosition({x:0,y:0,z:180},{x:0,y:0,z:0},0);syncLabels()}
  else if(action==='pause'){
    rotating=!rotating;if(graph){graph.controls().autoRotate=rotating;graph.controls().autoRotateSpeed=.35}
    b.setAttribute('aria-pressed',String(rotating));b.setAttribute('aria-label',rotating?'暂停旋转':'开始缓慢旋转');
    b.innerHTML='<i class="ph ph-'+(rotating?'pause':'play')+'" aria-hidden="true"></i>';
  }
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeBrowser()});
$('#search-input').addEventListener('input',renderResults);
$('#level-filter').addEventListener('change',renderResults);
$('#neighbor-filter').addEventListener('input',renderNeighbors);
// Dragging the handle changes only panel size; content still has native touch scroll.
let startY=null,suppressHandleClick=false;
$('.sheet-handle').addEventListener('pointerdown',e=>{startY=e.clientY;e.currentTarget.setPointerCapture(e.pointerId)});
$('.sheet-handle').addEventListener('pointerup',e=>{if(startY!==null&&startY-e.clientY>35){suppressHandleClick=true;setMode('reading')}startY=null});
$('.sheet-handle').addEventListener('pointercancel',()=>startY=null);
renderCard();setMode(mode,false);
await document.fonts.ready;
try{
  graph=new ForceGraph3D($('#webgl'),{controlType:'orbit',rendererConfig:{antialias:true,alpha:true}});
  graph.backgroundColor('rgba(0,0,0,0)').showNavInfo(false).nodeLabel(()=>null).nodeRelSize(1.6).nodeVal(n=>n.id===selected?1.8:.65).nodeColor(n=>n.id===selected?'#ba914d':n.color)
    .linkColor(e=>e.relation_type==='prerequisite'?'#75846e':'#a5a8a0').linkOpacity(.72).linkWidth(.3)
    .linkDirectionalArrowLength(e=>e.relation_type==='prerequisite'?2.5:0).linkDirectionalArrowRelPos(.96).linkDirectionalArrowColor('#75846e')
    .enableNodeDrag(false).cooldownTicks(1).onNodeClick(n=>selectConcept(n.id)).onEngineStop(syncLabels)
    .onLinkClick(e=>notify(e.relation_type==='prerequisite'?'学习'+name(e.effective_target)+'前，先了解“'+name(e.effective_source)+'”。':name(e.effective_source)+'与'+name(e.effective_target)+'存在关联。'));
  graph.controls().addEventListener('change',syncLabels);
  let canvasStart=null;
  const canvas=graph.renderer().domElement;
  canvas.addEventListener('pointerdown',e=>{canvasStart={x:e.clientX,y:e.clientY}});
  canvas.addEventListener('pointercancel',()=>canvasStart=null);
  canvas.addEventListener('pointerup',e=>{
    const start=canvasStart;canvasStart=null;
    if(mode!=='explore'||!start||Math.hypot(e.clientX-start.x,e.clientY-start.y)>6)return;
    const bounds=surface.getBoundingClientRect();
    const hit=graph.graphData().nodes.map(n=>{
      const p=graph.graph2ScreenCoords(n.x,n.y,n.z);
      return {id:n.id,distance:Math.hypot(p.x+bounds.x-e.clientX,p.y+bounds.y-e.clientY)};
    }).sort((a,b)=>a.distance-b.distance)[0];
    // A small visible sphere still needs a forgiving touch target.
    if(hit?.distance<=16)selectConcept(hit.id);
  });
  graphReady=true;renderGraphData();resizeGraph();
  graph.cameraPosition({x:0,y:0,z:180},{x:0,y:0,z:0},0);
  new ResizeObserver(resizeGraph).observe(surface);
  requestAnimationFrame(syncLabels);
}catch(error){
  $('#graph-error').hidden=false;$('#graph-error').textContent='三维视图暂时无法加载。你仍可阅读正文，并在相邻概念清单中继续浏览。';
  console.error(error);
}
// Stable UI entry points for the production scene/state adapter; no source writes.
window.atlasUI={
  selectConcept,setMode,focusSelected,
  getState:()=>({selected,focus,mode,graphReady,visible:visibleNodes.map(n=>n.id),camera:cameraState()}),
  readCard:id=>cards.get(id),
  getNeighbors:neighbors,
  graph:()=>graph
};
