/* Sidebar width is local; folder membership and feed order are shared. */
(() => {
  'use strict';
  const shell=document.querySelector('.app-shell'), list=document.querySelector('[data-folder-order]');
  if(!shell || !list)return;
  const separator=document.querySelector('[data-sidebar-resizer]'), widthKey='feedastrolabe.sidebar-width.v1';
  let width=248, resize=null;
  try{const saved=JSON.parse(localStorage.getItem(widthKey));if(saved?.version===1 && Number.isFinite(saved.width))width=saved.width;}catch{}
  function applyWidth(value,persist=false){
    const max=Math.max(200,Math.min(480,innerWidth-360));width=Math.round(Math.max(200,Math.min(max,value)));
    shell.style.setProperty('--sidebar-width',`${width}px`);
    separator.setAttribute('aria-valuemin','200');separator.setAttribute('aria-valuemax',String(max));separator.setAttribute('aria-valuenow',String(width));
    separator.hidden=innerWidth<=700;
    if(persist)try{localStorage.setItem(widthKey,JSON.stringify({version:1,width}));}catch{}
  }
  applyWidth(width);window.addEventListener('resize',()=>applyWidth(width));
  separator.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();resize={id:event.pointerId,start:width,x:event.clientX};separator.setPointerCapture(event.pointerId);});
  separator.addEventListener('pointermove',event=>{if(resize?.id===event.pointerId)applyWidth(resize.start+event.clientX-resize.x);});
  separator.addEventListener('pointerup',()=>{if(resize){resize=null;applyWidth(width,true);}});
  separator.addEventListener('pointercancel',()=>{if(resize){applyWidth(resize.start);resize=null;}});
  separator.addEventListener('keydown',event=>{
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();
    applyWidth(event.key==='Home'?200:event.key==='End'?480:width+(event.key==='ArrowLeft'?-16:16),true);
  });
  const groups=()=>[...list.children].filter(node=>node.matches('.feed-folder'));
  const rows=group=>[...group.querySelector('.feed-folder-content').children].filter(node=>node.matches('.feed-row'));
  const status=list.parentElement.querySelector('[data-order-status]');let drag=null,saving=false,frame=0;
  function announce(text,error=false){status.textContent=text;status.className=error?'folder-order-status notice error':'folder-order-status sr-only';status.setAttribute('role',error?'alert':'status');}
  const snapshot=()=>new Map(groups().map(group=>[group,rows(group)]));
  function restore(original){for(const [group,items] of original)for(const row of items)group.querySelector('.feed-folder-content').append(row);}
  async function save(row,original,source){
    const group=row.closest('.feed-folder'), destination=group.dataset.folder, position=rows(group).indexOf(row)+1;
    if(destination===source && original.get(group).indexOf(row)===position-1)return;
    saving=true;list.classList.add('order-saving');list.setAttribute('aria-busy','true');announce('表示順を保存中…');
    try{
      const response=await fetch(`/feeds/${row.dataset.feedId}/order`,{method:'POST',headers:{Accept:'application/json'},
        body:new URLSearchParams({csrf:list.dataset.csrf,source,folder:destination,position:String(position)}),signal:AbortSignal.timeout(15000)});
      const result=await response.json();if(!response.ok || !Array.isArray(result.groups))throw new Error();
      const known=new Map([...list.querySelectorAll('.feed-row')].map(item=>[Number(item.dataset.feedId),item]));
      const existing=new Map(groups().map(item=>[item.dataset.folder,item]));
      for(const saved of result.groups){
        const folder=existing.get(saved.folder);if(!folder)continue;
        for(const id of saved.feeds)if(known.has(id))folder.querySelector('.feed-folder-content').append(known.get(id));
        const counts=folder.querySelector('.feed-folder-counts');counts.replaceChildren();
        if(saved.unread){const count=document.createElement('span');count.className='count';count.textContent=saved.unread;count.setAttribute('aria-label',`未読 ${saved.unread} 件`);counts.append(count);}
      }
      for(const [name,folder] of existing)if(!result.groups.some(item=>item.folder===name))folder.remove();
      announce(`${row.dataset.contextLabel} を ${position} 番目に移動しました。`);
      if(source!==destination)document.dispatchEvent(new CustomEvent('library-membership-changed'));
    }catch{restore(original);announce('移動の保存を確認できませんでした。再読み込みして確認してください。',true);}
    finally{saving=false;list.classList.remove('order-saving');list.removeAttribute('aria-busy');row.querySelector('[data-feed-drag]')?.focus({preventScroll:true});}
  }
  function reorder(y){
    const folder=groups().find(group=>{const box=group.getBoundingClientRect();return y>=box.top && y<=box.bottom;});
    if(!folder)return;
    const children=rows(folder).filter(row=>row!==drag.row);
    const next=folder.open?children.find(row=>{const box=row.getBoundingClientRect();return y<box.top+box.height/2;}):null;
    drag.targetGroup=folder;drag.next=next;
    list.querySelectorAll('.feed-insert-before,.feed-insert-end').forEach(node=>node.classList.remove('feed-insert-before','feed-insert-end'));
    if(next)next.classList.add('feed-insert-before');else folder.querySelector('.feed-folder-content').classList.add('feed-insert-end');
    // A collapsed target remains collapsed, even while accepting the drop.
    groups().forEach(item=>item.classList.toggle('feed-drop-target',item===folder));
  }
  function autoscroll(){if(!drag?.active)return;const delta=drag.y<90?-12:drag.y>innerHeight-55?12:0;if(delta){window.scrollBy(0,delta);reorder(drag.y);}frame=requestAnimationFrame(autoscroll);}
  function finish(cancelled){
    if(!drag)return;const current=drag;drag=null;cancelAnimationFrame(frame);
    list.querySelectorAll('.feed-insert-before,.feed-insert-end').forEach(node=>node.classList.remove('feed-insert-before','feed-insert-end'));
    if(!cancelled && current.active && current.targetGroup)current.targetGroup.querySelector('.feed-folder-content').insertBefore(current.row,current.next||null);
    list.classList.remove('is-sorting');current.row.classList.remove('is-dragging');groups().forEach(group=>group.classList.remove('feed-drop-target'));
    if(list.hasPointerCapture(current.id))list.releasePointerCapture(current.id);
    if(cancelled){restore(current.original);announce('並べ替えを取り消しました。');}
    else if(current.active)void save(current.row,current.original,current.source);
  }
  for(const handle of list.querySelectorAll('[data-feed-drag]')){
    handle.hidden=false;
    handle.setAttribute('aria-description','ドラッグ、または上下矢印キーで移動。Escapeで取り消し。');
    handle.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();});
    handle.addEventListener('pointerdown',event=>{
      if(saving || drag || list.classList.contains('order-saving') || event.button!==0 || !event.isPrimary)return;
      event.preventDefault();event.stopPropagation();handle.focus({preventScroll:true});
      const row=handle.closest('.feed-row');drag={row,id:event.pointerId,startY:event.clientY,y:event.clientY,source:row.closest('.feed-folder').dataset.folder,original:snapshot(),active:false};list.setPointerCapture(event.pointerId);
    });
    handle.addEventListener('keydown',event=>{
      if(!['ArrowUp','ArrowDown','Home','End'].includes(event.key))return;event.preventDefault();if(saving||drag||list.classList.contains('order-saving'))return;
      const row=handle.closest('.feed-row'),group=row.closest('.feed-folder'),current=rows(group),index=current.indexOf(row),original=snapshot();
      const target=event.key==='Home'?0:event.key==='End'?current.length-1:Math.max(0,Math.min(current.length-1,index+(event.key==='ArrowUp'?-1:1)));
      if(target!==index){group.querySelector('.feed-folder-content').insertBefore(row,target<index?current[target]:current[target].nextSibling);void save(row,original,group.dataset.folder);}
    });
  }
  list.addEventListener('pointermove',event=>{if(!drag || drag.id!==event.pointerId)return;drag.y=event.clientY;
    if(!drag.active && Math.abs(drag.y-drag.startY)>=6){drag.active=true;drag.row.classList.add('is-dragging');list.classList.add('is-sorting');frame=requestAnimationFrame(autoscroll);}
    if(drag.active){event.preventDefault();reorder(drag.y);}
  });
  list.addEventListener('pointerup',()=>finish(false));list.addEventListener('pointercancel',()=>finish(true));list.addEventListener('lostpointercapture',()=>finish(true));
  document.addEventListener('keydown',event=>{if(event.key==='Escape' && drag){event.preventDefault();finish(true);}});
})();
