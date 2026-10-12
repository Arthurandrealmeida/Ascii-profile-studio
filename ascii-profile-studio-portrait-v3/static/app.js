'use strict';
const $ = id => document.getElementById(id);
const deep = obj => JSON.parse(JSON.stringify(obj));
let cfg = null, history = [], future = [], snapshot = '', lastChange = 0;
let svgURL = null, photoURL = null, photoImg = null, renderTicket = 0, timer = null, dirty = false, dragInfo = null;
const labels = {background:'Fundo', text:'Texto', key:'Rótulos', value:'Valores', muted:'Pontilhado', addition:'Adições (+)', deletion:'Remoções (-)'};
const layoutLabels = {padding:'Margem', portrait_x:'Posição do rosto',top:'Margem superior',column_gap:'Separação',left_min_width:'Largura esquerda',right_width:'Largura direita',label_width:'Coluna dos rótulos',line_height:'Altura da linha',section_gap:'Entre seções',min_height:'Altura mínima'};
const layoutRanges = {padding:[8,70,1],portrait_x:[0,100,1],top:[18,85,1],column_gap:[4,100,1],left_min_width:[150,680,1],right_width:[420,1150,1],label_width:[160,550,1],line_height:[1,2.5,.05],section_gap:[0,50,1],min_height:[200,1300,10]};
const PRESETS = {
  andrew:{theme:{background:'#161b22',text:'#c9d1d9',key:'#ffa657',value:'#a5d6ff',muted:'#616e7f',addition:'#3fb950',deletion:'#f85149',font_size:15},layout:{padding:16,portrait_x:15,top:30,column_gap:18,left_min_width:332,right_width:640,label_width:292,line_height:1.33,section_gap:13,min_height:530},portrait:{columns:94,rows:72,mode:'portrait',font_scale:.46}},
  compact:{theme:{background:'#0c1119',text:'#d2dde9',key:'#efb86a',value:'#c0d7f4',muted:'#60738e',addition:'#56ca96',deletion:'#f06e73',font_size:13},layout:{padding:12,portrait_x:10,top:24,column_gap:8,left_min_width:260,right_width:510,label_width:220,line_height:1.2,section_gap:7,min_height:390},portrait:{columns:32,rows:28,mode:'dither'}},
  neon:{theme:{background:'#090e1c',text:'#dbecff',key:'#e987fd',value:'#56eaff',muted:'#536b88',addition:'#3fffaf',deletion:'#ff527b',font_size:15},layout:{padding:20,portrait_x:18,top:35,column_gap:26,left_min_width:350,right_width:670,label_width:310,line_height:1.42,section_gap:15,min_height:570},portrait:{columns:40,rows:30,mode:'edges'}},
  minimal:{theme:{background:'#10151b',text:'#e0e5e9',key:'#c9cfd5',value:'#b8c6d2',muted:'#61717e',addition:'#69bd98',deletion:'#df8b8b',font_size:14},layout:{padding:25,portrait_x:22,top:30,column_gap:35,left_min_width:320,right_width:610,label_width:270,line_height:1.47,section_gap:18,min_height:550},portrait:{columns:34,rows:28,mode:'classic'}}
};
function setStatus(message, type='') {$('status').textContent = message;$('status').className=type;$('dirty-indicator').textContent = dirty?'● Não salvo':'';}
function historyChange({structural=false, photo=false}={}) {
  if(!cfg) return;
  const next = JSON.stringify(cfg);if(next===snapshot)return;
  const now=Date.now();if(now-lastChange > 650 || structural || !history.length){history.push(snapshot);if(history.length>75)history.shift();}
  snapshot=next;lastChange=now;future=[];dirty=true;
  if(structural)drawSections();if(photo)loadPhoto();
  updateUndo();scheduleRender();
}
function updateUndo(){ $('undo').disabled = history.length===0;$('redo').disabled=future.length===0; }
function historyTravel(direction){
  const from=direction==='undo'?history:future, to=direction==='undo'?future:history;
  if(!from.length)return;to.push(snapshot);snapshot=from.pop();cfg=JSON.parse(snapshot);dirty=true;lastChange=0;
  refreshControls();drawSections();loadPhoto();updateUndo();scheduleRender();
}
function wireInput(id,obj,key,number=false, action){
  const node=$(id);
  const sync=()=>{node.value=obj[key];};
  sync();node.addEventListener('input',()=>{
    if(!cfg)return;const current=action?cfg[action]:obj;current[key] = number?Number(node.value):node.value;
    const display=$(id+'-display');if(display)display.textContent=node.value;
    historyChange(); if(['columns','rows','zoom','center_x','center_y'].includes(key))drawCrop();
  });
}
function make(tag,classname='',text=''){const node=document.createElement(tag);if(classname)node.className=classname;if(text)node.textContent=text;return node;}
function btn(title,handler,classname=''){const element=make('button',classname,title);element.type='button';element.addEventListener('click',handler);return element;}
function textField(value,update,placeholder=''){
  const inp=make('input');inp.type='text';inp.value=value||'';inp.placeholder=placeholder;
  inp.addEventListener('input',()=>{update(inp.value);historyChange();});return inp;
}
function move(list,from,to){if(from===to||to<0||to>=list.length)return;list.splice(to,0,list.splice(from,1)[0]);historyChange({structural:true});}
function attachDrag(handle,card,identity,doDrop){
  handle.draggable=true;handle.setAttribute('aria-label','Arrastar para reorganizar');
  handle.addEventListener('dragstart',e=>{dragInfo=identity;card.classList.add('dragging');e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain','move');});
  card.addEventListener('dragover',e=>{if(dragInfo && dragInfo.kind===identity.kind && (identity.kind==='section'||dragInfo.section===identity.section)){e.preventDefault();card.classList.add('dragover');}});
  card.addEventListener('dragleave',()=>card.classList.remove('dragover'));
  card.addEventListener('drop',e=>{e.preventDefault();card.classList.remove('dragover');if(dragInfo)doDrop(dragInfo);dragInfo=null;});
  handle.addEventListener('dragend',()=>{dragInfo=null;document.querySelectorAll('.dragging,.dragover').forEach(e=>e.classList.remove('dragging','dragover'));});
}
function drawSections(){
  const root=$('sections');root.replaceChildren();
  cfg.sections.forEach((section,si)=>{
    const card=make('div','section-card');const heading=make('div','sectionhead');const handle=btn('⠿',()=>{},'drag');
    heading.append(handle,textField(section.title, v=>section.title=v, 'Título opcional'));
    const controls=make('div','ops');controls.append(btn('↑',()=>move(cfg.sections,si,si-1)),btn('↓',()=>move(cfg.sections,si,si+1)),btn('×',()=>{if(confirm('Remover seção?')){cfg.sections.splice(si,1);historyChange({structural:true});}},'danger'));
    heading.append(controls);card.append(heading);
    attachDrag(handle,card,{kind:'section',index:si},from=>{if(from.kind==='section')move(cfg.sections,from.index,si);});
    section.rows.forEach((row,ri)=>{
      const r=make('div','row-card');const lbl=make('label','','Rótulo');lbl.append(textField(row.label,v=>row.label=v,'Nome'));
      const val=make('label','','Valor');val.append(textField(row.value,v=>row.value=v,'Conteúdo'));
      const operations=make('div','ops');const drag=btn('⠿',()=>{},'drag');operations.append(drag,btn('↑',()=>move(section.rows,ri,ri-1)),btn('↓',()=>move(section.rows,ri,ri+1)),btn('×',()=>{section.rows.splice(ri,1);historyChange({structural:true});},'danger'));
      r.append(lbl,val,operations);card.append(r);
      attachDrag(drag,r,{kind:'row',section:si,index:ri},from=>{if(from.kind==='row' && from.section===si)move(section.rows,from.index,ri);});
    });
    card.append(btn('+ Campo',()=>{if(section.rows.length>=80){setStatus('Máximo de 80 campos por seção','error');return;}section.rows.push({label:'Novo campo',value:'Novo valor'});historyChange({structural:true});},'add-field'));
    root.append(card);
  });
}
function createLayoutControls(){
  const root=$('layout-controls');root.replaceChildren();
  for(const [key,[min,max,step]] of Object.entries(layoutRanges)){
    const label=make('label','',layoutLabels[key]+' ');const output=make('output');output.id=key+'-display';
    const slider=make('input');slider.type='range';slider.id=key;slider.min=min;slider.max=max;slider.step=step;
    label.append(output,slider);root.append(label);
    slider.addEventListener('input',()=>{cfg.layout[key]=Number(slider.value);output.textContent=slider.value;historyChange();});
  }
}
function createColors(){
  for(const [target,mode] of [['dark-colors','dark'],['light-colors','light']]){
    const root=$(target);root.replaceChildren();
    for(const [key,title] of Object.entries(labels)){
      const label=make('label','',title);const input=make('input');input.type='color';input.id=mode+'-'+key;
      label.append(input);root.append(label);
      input.addEventListener('input',()=>{const pal=mode==='light'?cfg.theme.light:cfg.theme;pal[key]=input.value;historyChange();});
    }
  }
}
function refreshControls(){
  if(!cfg)return;
  for(const [id,val] of [['username',cfg.profile.username],['hostname',cfg.profile.title],['charset',cfg.portrait.charset],['mode',cfg.portrait.mode]])$(id).value=val;
  for(const key of ['columns','rows','contrast','brightness','zoom','center_x','center_y','edge_strength','sharpness','local_contrast','font_scale']){
    $(key).value=cfg.portrait[key];const out=$(key+'-display');if(out)out.textContent=cfg.portrait[key];
  }
  $('invert').checked=cfg.portrait.invert;$('auto_update').checked=cfg.github.auto_update;
  $('font_size').value=cfg.theme.font_size;$('font_size-display').textContent=cfg.theme.font_size;
  for(const key of Object.keys(layoutRanges)){ $(key).value=cfg.layout[key];$(key+'-display').textContent=cfg.layout[key]; }
  for(const name of Object.keys(labels)){ $('dark-'+name).value=cfg.theme[name];$('light-'+name).value=cfg.theme.light[name]; }
  $('last-stats').textContent=cfg.github.updated_at?'Dados consultados em '+cfg.github.updated_at:'Nenhuma consulta feita ainda.';
  drawCrop();
}
function setCropPhoto(url){
  if(photoURL && photoURL.startsWith('blob:'))URL.revokeObjectURL(photoURL);
  photoURL=url;const img=new Image();img.onload=()=>{if(photoURL!==url)return;photoImg=img;drawCrop();};img.onerror=()=>{photoImg=null;drawCrop();};img.src=url;
}
function loadPhoto(){if(!cfg)return;setCropPhoto('/api/photo-preview?path='+encodeURIComponent(cfg.profile.photo)+'&v='+encodeURIComponent(cfg.profile.photo));}
function cropGeometry(){
  if(!photoImg || !cfg)return null;
  const canvas=$('crop'),iw=photoImg.naturalWidth,ih=photoImg.naturalHeight;
  const scale=Math.min(canvas.width/iw,canvas.height/ih);
  const px=(canvas.width-iw*scale)/2,py=(canvas.height-ih*scale)/2;
  const ratio=cfg.portrait.columns*.57/cfg.portrait.rows;
  let cw,ch;if(iw/ih>ratio){ch=ih;cw=ih*ratio;}else{cw=iw;ch=iw/ratio;}
  cw/=cfg.portrait.zoom;ch/=cfg.portrait.zoom;
  const left=Math.max(0,Math.min(iw-cw,cfg.portrait.center_x*iw-cw/2));
  const top=Math.max(0,Math.min(ih-ch,cfg.portrait.center_y*ih-ch/2));
  return {iw,ih,scale,px,py,left,top,cw,ch};
}
function drawCrop(){
  const canvas=$('crop');if(!canvas)return;const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);
  if(!photoImg){ctx.fillStyle='#aac0d6';ctx.font='15px sans-serif';ctx.fillText('Selecione uma foto para editar o recorte.',22,canvas.height/2);return;}
  const g=cropGeometry();ctx.drawImage(photoImg,g.px,g.py,g.iw*g.scale,g.ih*g.scale);
  ctx.fillStyle='rgba(0,0,0,.52)';ctx.fillRect(g.px,g.py,g.iw*g.scale,g.ih*g.scale);
  ctx.save();ctx.beginPath();ctx.rect(g.px+g.left*g.scale,g.py+g.top*g.scale,g.cw*g.scale,g.ch*g.scale);ctx.clip();ctx.drawImage(photoImg,g.px,g.py,g.iw*g.scale,g.ih*g.scale);ctx.restore();
  ctx.strokeStyle='#ffc477';ctx.lineWidth=2;ctx.strokeRect(g.px+g.left*g.scale,g.py+g.top*g.scale,g.cw*g.scale,g.ch*g.scale);
}
function initCropPointer(){
  const canvas=$('crop');let start=null;
  canvas.addEventListener('pointerdown',e=>{if(!cfg||!photoImg)return;const r=canvas.getBoundingClientRect();const g=cropGeometry();start={x:e.clientX,y:e.clientY,cx:cfg.portrait.center_x,cy:cfg.portrait.center_y,sx:g.iw*g.scale*r.width/canvas.width,sy:g.ih*g.scale*r.height/canvas.height};canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointermove',e=>{if(!start)return;cfg.portrait.center_x=Math.max(0,Math.min(1,start.cx+(e.clientX-start.x)/start.sx));cfg.portrait.center_y=Math.max(0,Math.min(1,start.cy+(e.clientY-start.y)/start.sy));$('center_x').value=cfg.portrait.center_x;$('center_y').value=cfg.portrait.center_y;$('center_x-display').textContent=cfg.portrait.center_x.toFixed(2);$('center_y-display').textContent=cfg.portrait.center_y.toFixed(2);drawCrop();historyChange();});
  for(const event of ['pointerup','pointercancel'])canvas.addEventListener(event,()=>start=null);
}
function scheduleRender(){setStatus('Atualizando prévia...');clearTimeout(timer);timer=setTimeout(render,260);}
async function jsonPost(url,payload){const res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(!res.ok){let info;try{info=await res.json();}catch{info={error:'HTTP '+res.status};}throw Error(info.error||'Erro ao consultar o servidor.');}return res;}
async function render(){if(!cfg)return;const ticket=++renderTicket;try{
  const response=await jsonPost('/api/render',{...cfg,preview_light:$('light').checked});const blob=await response.blob();if(ticket!==renderTicket)return;
  const next=URL.createObjectURL(blob);const old=svgURL;svgURL=next;$('preview-img').src=next;if(old)URL.revokeObjectURL(old);
  setStatus(dirty?'Prévia atualizada • alterações não salvas':'Prévia atualizada','good');
}catch(err){if(ticket===renderTicket)setStatus(err.message,'error');}}
async function exportSVG(variant){try{
  setStatus('Exportando a configuração atual...');const response=await jsonPost('/api/export',{...cfg,variant});const blob=await response.blob();const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=variant+'_mode.svg';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);setStatus('SVG exportado da configuração atual','good');
}catch(err){setStatus(err.message,'error');}}
async function exportPortrait(){try{
  setStatus('Exportando retrato ASCII isolado...');
  const response=await jsonPost('/api/export-portrait',cfg);const blob=await response.blob();
  const url=URL.createObjectURL(blob);const link=document.createElement('a');
  link.href=url;link.download='portrait_only.svg';document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1500);setStatus('Retrato ASCII exportado','good');
}catch(err){setStatus(err.message,'error');}}
async function save(){try{
  setStatus('Salvando...');await jsonPost('/api/save',cfg);dirty=false;setStatus('SVGs e config.yaml salvos em disco.','good');
}catch(err){setStatus(err.message,'error');}}
async function upload(file){
  try{setStatus('Lendo foto...');const resp=await fetch('/api/photo',{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream'},body:file});const data=await resp.json();if(!resp.ok)throw Error(data.error);
    cfg.profile.photo=data.path;cfg.portrait.center_x=.5;cfg.portrait.center_y=.5;cfg.portrait.zoom=1;historyChange({photo:true});refreshControls();setStatus('Foto enviada localmente. Salve quando terminar.','good');
  }catch(err){setStatus(err.message,'error');}}
async function updateStats(){try{
  setStatus('Consultando GitHub...');const response=await jsonPost('/api/stats',{username:cfg.profile.username});const data=await response.json();cfg.github.cached=data.cached;cfg.github.updated_at=data.updated_at;
  let section=cfg.sections.find(s=>s.title.toLowerCase().includes('github stat'));
  if(!section){section={title:'GitHub Stats',rows:[]};cfg.sections.push(section);}
  const options=[['Repositórios','public_repos'],['Seguidores','followers'],['Estrelas recebidas','stars_received'],['Forks recebidos','forks_received']];
  for(const [label,key] of options){let row=section.rows.find(r=>r.label===label);if(!row){row={label,value:''};section.rows.push(row);}row.value='{{github.'+key+'}}';}
  historyChange({structural:true});refreshControls();setStatus('Estatísticas atualizadas; campos vinculados aos dados do GitHub.','good');
}catch(err){setStatus('Falha ao consultar GitHub: '+err.message,'error');}}
function init(){
  createLayoutControls();createColors();
  for(const [id,parent,key,isNumber] of [['username','profile','username',false],['hostname','profile','title',false],['charset','portrait','charset',false],['mode','portrait','mode',false], ...['columns','rows','contrast','brightness','zoom','center_x','center_y','edge_strength','sharpness','local_contrast','font_scale'].map(key=>[key,'portrait',key,true])]){
    $(id).addEventListener('input',e=>{cfg[parent][key]=isNumber?Number(e.target.value):e.target.value;const out=$(id+'-display');if(out)out.textContent=e.target.value;historyChange();if(['columns','rows','zoom','center_x','center_y'].includes(key))drawCrop();});
  }
  $('invert').addEventListener('change',e=>{cfg.portrait.invert=e.target.checked;historyChange();});
  $('font_size').addEventListener('input',e=>{cfg.theme.font_size=Number(e.target.value);$('font_size-display').textContent=e.target.value;historyChange();});
  $('auto_update').addEventListener('change',e=>{cfg.github.auto_update=e.target.checked;historyChange();});
  $('preset').addEventListener('change',e=>{const choice=PRESETS[e.target.value];if(!choice)return;Object.assign(cfg.theme,deep(choice.theme));Object.assign(cfg.layout,deep(choice.layout));Object.assign(cfg.portrait,deep(choice.portrait));historyChange({structural:true});refreshControls();e.target.value='';});
  $('add-section').addEventListener('click',()=>{if(cfg.sections.length>=24){setStatus('Limite de 24 seções','error');return;}cfg.sections.push({title:'Nova seção',rows:[{label:'Novo campo',value:'Seu conteúdo'}]});historyChange({structural:true});});
  $('light').addEventListener('change',render);$('refresh').addEventListener('click',render);
  $('save').addEventListener('click',save);$('stats').addEventListener('click',updateStats);
  $('download-dark').addEventListener('click',()=>exportSVG('dark'));$('download-light').addEventListener('click',()=>exportSVG('light'));$('download-portrait').addEventListener('click',exportPortrait);
  $('file').addEventListener('change',e=>{const file=e.target.files?.[0];if(file)upload(file);e.target.value='';});
  $('undo').addEventListener('click',()=>historyTravel('undo'));$('redo').addEventListener('click',()=>historyTravel('redo'));
  window.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey) && e.key.toLowerCase()==='z'){e.preventDefault();historyTravel(e.shiftKey?'redo':'undo');}else if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='y'){e.preventDefault();historyTravel('redo');}});
  initCropPointer();refreshControls();loadPhoto();updateUndo();render();
}
fetch('/api/config').then(async r=>{const data=await r.json();if(!r.ok)throw Error(data.error);return data;}).then(data=>{cfg=data;snapshot=JSON.stringify(cfg);init();}).catch(err=>setStatus('Falha ao abrir o projeto: '+err.message,'error'));
