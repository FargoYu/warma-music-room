const audio=document.querySelector('#audio'), stage=document.querySelector('#stage'), seek=document.querySelector('#seek');
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
const uiNodes=new Map();
const $=s=>{if(!uiNodes.has(s))uiNodes.set(s,document.querySelector(s));return uiNodes.get(s)};
const sceneNodes=new Map();
function sceneNode(selector){if(!sceneNodes.has(selector))sceneNodes.set(selector,stage.querySelector(selector));return sceneNodes.get(selector)}
function setText(node,value){if(node&&node.textContent!==value)node.textContent=value}
 let tracks=[], index=0, favorites=readFavorites();
const format=t=>Number.isFinite(t)?`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`:'0:00';
let renderedIndex=-1, renderedTime=NaN, renderedReduced=null;
function tick(){
 const time=audio.currentTime;
 if(index!==renderedIndex||time!==renderedTime||reducedMotion.matches!==renderedReduced){
  renderedIndex=index;renderedTime=time;renderedReduced=reducedMotion.matches;
  updateFirstFrame();updateSecondFrame();updateThirdFrame();updateFourthFrame();updateFifthFrame();updateRemainingFrame();
 }
}
const frameScheduler=createFrameScheduler(audio,tick);
function renderList(){for(const nav of [$('#track-list'),$('#mobile-tracks')]){if(nav.children.length===tracks.length){[...nav.children].forEach((b,i)=>{const active=i===index;b.classList.toggle('active',active);b.setAttribute('aria-current',String(active));b.lastChild.textContent=active?'♪':''});continue;}tracks.forEach((t,i)=>{const b=document.createElement('button');b.className='track'+(i===index?' active':'');b.setAttribute('aria-current',i===index?'true':'false');const n=document.createElement('span');n.className='number';n.textContent=String(i+1).padStart(2,'0');const title=document.createElement('span');title.className='track-title';title.textContent=t.title;const mark=document.createElement('span');mark.className='playing-indicator';mark.textContent=i===index?'♪':'';b.append(n,title,mark);b.addEventListener('click',()=>select(i,true));nav.append(b)})}}
function mountScene(i,autoplay=false){sceneNodes.clear();for(const a of [...firstAnimations,...secondAnimations,...thirdAnimations,...fourthAnimations,...fifthAnimations,...remainingAnimations])a.cancel();if(eighthController){eighthController.destroy();eighthController=null}if(fourthController){fourthController.destroy();fourthController=null}renderedIndex=-1;index=(i+tracks.length)%tracks.length;const t=tracks[index];stage.replaceChildren();firstAnimations=[];secondAnimations=[];thirdAnimations=[];fourthAnimations=[];fifthAnimations=[];fourthLayers={};remainingLayers={};remainingAnimations=[];const art=document.createElement('div');art.className='stage-art';stage.append(art);stage.classList.toggle('mirrored',index===3);stage.style.setProperty('--player-ink',['#a46369','#493b3e','#ffffff','#886760','#4c101c','#ffffff','#39415f','#a45d61','#74659b','#18064e','#29102f','#632d34'][index]);t.layers.forEach((layer,j)=>{if(index===1&&layer.name==='Really')return;if(index===2&&j>0)return;const img=document.createElement('img');img.decoding='async';img.src=sceneImageSource(index,layer,j,t.layers.length);img.alt='';img.className=(index===9&&j===0?'landscape':'');(index===1&&j>0?art.querySelector('.second-character'):index===4&&j>0?art.querySelector('.fifth-components'):index===6&&layer.name==='沃玛'?art.querySelector('.remaining-window'):art).append(img);if(index===0)setupFirstLayer(img,layer.name);else if(index===1)setupSecondLayer(img,layer.name);else if(index===3)setupFourthLayer(img,layer.name);else if(index===4)setupFifthLayer(img,layer.name);else if(index>=5)setupRemainingLayer(img,layer.name);else animateLayer(img,index,layer.name);if(index===1&&j===0)setupSecondScene(art);if(index===2&&j===0)setupThirdScene(art);if(index===3&&j===0)setupFourthScene(art);if(index===4&&j===0)setupFifthScene(art);if(index>=5&&j===0)setupRemainingScene(art);if(index===7&&j===0){const disk=document.createElement('div');disk.className='sun-disc';art.append(disk)}});if(index===0)setupFirstScene(art);$('#title').textContent=t.title;$('#header-title').textContent=t.title;$('#stage-number').textContent=`${String(index+1).padStart(2,'0')} / 12`;audio.src=`audio/${index+1}.mp3`;if(index===3&&!reducedMotion.matches)fourthController=createFourthMotion(fourthLayers,audio);if(index===7)eighthController=createEighthMotion(remainingLayers,audio,art,reducedMotion);seek.value=0;$('#current').textContent='0:00';$('#duration').textContent='0:00';updateFavorite();renderList();if(autoplay)audio.play().catch(()=>{});updatePlay()}
function updatePlay(){$('#play').textContent=audio.paused?'▶':'Ⅱ';$('#play').setAttribute('aria-label',audio.paused?'播放':'暂停');const button=stage.querySelector('.hotspot.toggle');if(button){button.setAttribute('aria-label',audio.paused?'播放':'暂停');button.innerHTML=audio.paused?'<svg viewBox="0 0 40 48" aria-hidden="true"><path d="M5 4 Q5 1 9 3 L36 21 Q40 24 36 27 L9 45 Q5 47 5 43 Z"/></svg>':'<svg viewBox="0 0 40 48" aria-hidden="true"><rect x="6" y="4" width="10" height="40" rx="3"/><rect x="24" y="4" width="10" height="40" rx="3"/></svg>'}}
function updateFavorite(){let on=favorites.has(index);$('#favorite').textContent=on?'♥':'♡';$('#favorite').setAttribute('aria-pressed',on);const heart=stage.querySelector('.hotspot.heart');if(heart)heart.setAttribute('aria-pressed',String(on))}
$('#play').onclick=()=>audio.paused?audio.play().catch(()=>{}):audio.pause();$('#previous').onclick=()=>select(index-1,true);$('#next').onclick=()=>select(index+1,true);$('#favorite').onclick=()=>{favorites.has(index)?favorites.delete(index):favorites.add(index);try{localStorage.setItem('warma-favorites',JSON.stringify([...favorites]))}catch{};updateFavorite()};$('#volume').oninput=e=>audio.volume=Number(e.target.value);audio.volume=.8;seek.oninput=()=>{if(Number.isFinite(audio.duration))audio.currentTime=Number(seek.value)/1000*audio.duration};audio.ontimeupdate=()=>{seek.value=audio.duration?audio.currentTime/audio.duration*1000:0;$('#current').textContent=format(audio.currentTime)};audio.onloadedmetadata=()=>$('#duration').textContent=format(audio.duration);audio.onplay=updatePlay;audio.onpause=updatePlay;audio.onended=()=>select(index+1,true);$('#list-toggle').onclick=()=>$('.mobile-list').scrollIntoView({behavior:'smooth'});
tracks=TRACKS;
const scenePreloader=createScenePreloader(tracks);

function addStageControls(){const controls=[['heart','收藏歌曲',()=>$('#favorite').click()],['prev','上一首',()=>select(index-1,true)],['toggle','播放或暂停',()=>audio.paused?audio.play().catch(()=>{}):audio.pause()],['next','下一首',()=>select(index+1,true)]];for(const [cls,label,action] of controls){const b=document.createElement('button');b.className=`hotspot ${cls}`;b.setAttribute('aria-label',label);if(cls==='heart')b.innerHTML='<svg viewBox="0 0 48 44" aria-hidden="true"><path d="M24 39 C20 36 4 25 4 14 C4 3 17 0 24 9 C31 0 44 3 44 14 C44 25 28 36 24 39 Z"/></svg>';if(cls==='prev'||cls==='next')b.innerHTML='<svg class="skip-icon '+cls+'" viewBox="0 0 48 40" aria-hidden="true"><path d="M3 3 Q3 1 6 1 H8 Q11 1 11 4 V36 Q11 39 8 39 H6 Q3 39 3 36 Z M12 18 L27 7 Q30 5 30 9 V17 L42 7 Q46 4 46 9 V31 Q46 36 42 33 L30 23 V31 Q30 35 27 33 L12 22 Q9 20 12 18 Z"/></svg>';b.onclick=action;stage.append(b)}const slider=document.createElement('input');slider.type='range';slider.min='0';slider.max='1000';slider.value=seek.value;slider.className='art-seek';slider.setAttribute('aria-label','画面中的播放进度');slider.oninput=()=>{if(Number.isFinite(audio.duration))audio.currentTime=Number(slider.value)/1000*audio.duration};stage.append(slider)}
function selectScene(i,autoplay=false){mountScene(i,autoplay);addStageControls();updatePlay();updateFavorite();frameScheduler.refresh()}
audio.addEventListener('timeupdate',()=>{const s=stage.querySelector('.art-seek');if(s)s.value=seek.value});

// Slide complete canvases only after the incoming images are ready.
let transitionAnimations = [], transitionVersion = 0;
function select(i, autoplay = false) {
  const version = ++transitionVersion;
  const nextIndex = (i + tracks.length) % tracks.length;
  const direction = nextIndex === (index - 1 + tracks.length) % tracks.length ? -1 : 1;
  transitionAnimations.forEach(animation => animation.cancel());
  transitionAnimations = [];
  document.querySelectorAll('.transition-old').forEach(node => node.remove());
  stage.style.visibility = '';

  if (reducedMotion.matches) { selectScene(i, autoplay); removeSceneEntry(); scenePreloader.neighbors(index); return; }
  const old = stage.cloneNode(true);
  old.removeAttribute('id');
  old.classList.add('transition-old');
  old.setAttribute('aria-hidden', 'true');
  // Cloning does not preserve Web Animations: freeze the visible pose instead.
  const originals = stage.querySelectorAll('*');
  old.querySelectorAll('*').forEach((node, n) => {
    const style = getComputedStyle(originals[n]);
    node.style.transform = style.transform;
    node.style.opacity = style.opacity;
    node.style.animation = 'none';
  });
  old.querySelectorAll('button, input').forEach(node => { node.tabIndex = -1; });
  stage.parentElement.append(old);
  selectScene(i, autoplay);

  // The old scene had its own partial entry animation. The full-canvas slide
  // replaces it, preventing a blank strip and two competing movements.
  removeSceneEntry();
  stage.style.visibility = 'hidden';
  const images = [...stage.querySelectorAll('img')];
  Promise.all(images.map(img => img.decode().catch(() => {}))).then(() => {
    if (version !== transitionVersion) return;
    stage.style.visibility = '';
    if (reducedMotion.matches) { old.remove(); scenePreloader.neighbors(index); return; }
    const options = {duration: 420, easing: 'cubic-bezier(.4,0,.2,1)', fill: 'both'};
    const outgoing = old.animate([{transform:'translateX(0)'},{transform:`translateX(${-direction * 100}%)`}], options);
    const incoming = stage.animate([{transform:`translateX(${direction * 100}%)`},{transform:'translateX(0)'}], options);
    transitionAnimations = [outgoing, incoming];
    outgoing.finished.then(() => {
      if (version !== transitionVersion) return;
      old.remove(); incoming.cancel(); transitionAnimations = [];
      scenePreloader.neighbors(index);
    }).catch(() => old.remove());
  });
};

function removeSceneEntry() {
  const art = stage.querySelector('.stage-art');
  for (const animations of [firstAnimations, secondAnimations, thirdAnimations, fourthAnimations, fifthAnimations, remainingAnimations]) {
    for (let n = animations.length - 1; n >= 0; n--) {
      if (animations[n].effect?.target === art) { animations[n].cancel(); animations.splice(n, 1); }
    }
  }
}
// Render the first scene at rest; playback begins only on user action.
selectScene(0, false);
removeSceneEntry();
scenePreloader.neighbors(0);

reducedMotion.addEventListener('change',()=>{
 const time=audio.currentTime,playing=!audio.paused;
 select(index,false);
 const version=transitionVersion;
 audio.addEventListener('loadedmetadata',()=>{
  if(version!==transitionVersion)return;
  audio.currentTime=time;
  if(playing)audio.play().catch(()=>{});
 },{once:true});
});
