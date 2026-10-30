// Scene-specific composition and audio-time rendering. Player lifecycle lives in app.js.
function motion(name, i){if(i===0)return ''; if(name.includes('海浪'))return 'wave'; if(name.includes('对话框'))return 'bubble'; if(name.includes('星球')||name==='蜘蛛'||name==='甜甜圈'||name==='Really')return 'orbit'; if(/发|辫|呆毛/.test(name))return 'hair'; if(/沃玛|身体|头|忆雨/.test(name))return 'motion';return ''}
// Positions sampled from three reference frames in each corresponding video section.
// Translation values are percentages of the source canvas; timings remain easy to adjust.
const measuredMotion={
  5:{'星球':[[0,-.83],[1.44,-.83],[1.44,-.83]]}
};
const sceneSeconds=[8,7,5,7,5,6,6,5,7,7,6,6];
function animateLayer(img,scene,name){
 if(reducedMotion.matches)return;
 const samples=measuredMotion[scene]?.[name];
 if(samples)img.animate(samples.map(([x,y])=>({transform:`translate(${x}%, ${y}%)`})),{duration:sceneSeconds[scene]*1000,iterations:Infinity,direction:'alternate',easing:'linear'});
 if(scene===8&&name.includes('海浪'))img.animate([{transform:'translateY(65%)',offset:0},{transform:'translateY(65%)',offset:.55},{transform:'translateY(0)',offset:1}],{duration:7000,iterations:Infinity,direction:'alternate',easing:'ease-in-out'});
 if(scene===10&&name.includes('对话框')){const n=Number(name.match(/[123]/)?.[0]||1);img.animate([{opacity:0,offset:0},{opacity:0,offset:Math.min(.8,n*.16)},{opacity:1,offset:Math.min(.9,n*.16+.08)},{opacity:1,offset:1}],{duration:6000,iterations:Infinity});}
}
// First scene: the video shows a rapid vertical squash, anchored at the feet,
// and a matching stretch of the spider from the top of its thread.
let firstAnimations=[], secondAnimations=[], thirdAnimations=[], fourthAnimations=[], fifthAnimations=[];
let fourthLayers={}, fourthController=null, eighthController=null;
let remainingLayers={}, remainingAnimations=[];
function setupFirstLayer(img,name){
 img.dataset.layer=name;
 if(reducedMotion.matches)return;
 let frames,origin;
 if(name==='沃玛'){origin='50% 61.9%';frames=[{transform:'scaleY(.978)'},{transform:'scaleY(1)',offset:.87},{transform:'scaleY(1)'}]}
 if(name==='蜘蛛'){origin='24.3% 24.0%';frames=[{transform:'scaleY(1.06)'},{transform:'scaleY(1)',offset:.87},{transform:'scaleY(1)'}]}
 if(frames){img.style.transformOrigin=origin;const a=img.animate(frames,{duration:450,iterations:Infinity,easing:'linear'});a.pause();firstAnimations.push(a)}
}
function setupFirstScene(art){
 if(!reducedMotion.matches){const a=art.animate([{transform:'translateX(9.5%)'},{transform:'translateX(0)'}],{duration:400,easing:'cubic-bezier(.16,1,.3,1)',fill:'forwards'});a.pause();firstAnimations.push(a)}
 const elapsed=document.createElement('span');elapsed.className='first-elapsed';elapsed.textContent='0:41';art.append(elapsed);
}
function updateFirstFrame(){
 if(index!==0)return;
 const seconds=Number.isFinite(audio.currentTime)?audio.currentTime:0;
 for(const a of firstAnimations)a.currentTime=seconds*1000;
 const marker=sceneNode('[data-layer="进度条"]');if(marker)marker.style.transform=`translateX(${seconds*.13}%)`;
 const elapsed=sceneNode('.first-elapsed');setText(elapsed,format(41+seconds));
}
// Second scene measurements come from 10 fps reference samples. Each rotation
// uses its own pivot; the common vertical pulse is applied to the character group.
const secondRotations={
 '麻花辫（右）':{pivot:'46% 38%',degrees:[-1.5,.5,2,1.5,0,-3.5,-4,-4,-4,-2.5,-1.5]},
 '麻花辫（左）':{pivot:'35% 42%',degrees:[-.5,1,1,.5,-.5,-1,-2.5,-3,-2.5,-1.5,-.5]},
 '侧发':{pivot:'48% 37%',degrees:[1.5,2,3,3,2,-.5,-1.5,-1.5,0,1.5,1.5]},
 '沃玛の刘海':{pivot:'43% 29%',degrees:[2,2.5,2,1,-.5,-2,-2.5,-3,-1.5,0,2]}
};
function setupSecondLayer(img,name){
 if(reducedMotion.matches)return;
 const config=secondRotations[name];if(!config)return;
 img.style.transformOrigin=config.pivot;
 const frames=config.degrees.map(deg=>({transform:`rotate(${deg}deg)`}));
 const a=img.animate(frames,{duration:1000,iterations:Infinity,easing:'linear'});a.pause();secondAnimations.push(a);
}
function setupSecondScene(art){
 if(!reducedMotion.matches){const a=art.animate([{transform:'translateX(9.5%)'},{transform:'translateX(0)'}],{duration:400,easing:'cubic-bezier(.16,1,.3,1)',fill:'forwards'});a.pause();secondAnimations.push(a)}
 // The four words travel at the same measured speed, with distinct fade slopes.
 const specs=[
  {x:18.3,y:12.86,alpha:.93,fade:1.52},
  {x:68.8,y:20.35,alpha:1.22,fade:1.52},
  {x:18.5,y:29.44,alpha:2.70,fade:1.50,appear:.48,rise:.50},
  {x:66.85,y:27.06,alpha:1.80,fade:1.17,appear:.68,rise:.16}
 ];
 specs.forEach((spec,i)=>{const word=document.createElement('img');word.src='assets/really.png';word.alt='';word.className='second-word';word.style.left=spec.x+'%';word.dataset.word=i;art.append(word)});
 art._wordSpecs=specs;
 const dot=document.createElement('span');dot.className='second-progress-dot';art.append(dot);
 const current=document.createElement('span');current.className='second-time second-current';art.append(current);
 const total=document.createElement('span');total.className='second-time second-total';total.textContent='2:16';art.append(total);
 const character=document.createElement('div');character.className='second-character';art.append(character);
 if(!reducedMotion.matches){
  const pulse=character.animate([{transform:'scaleY(.978)'},{transform:'scaleY(1)',offset:.9},{transform:'scaleY(1)'}],{duration:500,iterations:Infinity,easing:'linear'});pulse.pause();secondAnimations.push(pulse);
 }
}
function updateSecondFrame(){
 if(index!==1)return;
 const time=Number.isFinite(audio.currentTime)?audio.currentTime:0;
 for(const a of secondAnimations)a.currentTime=time*1000;
 const art=sceneNode('.stage-art'),phase=time%1.7833;
 art.querySelectorAll('.second-word').forEach(word=>{const spec=art._wordSpecs[Number(word.dataset.word)];word.style.top=spec.y+'%';word.style.transform=`translateY(${phase*25*1932/1111}cqw)`;word.style.opacity=Math.max(0,Math.min(1,spec.alpha-spec.fade*phase,spec.appear===undefined?1:(phase-spec.appear)/spec.rise))});
 const dot=sceneNode('.second-progress-dot');if(dot)dot.style.left=(18.4+time*.19)+'%';
 const current=sceneNode('.second-current');setText(current,format(2.5+time));
}
// Third scene uses small, sampled movements rather than a whole-canvas drift.
function setupThirdScene(art){
 if(!reducedMotion.matches){
  const entry=[{offset:0,transform:'translateX(7%)'},{offset:.05/.65,transform:'translateX(5.25%)'},{offset:.15/.65,transform:'translateX(3.26%)'},{offset:.25/.65,transform:'translateX(1.99%)'},{offset:.35/.65,transform:'translateX(1.09%)'},{offset:.45/.65,transform:'translateX(.54%)'},{offset:.55/.65,transform:'translateX(.18%)'},{offset:1,transform:'translateX(0)'}];
  const a=art.animate(entry,{duration:650,easing:'linear',fill:'forwards'});a.pause();thirdAnimations.push(a);
 }
 const elements=document.createElement('div');elements.className='third-components';art.append(elements);
 for(const name of ['person','planet','star1','star2','star3']){
  const img=document.createElement('img');img.src=`assets/third/${name}.png`;img.alt='';img.dataset.third=name;
  const pivots={planet:'26.27% 57.85%',star1:'24.46% 32.23%',star2:'34.96% 47.31%',star3:'81.16% 58.88%'};
  if(pivots[name])img.style.transformOrigin=pivots[name];elements.append(img);
 }
 const cover=document.createElement('span');cover.className='third-duration-cover';art.append(cover);
 const elapsed=document.createElement('span');elapsed.className='third-time third-current';art.append(elapsed);
 const total=document.createElement('span');total.className='third-time third-total';total.textContent='3:14';art.append(total);
 const dot=document.createElement('span');dot.className='third-progress-dot';art.append(dot);
}
function updateThirdFrame(){
 if(index!==2)return;
 const time=Number.isFinite(audio.currentTime)?audio.currentTime:0;
 for(const animation of thirdAnimations)animation.currentTime=time*1000;
 if(!reducedMotion.matches){
  const sample=Math.max(0,Math.min(46,Math.round((time-.45)*10)));
  for(const [name,values] of Object.entries(THIRD_MOTION)){
   const element=sceneNode(`[data-third="${name}"]`);if(!element)continue;
   const value=values[sample];let angle=0,dx,dy;
   if(name==='person'){[dx,dy]=value}else{[angle,dx,dy]=value;angle=Math.max(-6,Math.min(6,-angle))}
   element.style.transform=`translate(${dx/552*100}%, ${dy/968*100}%) rotate(${angle}deg)`;
  }
 }
 const dot=sceneNode('.third-progress-dot');if(dot)dot.style.left=(42.4+Math.max(0,time-.45)*.36)+'%';
 const current=sceneNode('.third-current');setText(current,format(73+time));
}
// The original background includes the upright braids; the separate rear-hair
// and front-hair sprites rotate independently over the fixed character.
function setupFourthLayer(img,name){
 if(name==='麻花辫'){img.dataset.fourth='braid';img.style.transformOrigin='50% 43.39%';fourthLayers.braid=img}
 if(name==='头发'){img.dataset.fourth='hair';img.style.transformOrigin='50% 34.09%';fourthLayers.hair=img}
}
function setupFourthScene(art){
 if(!reducedMotion.matches){
  const positions=[[0,12],[.05,8.88],[.15,3.8],[.25,1.81],[.35,.72],[.45,.18],[.55,0]];
  const entry=positions.map(([time,x])=>({offset:time/.55,transform:`translateX(${x}%)`}));
  const a=art.animate(entry,{duration:550,easing:'linear',fill:'forwards'});a.pause();fourthAnimations.push(a);
 }
 const elapsed=document.createElement('span');elapsed.className='fourth-time fourth-current';art.append(elapsed);
 const total=document.createElement('span');total.className='fourth-time fourth-total';total.textContent='3:56';art.append(total);
 const dot=document.createElement('span');dot.className='fourth-progress-dot';art.append(dot);
}
function updateFourthFrame(){
 if(index!==3)return;
 const time=Number.isFinite(audio.currentTime)?audio.currentTime:0;
 for(const animation of fourthAnimations)animation.currentTime=time*1000;
 const dot=sceneNode('.fourth-progress-dot');if(dot)dot.style.left=(43.85+time*.27)+'%';
 const current=sceneNode('.fourth-current');setText(current,format(64+time));
}
// Fifth scene: the donut compresses around its lower edge while the figure rocks.
function setupFifthLayer(img,name){
 if(name==='沃玛'){img.dataset.fifth='person';img.style.transformOrigin='37.14% 61.98%'}
 if(name==='甜甜圈'){img.dataset.fifth='donut';img.style.transformOrigin='67.03% 61.98%'}
}
function setupFifthScene(art){
 if(!reducedMotion.matches){
  const positions=[[0,14],[.05,9.96],[.15,2.72],[.25,.72],[.35,.18],[.45,0]];
  const entry=positions.map(([time,x])=>({offset:time/.45,transform:`translateX(${x}%)`}));
  const a=art.animate(entry,{duration:450,easing:'linear',fill:'forwards'});a.pause();fifthAnimations.push(a);
 }
 const current=document.createElement('span');current.className='fifth-time';art.append(current);
 const dot=document.createElement('span');dot.className='fifth-progress-dot';art.append(dot);
 const components=document.createElement('div');components.className='fifth-components';art.append(components);
}
function updateFifthFrame(){
 if(index!==4)return;
 const time=Number.isFinite(audio.currentTime)?audio.currentTime:0;
 for(const animation of fifthAnimations)animation.currentTime=time*1000;
 if(!reducedMotion.matches){
  let t=time;while(t>4.85)t-=1;
  const sample=Math.max(0,Math.min(44,(t-.45)*10)),lo=Math.floor(sample),hi=Math.min(44,lo+1),fraction=sample-lo;
  for(const name of ['person','donut']){
   const el=sceneNode(`[data-fifth="${name}"]`);if(!el)continue;
   const a=FIFTH_MOTION[name][lo],b=FIFTH_MOTION[name][hi],mix=i=>a[i]+(b[i]-a[i])*fraction;
   if(name==='person')el.style.transform=`translate(${mix(2)/552*100}%, ${mix(3)/968*100}%) rotate(${-mix(0)}deg) scaleY(${mix(1)})`;
   else el.style.transform=`translate(${mix(1)/552*100}%, ${mix(2)/968*100}%) scaleY(${mix(0)})`;
  }
 }
 const dot=sceneNode('.fifth-progress-dot');if(dot)dot.style.left=(18.38+time*.18)+'%';
 const current=sceneNode('.fifth-time');setText(current,format(6+time));
}
// Scenes 6–12: fitted layer curves and scene-specific elements.
const remainingConfig={
 6:{start:73,color:'#ffffff',dot:40.0},7:{start:82,color:'#344052',dot:40.0},
 8:{start:69,color:'#a45d61',dot:32.0},9:{start:111,color:'#74659b',dot:44.0},
 10:{start:84,color:'#18064e',dot:39.0},11:{start:83,color:'#29102f',dot:39.3},12:{start:48,color:'#632d34',dot:35.0}
};
function setupRemainingLayer(img,name){
 remainingLayers[name]=img;img.dataset.remaining=name;if(REMAINING_MOTION[index+1]?.[name]||name.includes('海浪'))img.style.willChange='transform';
 const motion=REMAINING_MOTION[index+1]?.[name];if(motion)img.style.transformOrigin=motion.pivot[0]+'% '+motion.pivot[1]+'%';if(name==='沃玛'&&REMAINING_PULSE[index+1])img.style.transformOrigin='50% 61.98%';
 if(index===9&&name==='背景.jpg')img.classList.add('remaining-pan-background');
}
function setupRemainingScene(art){
 if(!reducedMotion.matches&&index!==7){
  const entry=art.animate([{transform:'translateX(10%)'},{transform:'translateX(0)'}],{duration:500,easing:'cubic-bezier(.2,.8,.2,1)',fill:'forwards'});entry.pause();remainingAnimations.push(entry);
 }
 if(index===6){const window=document.createElement('div');window.className='remaining-window';art.append(window)}
 const cfg=remainingConfig[index+1],elapsed=document.createElement('span');elapsed.className='remaining-time';elapsed.style.color=cfg.color;art.append(elapsed);
 const dot=document.createElement('span');dot.className='remaining-progress-dot';dot.style.background=cfg.color;art.append(dot);
}
function fittedParam(p,time){const c=p.coef;if(!p.period)return c[0];const phase=2*Math.PI*time/p.period;return c[0]+c[1]*Math.sin(phase)+c[2]*Math.cos(phase)}
function between(value,a,b){return Math.max(0,Math.min(1,(value-a)/(b-a)))}
function interpolateKeys(t,keys){if(t<=keys[0][0])return keys[0][1];for(let i=1;i<keys.length;i++){if(t<=keys[i][0]){const [a,x]=keys[i-1],[b,y]=keys[i];return x+(y-x)*(t-a)/(b-a)}}return keys.at(-1)[1]}
function updateRemainingFrame(){
 if(index<5)return;
 const scene=index+1,time=Number.isFinite(audio.currentTime)?audio.currentTime:0,cfg=remainingConfig[scene];
 for(const animation of remainingAnimations)animation.currentTime=time*1000;
 if(!reducedMotion.matches){
  for(const [name,motion] of Object.entries(REMAINING_MOTION[scene]||{})){
   if(scene===8||scene===9&&(name==='沃玛'||name==='头发'))continue;
   const el=remainingLayers[name];if(!el)continue;
   let [angle,sy,x,y]=motion.params.map(p=>fittedParam(p,time));
   if(name==='沃玛'&&REMAINING_PULSE[scene]){const [period,reset,base,rise]=REMAINING_PULSE[scene];const phase=(((time-reset)/period)%1+1)%1;sy=Math.max(.96,Math.min(1.01,base+rise*phase));angle=0;x=0;y=0}
   if(scene===6&&name==='星球'){angle=0;sy=1;y=0}
   el.style.transform=`translate(${x/276*100}%, ${y/484*100}%) rotate(${-angle}deg) scaleY(${sy})`;
  }
  if(scene===10&&remainingLayers['背景.jpg'])remainingLayers['背景.jpg'].style.transform=`translateX(${-time*8/165*100}%)`;
 }
 if(scene===9){
  applyScene9Fix(time,remainingLayers,reducedMotion.matches);
  const keys=[[0,70],[4.12,70],[4.35,17.6],[4.55,9.5],[4.75,5],[5.15,.6],[5.35,0],[6.65,8]];
  ['海浪（后）','海浪（中）','海浪（前）'].forEach((name,i)=>{const el=remainingLayers[name];if(el)el.style.transform=`translateY(${interpolateKeys(time-i*.18,keys)}%)`});
 }
 if(scene===11){
  const u=between(time,2.2,2.5),v=between(time,4.12,4.42),green=remainingLayers['对话框（3）'],white=remainingLayers['对话框（2）'],newGreen=remainingLayers['对话框（1）'];
  if(green){green.style.transform=`translateY(${-9.1*u-9.7*v}%)`;green.style.opacity='1'}
  if(white){white.style.transform=`translateY(${9.1*(1-v)}%)`;white.style.opacity=String(between(time,2.35,2.55))}
  if(newGreen){newGreen.style.transform='translateY(18.8%)';newGreen.style.opacity=String(between(time,4.28,4.48))}
 }
 const dot=sceneNode('.remaining-progress-dot');if(dot)dot.style.left=(cfg.dot+time*.18)+'%';
 const elapsed=sceneNode('.remaining-time');setText(elapsed,format(cfg.start+time));
}
