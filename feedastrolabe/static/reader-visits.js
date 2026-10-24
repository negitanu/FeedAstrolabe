/* Actual detail visits are independent of read/star mutations. */
(() => {
  const layout=document.querySelector('.reading-layout');
  if(!layout)return;
  let previous=null;
  function record() {
    const form=layout.querySelector('[data-visit-form]');
    const id=form?.dataset.visitId||null;
    if(id===previous)return;
    previous=id;
    if(!form)return;
    fetch(form.action,{method:'POST',body:new URLSearchParams(new FormData(form)),
      headers:{'X-Reader-Visit':'1'},signal:AbortSignal.timeout(15000)})
      .then(response=>{if(!response.ok)throw new Error();})
      .catch(()=>{form.querySelector('[data-visit-status]').textContent='閲覧履歴を保存できませんでした。';});
  }
  new MutationObserver(record).observe(layout,{childList:true});
  record();
})();
