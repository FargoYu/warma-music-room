// Scene 8: source-measured local hair matrices share the same body pulse.
// SCENE8_MOTION stores curves and losslessly cropped original sprite bounds.
function createEighthMotion(layers, audio, art, reducedMotion) {
  const data = SCENE8_MOTION, animations = [];
  const multiply = (a,b) => [
    a[0]*b[0]+a[1]*b[3], a[0]*b[1]+a[1]*b[4], a[0]*b[2]+a[1]*b[5]+a[2],
    a[3]*b[0]+a[4]*b[3], a[3]*b[1]+a[4]*b[4], a[3]*b[2]+a[4]*b[5]+a[5]
  ];
  function matrixAt(name, t) {
    const phase = ((t-data.pulseReset)/data.pulsePeriod%1+1)%1;
    const pulse = .5*(1-Math.cos(Math.PI*phase));
    const body = data.body[0].map((x,i)=>x+data.body[1][i]*pulse);
    if(name==='沃玛') return body;
    const cfg = data.layers[name], angle = 2*Math.PI*t/cfg.period;
    const basis = [1];
    for(let k=1;k<=cfg.harmonics;k++) basis.push(Math.sin(k*angle),Math.cos(k*angle));
    const local = cfg.coef[0].map((_,i)=>basis.reduce((sum,x,k)=>sum+x*cfg.coef[k][i],0));
    return multiply(body,local);
  }
  function spriteTransform(name,t) {
    const f=matrixAt(name,t), [x,y,w,h]=data.sprites[name].box;
    // Reference matrices use 552 × 968; original PNG canvas is 1111 × 1932.
    const sx=1111/552, sy=1932/968;
    const a=f[0], b=f[3]*sy/sx, c=f[1]*sx/sy, d=f[4];
    const dx=(a-1)*x+c*y+f[2]*sx, dy=b*x+(d-1)*y+f[5]*sy;
    return `translate(${dx/w*100}%, ${dy/h*100}%) matrix(${a},${b},${c},${d},0,0)`;
  }
  function animate(el,frames,duration=6000) {
    const animation=el.animate(frames,{duration,easing:'linear',fill:'both'});
    animation.pause();animations.push(animation);
  }
  for(const [name,sprite] of Object.entries(data.sprites)) {
    const el=layers[name];if(!el)continue;
    const [x,y,w,h]=sprite.box;
    el.src=sprite.src;
    Object.assign(el.style,{left:`${x/1111*100}%`,top:`${y/1932*100}%`,width:`${w/1111*100}%`,height:`${h/1932*100}%`,right:'auto',bottom:'auto',transformOrigin:'0 0',willChange:'transform'});
    // Interpolate between the original video's 30 fps poses on the compositor.
    animate(el,Array.from({length:181},(_,i)=>({offset:i/180,transform:spriteTransform(name,i/30)})));
  }
  const sun=art.querySelector('.sun-disc'),s=data.sun;
  if(sun) {
    const maxX=s.minDiameters[0]+s.rangeDiameters[0],maxY=s.minDiameters[1]+s.rangeDiameters[1];
    Object.assign(sun.style,{left:`${s.center[0]/552*100}%`,top:`${s.center[1]/968*100}%`,width:`${maxX/552*100}%`,height:`${maxY/968*100}%`,aspectRatio:'auto',background:s.color,willChange:'transform'});
    animate(sun,Array.from({length:181},(_,i)=>{
      const phase=((i/30-s.reset)/s.period%1+1)%1,f=.5*(1+Math.cos(Math.PI*phase));
      return {offset:i/180,transform:`translate(-50%,-50%) scale(${(s.minDiameters[0]+s.rangeDiameters[0]*f)/maxX},${(s.minDiameters[1]+s.rangeDiameters[1]*f)/maxY})`};
    }));
  }
  // Full-canvas transitions are handled by the player.
  const events=['play','playing','waiting','pause','seeking','seeked','ratechange','loadedmetadata'];
  let waiting=false;
  function sync(event) {
    if(event?.type==='waiting')waiting=true;
    if(event?.type==='playing'||event?.type==='pause')waiting=false;
    const still=reducedMotion.matches,t=still?0:(Number.isFinite(audio.currentTime)?audio.currentTime:0);
    for(const anim of animations) {
      anim.playbackRate=audio.playbackRate;anim.currentTime=t*1000;
      if(document.hidden||still||audio.paused||audio.seeking||waiting)anim.pause();else anim.play();
    }
    if(still)animations.at(-1).currentTime=1000;
  }
  events.forEach(e=>audio.addEventListener(e,sync));
  document.addEventListener('visibilitychange',sync);reducedMotion.addEventListener('change',sync);sync();
  return {destroy(){events.forEach(e=>audio.removeEventListener(e,sync));document.removeEventListener('visibilitychange',sync);reducedMotion.removeEventListener('change',sync);animations.forEach(a=>a.cancel())}};
}
