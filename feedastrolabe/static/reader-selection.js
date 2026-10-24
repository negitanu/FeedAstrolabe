/* Selection follows article identities across appends and card reconciliation. */
(() => {
  const list=document.querySelector('.article-list');
  const form=document.querySelector('#reader-selection-form');
  if(!list || !form)return;
  const selected=new Set();
  const count=form.querySelector('[data-selection-count]');
  const submit=form.querySelector('[type=submit]');
  function reconcile() {
    const boxes=[...list.querySelectorAll('[data-select-article]')];
    const visible=new Set(boxes.map(box=>box.value));
    for(const id of selected)if(!visible.has(id))selected.delete(id);
    for(const box of boxes)box.checked=selected.has(box.value);
    count.textContent=`${selected.size} 件を選択`;
    submit.disabled=selected.size===0;
    form.hidden=selected.size===0;
  }
  list.addEventListener('change',event=>{
    const box=event.target.closest('[data-select-article]');
    if(!box)return;
    if(box.checked && selected.size>=100){box.checked=false;count.textContent='一度に選択できるのは100件までです。';return;}
    if(box.checked)selected.add(box.value);else selected.delete(box.value);
    reconcile();
  });
  form.querySelector('[data-select-loaded]').hidden=false;
  form.querySelector('[data-clear-selection]').hidden=false;
  form.querySelector('[data-select-loaded]').addEventListener('click',()=>{
    for(const box of list.querySelectorAll('[data-select-article]')){
      if(selected.size>=100)break;
      selected.add(box.value);
    }
    reconcile();
  });
  form.querySelector('[data-clear-selection]').addEventListener('click',()=>{selected.clear();reconcile();});
  new MutationObserver(reconcile).observe(list,{childList:true,subtree:true});
  document.addEventListener('reader-reconciled',reconcile);
  reconcile();
})();
