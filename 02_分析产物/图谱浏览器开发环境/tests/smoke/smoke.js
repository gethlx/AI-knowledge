import ForceGraph3D from '3d-force-graph';
import '@phosphor-icons/web/regular';
const el=document.querySelector('#graph'),status=document.querySelector('#status');
window.toolchainSmoke={ready:false,selected:null,paused:false};
try{
 const graph=new ForceGraph3D(el).width(el.clientWidth).height(el.clientHeight).backgroundColor('#091226').graphData({nodes:[{id:'a',name:'测试甲'},{id:'b',name:'测试乙'},{id:'c',name:'测试丙'}],links:[{source:'a',target:'b',kind:'prerequisite'},{source:'b',target:'c',kind:'related'}]}).nodeLabel('name').nodeColor(()=> '#85b5fc').linkColor(l=>l.kind==='prerequisite'?'#ffb65e':'#8091af').linkDirectionalArrowLength(l=>l.kind==='prerequisite'?4:0).onNodeClick(node=>{window.toolchainSmoke.selected=node.id;status.textContent='已选择 '+node.name;});
 window.smokeGraph=graph;
 document.querySelector('#pause').onclick=()=>{graph.pauseAnimation();window.toolchainSmoke.paused=true;status.textContent='已暂停';};
 document.querySelector('#resume').onclick=()=>{graph.resumeAnimation();window.toolchainSmoke.paused=false;status.textContent='已继续';};
 document.querySelector('#focus').onclick=()=>{const n=graph.graphData().nodes[0];graph.cameraPosition({x:n.x||0,y:n.y||0,z:(n.z||0)+120},n,0);window.toolchainSmoke.selected=n.id;status.textContent='已定位 测试甲';};
 const resize=new ResizeObserver(()=>graph.width(el.clientWidth).height(el.clientHeight));resize.observe(el);
 window.toolchainSmoke.ready=true;status.textContent='三维库已加载：3节点 / 2关系。';
}catch(error){window.toolchainSmoke.error=String(error);document.querySelector('#error').textContent=String(error);}
