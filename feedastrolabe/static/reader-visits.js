/* A displayed detail records its visit and read state with a CSRF-protected POST. */
(() => {
  const layout=document.querySelector('.reading-layout');
  if(!layout)return;
  let previous=null, failedForm=null;
  function markRead(root) {
    root.classList.add('read');
    root.querySelector('.unread-dot')?.remove();
    const form=root.querySelector('form[action$="/read"]');
    if(!form)return;
    form.querySelector('[name=value]').value='0';
    const button=form.querySelector('button');
    button.textContent='未読に戻す';
    button.setAttribute('aria-label','未読に戻す');
    button.title='未読に戻す';
  }
  function record() {
    const form=layout.querySelector('.article-detail:not([inert]) [data-visit-form]');
    const id=form?.dataset.visitId||null;
    if(id===previous && (!failedForm || form===failedForm))return;
    previous=id;failedForm=null;
    if(!form)return;
    fetch(form.action,{method:'POST',body:new URLSearchParams(new FormData(form)),
      headers:{'X-Reader-Visit':'1','X-Reader-State':'1'},signal:AbortSignal.timeout(15000)})
      .then(async response=>{
        if(!response.ok)throw new Error();
        const data=await response.json();
        const card=layout.querySelector(`.article-card[data-article-id="${id}"]`);
        if(card)markRead(card);
        if(!form.isConnected || form.closest('[inert]'))return;
        markRead(form.closest('.article-detail'));
        const badges=document.querySelectorAll('.sidebar nav[aria-label="記事の表示条件"] .count');
        ['total','unread','starred','history'].forEach((name,index)=>{if(badges[index])badges[index].textContent=data.counts[name];});
        document.querySelector('.view-heading .muted').textContent=`${data.total} 件の記事`;
      })
      .catch(()=>{failedForm=form;form.querySelector('[data-visit-status]').textContent='既読・閲覧履歴を保存できませんでした。記事を選び直して再試行してください。';});
  }
  new MutationObserver(record).observe(layout,{childList:true,attributes:true,attributeFilter:['inert'],subtree:true});
  record();
})();
