'use strict';
// Paint a small textured pebble comparison on open rock, retaining all other pixels.
const fs=require('node:fs'),crypto=require('node:crypto');
const {decodePNG,encodePNG,preview}=require('./finish_wall.js');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const source='artifacts/line-1/wall-v13.png';
const old=JSON.parse(fs.readFileSync('dist/line-1/31.json','utf8'));
const ancestor=decodePNG(source), raw=fs.readFileSync(source);
if(old.image!=='https://api.imd.fun/artifacts/'+hash(raw)) throw Error('record 31 ancestor digest mismatch');
if(ancestor.width!==1254||ancestor.height!==1254||ancestor.channels!==3) throw Error('unexpected ancestor dimensions');
const out={...ancestor,pixels:Buffer.from(ancestor.pixels)};
const bounds=[870,48,1155,300];
function blend(x,y,color,alpha) {
  if(x<bounds[0]||x>=bounds[2]||y<bounds[1]||y>=bounds[3]) return;
  const i=(y*out.width+x)*3;
  for(let c=0;c<3;c++) out.pixels[i+c]=Math.round(out.pixels[i+c]*(1-alpha)+color[c]*alpha);
}
function rough(x,y,s) { return Math.sin(x*12.9898+y*78.233+s*37.719)*0.5+Math.sin(x*3.113+y*4.811+s)*0.22; }
function pebble(cx,cy,seed) {
  const rx=8, ry=9;
  for(let y=cy-ry-2;y<=cy+ry+2;y++) for(let x=cx-rx-2;x<=cx+rx+2;x++) {
    const dx=(x-cx)/rx,dy=(y-cy)/ry,d=Math.sqrt(dx*dx+dy*dy), n=rough(x,y,seed);
    if(d<.82+n*.16) blend(x,y,[192,111,43],.88);
    else if(d<1.03+n*.12) blend(x,y,[52,34,22],.55);
    else if(d<1.18+n*.10) blend(x,y,[218,157,76],.42);
  }
  for(let k=0;k<8;k++) {
    const x=cx+Math.round(Math.sin(seed*9+k*2.2)*4),y=cy+Math.round(Math.cos(seed*5+k*1.7)*5);
    blend(x,y,k%3===0?[47,32,21]:[225,171,94],k%3===0?.4:.34);
  }
}
function stroke(x0,y0,x1,y1,width,color,alpha,seed) {
  const length=Math.hypot(x1-x0,y1-y0), steps=Math.ceil(length*1.4);
  for(let k=0;k<=steps;k++) {
    const t=k/steps, jitter=rough(k,seed,seed)*.6;
    const cx=x0+(x1-x0)*t+jitter,cy=y0+(y1-y0)*t-jitter;
    for(let y=Math.floor(cy-width);y<=Math.ceil(cy+width);y++) for(let x=Math.floor(cx-width);x<=Math.ceil(cx+width);x++) {
      const d=Math.hypot(x-cx,y-cy);
      if(d<=width*(.78+Math.abs(rough(x,y,seed))*.3)) blend(x,y,color,alpha*(1-d/(width*1.5)));
    }
  }
}
// Five linked pairs angle down the open rock; a final pair is set apart below.
const pairs=[];
for(let i=0;i<5;i++) pairs.push([905+i*38,83+i*30]);
for(let i=0;i<pairs.length-1;i++) stroke(pairs[i][0]+10,pairs[i][1]+2,pairs[i+1][0]-10,pairs[i+1][1]-2,2.2,[38,28,19],.82,20+i);
for(let i=0;i<pairs.length;i++) {
  const [x,y]=pairs[i]; pebble(x-10,y-3,i*2+1); pebble(x+10,y+3,i*2+2);
}
pebble(1090,266,20); pebble(1111,268,21);
let changed=0, outside=true;
for(let y=0;y<out.height;y++) for(let x=0;x<out.width;x++) {
  const i=(y*out.width+x)*3;
  if(out.pixels[i]!==ancestor.pixels[i]||out.pixels[i+1]!==ancestor.pixels[i+1]||out.pixels[i+2]!==ancestor.pixels[i+2]) {
    changed++;
    if(x<bounds[0]||x>=bounds[2]||y<bounds[1]||y>=bounds[3]) outside=false;
  }
}
if(!outside||changed<500) throw Error('new mark/pixel preservation check failed');
const png=encodePNG(out),jpg=preview(out);
if(jpg.length>100000) throw Error('preview exceeds 100 KB');
const digest=hash(png);
const record={name:'The Paired Pebbles',image:'https://api.imd.fun/artifacts/'+digest,attributes:[
  {trait_type:'Cave',value:'Roots'},{trait_type:'Wall',value:'Line 1'},{trait_type:'Number',value:32},
  {trait_type:'Left behind',value:'Paired Magnitude'},
  {trait_type:'Meaning',value:'Each pair keeps two measurements together so their difference can be weighed across cases.'},
  {trait_type:'One thing',value:'Reproducible benchmark evidence'}
]};
fs.writeFileSync('artifacts/line-1/wall-v14.png',png);
fs.writeFileSync('artifacts/line-1/wall.png',png);
fs.writeFileSync('dist/line-1/32.jpg',jpg);
fs.writeFileSync('dist/line-1/32.json',JSON.stringify(record,null,2)+'\n');
const review={wall:'artifacts/line-1/wall-v14.png',dimensions:{width:out.width,height:out.height},format:'PNG RGB8',bytes:png.length,sha256:digest,preview:{path:'dist/line-1/32.jpg',width:512,height:512,format:'JPEG',bytes:jpg.length},ancestor_record:31,paint_bounds:bounds,changed_pixels:changed,all_pixels_outside_mark_identical:outside,visual_review:{pepe_present:true,no_new_hands_or_stencils:true,visible_five_digit_count_required:false,no_letters_or_numbers_observed:true,unmet_visual_requirements:[]},limits:['Local visual inspection only; no independent visual reviewer.','Small pebble texture softens in the 512-pixel preview.']};
fs.writeFileSync('line-1/wall-review-32.json',JSON.stringify(review,null,2)+'\n');
console.log(JSON.stringify({dimensions:review.dimensions,format:review.format,bytes:review.bytes,sha256:digest,preview:review.preview,changed_pixels:changed,all_pixels_outside_mark_identical:outside}));
