'use strict';
let catalog=[],liked=new Set(),feed=[],view='recommendations',user='demo',engine='c',busy=false,category='all',cold=true;
const $=id=>document.getElementById(id);
const labels={outdoors:'Out of office',design:'Dream spaces',food:'Something delicious',art:'Creative energy',photography:'Places to go',learning:'Stay curious'};
const creators={outdoors:'The outdoor edit',design:'Spaces worth saving',food:'The everyday kitchen',art:'Creative studio',photography:'A different perspective',learning:'The curious collection'};
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
async function api(path,options){const response=await fetch(path,options);const data=await response.json();if(!response.ok)throw new Error(data.error||`Request failed: ${response.status}`);return data;}
function orderedItems(){
  if(view==='saved')return catalog.filter(i=>liked.has(i.id));
  if(view==='explore'||cold){
    // Interleave categories so the discovery grid has a varied visual rhythm.
    return [...catalog].sort((a,b)=>((a.id-1)%8)-((b.id-1)%8)||a.id-b.id);
  }
  return feed;
}
function saveButton(item){const b=el('button',liked.has(item.id)?'Saved':'Save',`save ${liked.has(item.id)?'liked':''}`);b.disabled=busy;b.setAttribute('aria-label',`${liked.has(item.id)?'Unsave':'Save'} ${item.title}`);b.setAttribute('aria-pressed',liked.has(item.id));b.onclick=()=>toggle(item.id);return b;}
function openDetail(item){
  const content=$('detail-content');content.replaceChildren();const grid=el('div',undefined,'detail-grid');
  if(item.image){const image=el('img');image.src=item.image;image.alt=item.title;grid.append(image);}
  const body=el('div',undefined,'detail-body');body.append(el('div',labels[item.category],'eyebrow'),el('h2',item.title),el('p',item.description),el('div',item.tags.join(' · '),'detail-tags'));
  if(item.reasons&&item.score!==null)body.append(el('p',`Recommended because you saved ideas about ${item.reasons.join(', ')||'related interests'}. Tag similarity: ${item.score.toFixed(3)}.`));
  body.append(saveButton(item));grid.append(body);content.append(grid);if(!$('detail').open)$('detail').showModal();
}
function render(){
  const search=$('search').value.toLowerCase().trim();let items=orderedItems().filter(i=>category==='all'||i.category===category);
  if(search)items=items.filter(i=>`${i.title} ${i.description} ${i.tags.join(' ')} ${i.category}`.toLowerCase().includes(search));
  $('title').textContent=search?`A little more ${$('search').value.trim()}.`:view==='saved'?'Your kind of inspiration.':category!=='all'?labels[category]+'.':'Good ideas start here.';
  $('context').textContent=view==='saved'?'All the ideas you want to come back to.':search?`${items.length} ideas to get you inspired.`:'Find something you love. Save it. Make it yours.';
  for(const id of ['recommendations','explore','saved'])$(id).classList.toggle('selected',id===view);
  for(const b of $('categories').querySelectorAll('button'))b.classList.toggle('active',b.dataset.category===category);
  $('saved-count').textContent=liked.size;$('likes').textContent=`${liked.size} saved ${liked.size===1?'idea':'ideas'}`;
  const grid=$('grid');grid.replaceChildren();if(!items.length)grid.append(el('div','Nothing here yet. Try another search or save a few ideas from Explore.','empty'));
  for(const item of items){
    const card=el('article',undefined,'card'),media=el('div',undefined,'pin-image');
    const opener=el('button',undefined,'open-pin');opener.setAttribute('aria-label',`Open ${item.title}`);opener.onclick=()=>openDetail(item);
    const image=el('img');image.src=item.image||'/images/design-0.jpg';image.alt=item.title;image.loading='lazy';image.style.setProperty('--ratio',[.77,1.02,.67,.86,1.16][item.id%5]);opener.append(image);media.append(opener,saveButton(item),el('span',labels[item.category],'pin-category'));card.append(media);
    const body=el('div',undefined,'pin-content'),line=el('div',undefined,'pin-title');line.append(el('h2',item.title));
    const more=el('button','···','more');more.setAttribute('aria-label',`Details for ${item.title}`);more.onclick=()=>openDetail(item);line.append(more);body.append(line);
    const byline=el('div',undefined,'pin-byline');byline.append(el('span',creators[item.category][0],'tiny-avatar'),el('span',creators[item.category]));body.append(byline);
    if(!cold&&view==='recommendations'&&item.reasons?.length)body.append(el('div',`Inspired by your interest in ${item.reasons.slice(0,2).join(' & ')}`,'reason'));
    card.append(body);grid.append(card);
  }
}
async function refresh(){
  const [items,recs]=await Promise.all([api(`/api/items?user=${encodeURIComponent(user)}`),api(`/api/recommendations?user=${encodeURIComponent(user)}&k=50&engine=${engine}`)]);
  catalog=items.items;liked=new Set(recs.liked_ids);feed=recs.results;cold=recs.mode==='cold_start';$('mode').textContent=cold?'A fresh start, just for you':'Picked around your interests';$('timing').textContent=`${recs.pipeline_ms} ms pipeline`;render();
}
async function toggle(id){
  if(busy)return;busy=true;$('error').textContent='';render();
  try{await api('/api/likes',{method:liked.has(id)?'DELETE':'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({user,item:String(id)})});await refresh();if($('detail').open){const item=feed.find(i=>i.id===id)||catalog.find(i=>i.id===id);if(item)openDetail(item);}}
  catch(error){$('error').textContent=error.message;}
  finally{busy=false;render();if($('detail').open){for(const b of $('detail').querySelectorAll('button'))b.disabled=false;}}
}
$('load').onclick=async()=>{
  if(busy)return;const next=$('user').value.trim();if(!/^[A-Za-z0-9_-]{1,40}$/.test(next)){$('error').textContent='Use 1–40 letters, numbers, underscores or hyphens.';return;}
  busy=true;const old=user,oldEngine=engine;user=next;engine=$('engine').value;$('error').textContent='';
  try{await refresh();$('profile-settings').hidden=true;$('profile-button').textContent=user[0].toUpperCase();}catch(error){user=old;engine=oldEngine;$('error').textContent=error.message;}finally{busy=false;render();}
};
for(const id of ['recommendations','explore','saved'])$(id).onclick=()=>{view=id;render();};
for(const b of $('categories').querySelectorAll('button'))b.onclick=()=>{category=b.dataset.category;render();};
$('search').oninput=render;$('profile-button').onclick=()=>{$('profile-settings').hidden=!$('profile-settings').hidden;};$('close-detail').onclick=()=>$('detail').close();
document.addEventListener('keydown',event=>{if(event.key==='/'&&!['INPUT','TEXTAREA'].includes(document.activeElement.tagName)){event.preventDefault();$('search').focus();}});
refresh().catch(error=>{$('error').textContent=error.message;});
