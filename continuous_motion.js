/* Presentation only. No fetch, provider calls, session-state writes or input interception. */
(() => {
 document.documentElement.dataset.studioMotion='loaded';
 const boot=()=>{
 document.documentElement.dataset.studioMotion='booting';
  window.synthetixStudio?.destroy();
  const root=document.querySelector('.canvas-story');
  if(!root)return;
  const abort=new AbortController(),signal=abort.signal;
  const reduce=matchMedia('(prefers-reduced-motion:reduce)'),wide=matchMedia('(min-width:1000px)'),fine=matchMedia('(hover:hover) and (pointer:fine)');
  const clamp=x=>Math.max(0,Math.min(1,x)),mix=(a,b,t)=>a+(b-a)*t;
  const ramp=(p,a,b)=>{const x=clamp((p-a)/(b-a));return x*x*(3-2*x);};
  const windowed=(p,a,b,c,d)=>ramp(p,a,b)*(1-ramp(p,c,d));
  const $=s=>root.querySelector(s),$$=s=>[...root.querySelectorAll(s)];
  const nodes={canvas:$('.becoming-canvas'),stack:$('.story-stack'),page:$('.morph-page'),title:$('.morph-title'),brief:$('.brief-lines'),fields:$$('[data-field]'),gallery:$('.morph-gallery'),images:$$('.story-images img'),guides:$('.construction-grid'),labels:$('.wireframe-labels'),focus:$('.blue-focus'),cursor:$('.demo-cursor'),evidence:$('.inspection-evidence'),repair:$('.repair-difference'),review:$('.review-strip'),landscape:$('.landscape-photo'),interior:$('.interiors-photo'),orbit:$('.style-orbit'),phase:$('.assembly-phase'),count:$('.sample-gallery-count'),heading:$('.canvas-project-label'),copies:$$('[data-scene]'),stages:$$('[data-stage]'),track:$('.track-marker'),ending:$('.story-ending h2')};
  const hero=document.querySelector('.studio-hero'),heroTitle=hero?.querySelector('h1'),heroDemo=document.querySelector('.st-key-studio-demo');
  let manual=false,geometry=null,frame=0,measureFrame=0,pointerFrame=0,replayFrame=0,replayStart=null,lastScene=-1,override=null,openAnimations=[],openingInterrupted=false,dead=false;
  let samples=0,totalWork=0,maxWork=0;
  let userCompare=50,pointerRect=null,pointerX=0,pointerY=0,lastProgress=0;
  const bounds=[0,.14,.43,.55,.65,.76,.84,.93,1.001];
  const workflow=[0,1,1,2,3,4,5,5];
  // This setting belongs only to the authored sample. It never edits a project brief.
  try{const choice=sessionStorage.getItem('synthetix-sample-direction');if(['editorial','grid','minimal'].includes(choice))selectStyle(choice,false);}catch{}
  function active(){return wide.matches&&!reduce.matches&&!manual;}
  function text(node,value){if(node.textContent!==value)node.textContent=value;}
  function clearMotion(){
    Object.values(nodes).flat().forEach(node=>{if(node?.style)node.removeAttribute('style');});
    $$('.story-layer').forEach(e=>e.removeAttribute('style'));
    if(heroTitle)heroTitle.removeAttribute('style');
    root.style.setProperty('--compare',userCompare+'%');
  }
  function measure(){
    if(dead||!root.isConnected)return;
    root.classList.toggle('story-enhanced',active());root.dataset.static=String(!active());
    const runway=$('.story-runway'),pin=$('.story-pin');
    const box=runway.getBoundingClientRect(),heroBox=hero?.getBoundingClientRect();
    const track=$('.story-track').getBoundingClientRect();
    geometry={start:box.top+scrollY-56,distance:Math.max(1,runway.offsetHeight-pin.offsetHeight-24),heroTop:(heroBox?.top||0)+scrollY,heroHeight:heroBox?.height||400,markers:nodes.stages.map(e=>{const r=e.getBoundingClientRect();return {x:r.left-track.left,w:r.width};}),width:nodes.page.clientWidth};
    if(!active())clearMotion();
    render();
  }
  function requestMeasure(){if(!measureFrame)measureFrame=requestAnimationFrame(()=>{measureFrame=0;measure();});}
  function sceneAt(p){return Math.max(0,bounds.findIndex((b,i)=>8>i&&p>=b&&bounds[i+1]>p));}
  function scene(p){
    const s=sceneAt(p);
    if(s!==lastScene){lastScene=s;root.dataset.current=s;nodes.copies.forEach((e,i)=>e.classList.toggle('active',i===s));nodes.stages.forEach((e,i)=>e.classList.toggle('current',i===workflow[s]));
      const m=geometry?.markers[workflow[s]];if(m){nodes.track.style.transform=`translateX(${m.x}px)`;nodes.track.style.width=m.w+'px';}}
    return s;
  }
  function render(forced){
    if(dead||!geometry)return;
    const workStart=performance.now();
    const p=forced??override??clamp((scrollY-geometry.start)/geometry.distance);lastProgress=p;
    const s=scene(p);
    if(!active())return;
    root.style.setProperty('--chapter-shift',(s===1?18*(1-ramp(p,.25,.4)):0)+'px');
    const plan=ramp(p,0,.08),structure=ramp(p,.14,.23),identity=ramp(p,.25,.33),complete=ramp(p,.35,.4),explore=windowed(p,.43,.46,.51,.55),test=windowed(p,.55,.58,.635,.65),repair=windowed(p,.65,.68,.745,.77),retest=windowed(p,.76,.79,.825,.845),review=ramp(p,.84,.9),invite=ramp(p,.93,.985);
    // Each property has a single timeline owner; pointer depth affects only hero backing sheets.
    nodes.canvas.style.transform=`perspective(1600px) rotateY(${mix(-7,0,structure)}deg) rotateZ(${mix(2,0,plan)}deg)`;
    nodes.stack.style.transform=`translateX(${mix(35,-15,structure)+explore*30-invite*50}px) scale(${.92+.08*complete+.045*invite})`;
    $$('.story-layer').forEach((e,i)=>{e.style.transform=`translate(${(i?-14:16)*(1-complete)}px,${(-22-i*12)*(1-plan)-repair*(i?20:0)}px) rotate(${(i?-3:3)*(1-plan)}deg)`;});
    nodes.title.style.transform=`translate(${mix(0,-3,plan)}px,${mix(14,0,structure)}px) scale(${mix(.9,1,identity)})`;
    nodes.brief.style.opacity=1-ramp(p,.15,.22);nodes.brief.style.transform=`translateX(${-85*structure}px) scale(${1-.12*structure})`;
    nodes.fields.forEach((e,i)=>{const a=ramp(p,i*.012,.035+i*.012);e.style.transform=`translate(${(1-a)*30}px,${(1-a)*(20+i*8)}px)`;e.style.opacity=.25+.75*a;});
    nodes.gallery.style.opacity=structure;nodes.gallery.style.transform=`translateY(${65*(1-structure)}px) scaleY(${.55+.45*structure})`;
    nodes.images.forEach((e,i)=>{e.style.clipPath=`inset(${100*(1-ramp(p,.26+i*.025,.32+i*.025))}% 0 0 0)`;});
    nodes.guides.style.opacity=structure*(1-complete);nodes.labels.style.opacity=structure*(1-identity);
    nodes.orbit.style.transform=`translateX(${Math.sin(explore*Math.PI)*-42}px) scale(${.92+.08*explore})`;
    const click=windowed(p,.565,.59,.62,.64)+windowed(p,.772,.795,.82,.835);
    const cursorTravel=s===5?ramp(p,.762,.79):ramp(p,.55,.59);
    nodes.cursor.style.opacity=Math.max(test,retest);nodes.cursor.style.transform=`translate(${mix(geometry.width*.68,110,cursorTravel)}px,${mix(380,207,cursorTravel)}px) scale(${1-.15*clamp(click)})`;
    nodes.focus.style.transform=`translate(${mix(0,95,ramp(p,.47,.55))}px,${mix(-90,12,ramp(p,.47,.55))}px)`;nodes.focus.style.opacity=1-invite;
    $('.filter-target').style.boxShadow=click>.6?'inset 0 0 0 2px #3555E8':'none';
    nodes.evidence.style.opacity=Math.max(test,retest);nodes.evidence.style.transform=`translateX(${(1-Math.max(test,retest))*90}px)`;
    nodes.repair.style.opacity=repair;nodes.repair.style.transform=`translateX(${(1-repair)*90}px) scaleX(${.75+.25*repair})`;nodes.repair.style.clipPath=`inset(0 ${(1-repair)*80}% 0 0)`;
    nodes.review.style.opacity=review;nodes.review.style.transform=`translateY(${(1-review)*22}px)`;
    const fixed=ramp(p,.788,.81);nodes.landscape.style.opacity=1-fixed;nodes.landscape.style.transform=`scaleX(${1-fixed*.9})`;nodes.interior.style.transform=`translateX(${-fixed*25}%)`;
    const compare=s===6?userCompare:50;root.style.setProperty('--compare',compare+'%');
    if(s===6){nodes.repair.style.opacity=1-ramp(p,.90,.93);nodes.repair.style.transform=`translateY(${review*-6}px)`;nodes.repair.style.clipPath=`inset(0 0 0 0)`;}
    text(nodes.phase,p<.14?'Idea → Brief':p<.25?'01 / Structure':p<.35?'02 / Identity':p<.43?'03 / Website':p<.55?'Visual direction':p<.65?'Simulated check':p<.76?'Repair / 1 of 3':p<.84?'Same check again':p<.93?'Review the difference':'YOUR NEXT PROJECT');
    text(nodes.count,fixed>.9?'Interiors / 1 photograph · simulated outcome':'Selected work / 2 photographs');
    text(nodes.heading,invite>.8?'YOUR IDEA NEXT':'MIRA LANE');
    const h=clamp((scrollY-geometry.heroTop)/(geometry.heroHeight+250));
    if(heroTitle){heroTitle.style.setProperty('--hero-lift',(-45*h)+'px');heroTitle.style.setProperty('--hero-scale',1+.045*h);heroTitle.style.setProperty('--hero-clip',h*16+'%');}
    const end=clamp((scrollY-(geometry.start+geometry.distance))/(innerHeight*.65));
    samples++;const work=performance.now()-workStart;totalWork+=work;maxWork=Math.max(maxWork,work);
    root.dataset.motionSamples=samples;root.dataset.motionWorkMean=(totalWork/samples).toFixed(2);root.dataset.motionWorkMax=maxWork.toFixed(2);
    nodes.ending.style.transform=`translateY(${35*(1-end)}px)`;nodes.ending.style.clipPath=`inset(0 0 ${20*(1-end)}% 0)`;
  }
  function stopReplay(announce=false){if(replayFrame)cancelAnimationFrame(replayFrame);replayFrame=0;replayStart=null;override=null;const btn=$('[data-story-replay]');btn.textContent='▶ Replay demonstration';if(announce)$('.replay-status').textContent='Demonstration stopped. Scroll to continue.';}
  function replay(now){
    if(replayStart===null)replayStart=now;
    const x=clamp((now-replayStart)/8500);override=mix(.55,.845,x);render(override);
    if(1>x)replayFrame=requestAnimationFrame(replay);else{replayFrame=0;$('[data-story-replay]').textContent='▶ Replay demonstration';$('.replay-status').textContent='Simulated outcome: same Interiors check, one photograph. Other behavior untested.';}
  }
  function selectStyle(choice,animate=true){
    if(!['editorial','grid','minimal'].includes(choice))return;
    root.dataset.storyStyle=choice;$$('[data-story-choice]').forEach(e=>e.setAttribute('aria-pressed',String(e.dataset.storyChoice===choice)));
    const index=['editorial','grid','minimal'].indexOf(choice);$('.style-traveller').style.transform=`translateX(calc(${index} * (100% + 12px)))`;
    try{sessionStorage.setItem('synthetix-sample-direction',choice);}catch{}
    if(animate&&!reduce.matches&&!manual)nodes.page.animate([{clipPath:'inset(0 2% 0 2%)',transform:'scale(.985)'},{clipPath:'inset(0 0 0 0)',transform:'scale(1)'}],{duration:240,easing:'ease-out'});
  }
  root.addEventListener('click',e=>{
    const style=e.target.closest('[data-story-choice]');if(style){selectStyle(style.dataset.storyChoice);return;}
    const toggle=e.target.closest('[data-story-motion]');if(toggle){manual=!manual;stopReplay();toggle.setAttribute('aria-pressed',String(manual));toggle.textContent=manual?'Enable scroll animation':'Read without animation';measure();return;}
    if(e.target.closest('[data-story-replay]')){if(replayFrame){stopReplay(true);render();return;}if(!active()){$('.replay-status').textContent='Simulated demonstration: missing listener → targeted repair → same Interiors check, one photograph. No animation in static mode.';return;}$('.replay-status').textContent='Simulated demonstration playing. Scroll or select Stop to interrupt.';$('[data-story-replay]').textContent='■ Stop demonstration';replayStart=null;replayFrame=requestAnimationFrame(replay);}
  },{signal});
  root.addEventListener('input',e=>{if(e.target.matches('[data-story-divider]')){stopReplay();userCompare=Number(e.target.value);override=.875;render(override);root.style.setProperty('--compare',userCompare+'%');}},{signal});
  function interruptOpening(){if(openingInterrupted)return;openingInterrupted=true;openAnimations.forEach(a=>{try{a.finish();}catch{a.cancel();}});}
  window.addEventListener('scroll',()=>{interruptOpening();if(replayFrame||override!==null){stopReplay();}if(!frame)frame=requestAnimationFrame(()=>{frame=0;render();});},{passive:true,signal});
  window.addEventListener('resize',requestMeasure,{signal});wide.addEventListener('change',requestMeasure,{signal});reduce.addEventListener('change',()=>{stopReplay();interruptOpening();requestMeasure();},{signal});
  if(heroDemo){
    heroDemo.addEventListener('pointerenter',()=>{interruptOpening();pointerRect=heroDemo.getBoundingClientRect();},{signal});
    heroDemo.addEventListener('pointermove',e=>{if(!fine.matches||reduce.matches||manual||!pointerRect)return;pointerX=clamp((e.clientX-pointerRect.left)/pointerRect.width)*2-1;pointerY=clamp((e.clientY-pointerRect.top)/pointerRect.height)*2-1;if(!pointerFrame)pointerFrame=requestAnimationFrame(()=>{pointerFrame=0;heroDemo.querySelectorAll('.hero-planes i').forEach((n,i)=>{n.style.transform=`translate(${pointerX*(i?9:5)}px,${-14+pointerY*(i?7:4)}px) rotate(${pointerX*(i?3:-2)}deg)`;});});},{passive:true,signal});
    heroDemo.addEventListener('pointerleave',()=>{heroDemo.querySelectorAll('.hero-planes i').forEach(e=>e.removeAttribute('style'));},{signal});
  }
  // One opening per document; reruns never replay the welcome choreography.
  if(!window.synthetixStudioOpened&&!reduce.matches){window.synthetixStudioOpened=true;hero?.querySelectorAll('.hero-mask>*').forEach((e,i)=>{openAnimations.push(e.animate([{transform:'translateY(105%) rotate(2deg)'},{transform:'translateY(0) rotate(0)'}],{duration:1050,delay:i*130,easing:'cubic-bezier(.2,.7,.2,1)',fill:'backwards'}));});heroDemo?.querySelectorAll('.hero-planes i').forEach((e,i)=>openAnimations.push(e.animate([{transform:`translate(${i?35:-35}px,-45px) rotate(${i?6:-6}deg)`},{transform:`translate(${i?14:-14}px,${i?-23:-14}px) rotate(${i?2:-2}deg)`}],{duration:1100,delay:i*70,easing:'ease-out'})));}
  const mutations=new MutationObserver(()=>{if(!root.isConnected && window.synthetixStudio?.root===root)window.synthetixStudio.destroy();});mutations.observe(document.querySelector('[data-testid="stMain"]'),{childList:true,subtree:true});
  const resize=new ResizeObserver(requestMeasure);resize.observe(document.querySelector('[data-testid="stMain"]'));
  document.fonts?.ready.then(()=>{if(!dead)requestMeasure();});
  window.synthetixStudio={root,destroy(){dead=true;abort.abort();mutations.disconnect();resize.disconnect();[frame,measureFrame,pointerFrame,replayFrame].forEach(cancelAnimationFrame);openAnimations.forEach(a=>a.cancel());clearMotion();root.classList.remove('story-enhanced');}};
  measure();
 document.documentElement.dataset.studioMotion='ready';
 };
 if(document.querySelector('.canvas-story'))boot();
 else {const waiting=new MutationObserver(()=>{if(document.querySelector('.canvas-story')){waiting.disconnect();boot();}});waiting.observe(document.body,{childList:true,subtree:true});}
})();
