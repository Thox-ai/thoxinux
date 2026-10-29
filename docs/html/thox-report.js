'use strict';
// No remote services, trackers, storage or credentials are used by these templates.
const themeButton=document.querySelector('[data-theme-toggle]');
if(themeButton) themeButton.addEventListener('click',()=>{
  const dark=document.documentElement.dataset.theme!=='dark';
  document.documentElement.dataset.theme=dark?'dark':'light';
  themeButton.setAttribute('aria-pressed',String(dark));
  themeButton.textContent=dark?'Light view':'Dark view';
});
document.querySelector('[data-print]')?.addEventListener('click',()=>window.print());
const slides=Array.from(document.querySelectorAll('[data-slide]'));
if(slides.length){let active=0;const prev=document.querySelector('[data-prev]');const next=document.querySelector('[data-next]');const count=document.querySelector('[data-slide-count]');
  function show(i){active=Math.max(0,Math.min(slides.length-1,i));slides.forEach((s,n)=>s.hidden=n!==active);count.textContent=`Slide ${active+1} of ${slides.length}`;prev.disabled=active===0;next.disabled=active===slides.length-1;}
  prev.addEventListener('click',()=>show(active-1));next.addEventListener('click',()=>show(active+1));
  document.addEventListener('keydown',e=>{if(e.altKey||e.ctrlKey||e.metaKey||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)||e.target.isContentEditable)return;if(e.key==='ArrowRight'){e.preventDefault();show(active+1);}if(e.key==='ArrowLeft'){e.preventDefault();show(active-1);}});show(0);
}
