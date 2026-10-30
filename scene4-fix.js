// Fourth-scene compositor animations. Sources are losslessly cropped from the
// supplied 1111 × 1932 PNGs; transforms preserve the original canvas pivots.
function createFourthMotion(layers, audio) {
 const specs = {
  braid: {src:'assets/fourth/braid.png', box:[112,673,887,313], pivot:[.5,.4339], period:2.565, a:[-.0325,3.8298,-.0401], x:[-.0578,3.1731,.1076], y:[0,0,0]},
  hair: {src:'assets/fourth/hair.png', box:[340,440,431,400], pivot:[.5,.3409], period:2.29, a:[-.4555,1.5998,.0431], x:[-.369,1.8957,.2341], y:[.0216,.0042,.0392]}
 };
 const animations=[];
 for (const [key,s] of Object.entries(specs)) {
  const el=layers[key]; if(!el) continue;
  const [x,y,w,h]=s.box;
  el.src=s.src;
  Object.assign(el.style,{left:`${x/1111*100}%`,top:`${y/1932*100}%`,width:`${w/1111*100}%`,height:`${h/1932*100}%`,right:'auto',bottom:'auto',transformOrigin:`${(s.pivot[0]*1111-x)/w*100}% ${(s.pivot[1]*1932-y)/h*100}%`,willChange:'transform'});
  const frames=[];
  for(let i=0;i<=120;i++) {
   const p=2*Math.PI*i/120, calc=c=>c[0]+c[1]*Math.sin(p)+c[2]*Math.cos(p);
   const dx=calc(s.x)/552*1111/w*100, dy=calc(s.y)/968*1932/h*100;
   frames.push({offset:i/120, transform:`translate(${dx}%, ${dy}%) rotate(${-calc(s.a)}deg)`});
  }
  const anim=el.animate(frames,{duration:s.period*1000,iterations:Infinity,easing:'linear'});anim.pause();animations.push(anim);
 }
 const events=['play','playing','waiting','pause','seeked','seeking','ratechange','loadedmetadata'];
 let waiting=false;
 function sync(event){
  if(event?.type==='waiting')waiting=true;
  if(event?.type==='playing'||event?.type==='pause')waiting=false;
  const t=Number.isFinite(audio.currentTime)?audio.currentTime:0;
  for(const anim of animations){anim.playbackRate=audio.playbackRate;anim.currentTime=t*1000;if(audio.paused||audio.seeking||waiting)anim.pause();else anim.play()}
 }
 events.forEach(event=>audio.addEventListener(event,sync));document.addEventListener('visibilitychange',sync);sync();
 return {sync,destroy(){events.forEach(event=>audio.removeEventListener(event,sync));document.removeEventListener('visibilitychange',sync);animations.forEach(anim=>anim.cancel())}};
}
