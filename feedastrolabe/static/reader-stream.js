/* Progressive reader: cards survive detail navigation and filter-scoped mutations. */
(() => {
  'use strict';
  const list = document.querySelector('.article-list');
  const layout = document.querySelector('.reading-layout');
  if (!list || !layout) return;
  let loader = list.querySelector('[data-article-loader]');
  let loading = false, writing = false, generation = 0, detailVersion = 0;
  let listScroll = {x:scrollX,y:scrollY};
  const feedback = document.createElement('p'); feedback.className = 'sr-only'; feedback.setAttribute('role','status');
  document.querySelector('.reader-controls').after(feedback);
  const ids = () => new Set([...list.querySelectorAll('[data-article-id]')].map(node => node.dataset.articleId));
  function parse(html) { return new DOMParser().parseFromString(html,'text/html'); }
  function announce(text, error=false) {
    feedback.textContent=text;feedback.className=error?'notice error':'sr-only';feedback.setAttribute('role',error?'alert':'status');
  }
  function remember() {
    history.replaceState({...history.state,reader:true,x:scrollX,y:scrollY},'',location.href);
  }
  remember();
  function observe() {
    if (!loader) return;
    loader.querySelector('button').hidden=false;
    observer?.observe(loader);
  }
  const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
    if (entries.some(entry=>entry.isIntersecting)) void more();
  },{rootMargin:'0px 0px 300px 0px'}) : null;
  async function more() {
    if (!loader || loading || writing || loader.dataset.failed === 'true') return;
    loading=true;const version=generation;
    const current=loader, button=current.querySelector('button'), status=current.querySelector('[data-load-status]');
    button.disabled=true;status.textContent='読み込み中…';current.setAttribute('aria-busy','true');
    try {
      const response=await fetch(current.dataset.moreUrl,{headers:{Accept:'application/json'},signal:AbortSignal.timeout(15000)});
      if (!response.ok) throw new Error();
      const data=await response.json(); if(version!==generation)return;
      if(typeof data.html!=='string' || (data.next!==null && typeof data.next!=='string'))throw new Error();
      const doc=parse(data.html), known=ids(); let added=0;
      for (const card of doc.querySelectorAll('.article-card[data-article-id]')) {
        if(known.has(card.dataset.articleId))continue;
        card.querySelectorAll('script').forEach(node=>node.remove());
        list.insertBefore(card,current);known.add(card.dataset.articleId);added++;
      }
      if(data.next) {
        const next=new URL(data.next,location.href);
        if(next.origin!==location.origin || next.pathname!=='/articles/more')throw new Error();
        current.dataset.moreUrl=next.pathname+next.search;status.textContent='';
        observer?.unobserve(current);
      } else { observer?.unobserve(current);current.remove();loader=null; }
      announce(`${added} 件の記事を追加しました。`);
    } catch {
      if(version===generation) {
        current.dataset.failed='true';button.textContent='再読み込み';status.textContent='読み込めませんでした。';
        status.setAttribute('role','alert');
      }
    } finally {
      loading=false;button.disabled=false;current.removeAttribute('aria-busy');
      if(loader && loader.dataset.failed!=='true')observe();
    }
  }
  list.addEventListener('click',event=>{
    if(event.target.closest('[data-load-more]')) { delete loader.dataset.failed;void more(); }
  });
  observe();
  list.addEventListener('mousedown',event=>{
    if(event.button===1 && event.target.closest('.article-card') && !event.target.closest('.article-actions'))event.preventDefault();
  });
  list.addEventListener('auxclick',event=>{
    if(event.button!==1 || event.target.closest('.article-actions'))return;
    const card=event.target.closest('.article-card');
    if(!card)return;
    event.preventDefault();
    if(!card.dataset.originalUrl)return;
    const url=new URL(card.dataset.originalUrl,location.href);
    if(url.protocol==='https:' || url.protocol==='http:')window.open(url.href,'_blank','noopener,noreferrer');
  });
  function selected(url) {
    const id=new URL(url,location.href).searchParams.get('article');
    for(const card of list.querySelectorAll('.article-card'))card.classList.toggle('selected',card.dataset.articleId===id);
  }
  function apply(doc,url,scroll=true) {
    const fragment=doc.querySelector('[data-reader-fragment]');
    if(!fragment)throw new Error('本文を読み込めませんでした。');
    const detail=fragment.querySelector('.article-detail');
    layout.querySelector('.article-detail')?.remove();
    if(detail)layout.append(detail);
    layout.classList.toggle('has-detail',!!detail);selected(url);
    const counts=JSON.parse(fragment.dataset.counts);
    const badges=document.querySelectorAll('.sidebar nav[aria-label="記事の表示条件"] .count');
    ['total','unread','starred'].forEach((name,index)=>{if(badges[index])badges[index].textContent=counts[name];});
    document.querySelector('.view-heading .muted').textContent=`${fragment.dataset.total} 件の記事`;
    if(scroll) {
      if(detail) {detail.focus({preventScroll:true});}
      else window.scrollTo(listScroll.x,listScroll.y);
    }
    return fragment;
  }
  async function detail(url,push=true,position=null) {
    const version=++detailVersion;
    try {
      const response=await fetch(url,{headers:{'X-Reader-Detail':'1'},signal:AbortSignal.timeout(15000)});
      if(!response.ok)throw new Error();
      const doc=parse(await response.text());if(version!==detailVersion)return;
      if(push){remember();history.pushState({reader:true,x:scrollX,y:scrollY},'',url);}
      apply(doc,url,position===null);if(position)window.scrollTo(position.x||0,position.y||0);
      announce('');
    } catch { if(version===detailVersion)announce('本文を読み込めませんでした。もう一度選択してください。',true); }
  }
  document.addEventListener('click',event=>{
    const link=event.target.closest('a.article-title,.article-sequence a,.detail-top a');
    if(!link || event.button!==0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)return;
    const url=new URL(link.href);if(url.origin!==location.origin)return;
    event.preventDefault();if(link.matches('.article-title'))listScroll={x:scrollX,y:scrollY};
    void detail(url.href);
  });
  document.addEventListener('library-membership-changed',async()=>{
    generation++;const url=new URL(location.href);url.searchParams.delete('article');
    try{
      const response=await fetch(url,{headers:{'X-Reader-Detail':'1'}});
      if(!response.ok){location.assign('/');return;}
      const doc=parse(await response.text()),fragment=apply(doc,url.href,false);
      history.replaceState(history.state,'',url.href);
      observer?.disconnect();list.replaceChildren(...fragment.querySelector('[data-reconcile]').children);loader=null;
      const next=fragment.dataset.moreUrl;
      if(next){loader=document.createElement('div');loader.className='article-loader';loader.dataset.articleLoader='';loader.dataset.moreUrl=next;
        const button=document.createElement('button');button.type='button';button.dataset.loadMore='';button.textContent='さらに読み込む';
        const status=document.createElement('span');status.dataset.loadStatus='';status.setAttribute('role','status');loader.append(button,status);list.append(loader);observe();}
    }catch{announce('一覧を更新できませんでした。再読み込みしてください。',true);}
  });
  window.addEventListener('popstate',event=>{void detail(location.href,false,event.state||{x:0,y:0});});
  document.addEventListener('submit',async event=>{
    const form=event.target;
    const action=new URL(form.action,location.href);
    if(!/^\/articles\/(?:\d+\/(?:read|star|read-next|open)|read-all)$/.test(action.pathname))return;
    event.preventDefault();if(writing)return;
    writing=true;generation++;detailVersion++;
    for(const button of document.querySelectorAll('.article-card button,.article-detail button,.bulk-read-button')){
      if(!button.disabled){button.disabled=true;button.dataset.readerSaving='';}
    }
    const values=new URLSearchParams(new FormData(form));
    if(!(action.pathname.endsWith('/read-next') || action.pathname.endsWith('/open')))values.set('next',location.pathname+location.search);
    const match=action.pathname.match(/^\/articles\/(\d+)\//);
    const headers={'X-Reader-Detail':'1'};if(match)headers['X-Reader-Reconcile']=match[1];
    try {
      const response=await fetch(action.href,{method:'POST',body:values,headers,signal:AbortSignal.timeout(20000)});
      const doc=parse(await response.text());
      if(!response.ok || doc.querySelector('[data-flash=error]'))throw new Error();
      remember();history.pushState({reader:true,x:scrollX,y:scrollY},'',response.url);
      const fragment=apply(doc,response.url,(action.pathname.endsWith('/read-next') || action.pathname.endsWith('/open')));
      if(match) {
        const old=list.querySelector(`[data-article-id="${match[1]}"]`);
        const fresh=fragment.querySelector(`[data-reconcile] [data-article-id="${match[1]}"]`);
        if(fresh && old)old.replaceWith(fresh);else old?.remove();
      } else {
        for(const card of list.querySelectorAll('.article-card')) {
          if(fragment.dataset.view==='unread'){card.remove();continue;}
          card.classList.add('read');card.querySelector('.unread-dot')?.remove();
          const read=card.querySelector('form[action$="/read"]');
          if(read){read.querySelector('[name=value]').value='0';read.querySelector('button').textContent='未読に戻す';read.querySelector('button').setAttribute('aria-label','未読に戻す');}
        }
      }
      if(fragment.dataset.total==='0') {
        observer?.disconnect();loader?.remove();loader=null;
        if(!list.querySelector('.empty-state')){
          const empty=document.createElement('div');empty.className='empty-state';const h=document.createElement('h2');h.textContent='記事がありません';empty.append(h);list.append(empty);
        }
      }
      selected(response.url);announce('保存しました。');
    } catch { announce('保存を確認できませんでした。接続を確認して一覧を再読み込みしてください。',true); }
    finally {writing=false;document.querySelectorAll('[data-reader-saving]').forEach(button=>{button.disabled=false;delete button.dataset.readerSaving;});if(loader)observe();}
  });

  // Query current cards for each key action so appended and reconciled articles participate.
  document.addEventListener('keydown',event=>{
    const target=event.target;
    if(event.altKey || event.ctrlKey || event.metaKey || target.closest('input,textarea,select,button,a,summary,[contenteditable],dialog,[role="menu"]'))return;
    const cards=[...list.querySelectorAll('.article-card')];if(!cards.length)return;
    let index=cards.findIndex(card=>card.classList.contains('keyboard-focus'));
    if(index<0)index=Math.max(0,cards.findIndex(card=>card.classList.contains('selected')));
    let key=event.key.toLowerCase();
    if(key==='j' || key==='k' || key==='n'){
      event.preventDefault();
      if(key==='n'){
        const next=cards.findIndex((card,i)=>i>index && !card.classList.contains('read'));
        if(next<0)return;index=next;
      }else index=Math.max(0,Math.min(cards.length-1,index+(key==='j'?1:-1)));
      cards.forEach((card,i)=>card.classList.toggle('keyboard-focus',i===index));
      cards[index].scrollIntoView({block:'nearest'});
      if(key==='n')cards[index].querySelector('.article-title')?.click();
    }else if(key==='o' || key==='enter'){
      event.preventDefault();cards[index].querySelector('.article-title')?.click();
    }else if(key==='m' || key==='s'){
      event.preventDefault();cards[index].querySelector(key==='m'?'form[action$="/read"] button':'form[action$="/star"] button')?.click();
    }else if(key==='/'){
      event.preventDefault();document.querySelector('#search')?.focus();
    }
  });
})();
