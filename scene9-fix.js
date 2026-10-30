// Scene 9: body and hair share one breathing transform, keeping their seam fixed.
// Source-frame matching: 0.9872 - 0.00844 sin + 0.00161 cos, period 1.701 s.
function applyScene9Fix(time, layers, reduceMotion) {
 const body=layers['沃玛'], hair=layers['头发'];
 if(!body || !hair || !body.parentElement) return;
 let group=body.parentElement;
 if(!group.classList.contains('scene9-character')) {
  const art=group;
  group=document.createElement('div');
  group.className='scene9-character';
  Object.assign(group.style,{position:'absolute',inset:'0',transformOrigin:'50% 61.98%',willChange:'transform'});
  art.insertBefore(group,body);
  group.append(body,hair);
  hair.style.transformOrigin='48.37% 35.43%';
  hair.style.willChange='transform';
 }
 body.style.transform='none';
 if(reduceMotion){group.style.transform='none';hair.style.transform='none';return}
 const wave=2*Math.PI*time/1.701;
 const sy=.98720131-.00844065*Math.sin(wave)+.00161205*Math.cos(wave);
 group.style.transform=`scaleY(${sy})`;
 const p=2*Math.PI*time;
 const angle=-.20902376-1.07931726*Math.sin(p/1.49)-.21788754*Math.cos(p/1.49);
 const x=.06553798-1.00526404*Math.sin(p/1.535)-.586257*Math.cos(p/1.535);
 const y=-.24125467-.38470031*Math.sin(p/1.415)-.00693061*Math.cos(p/1.415);
 hair.style.transform=`translate(${x/276*100}%,${y/484*100}%) rotate(${-angle}deg)`;
}
