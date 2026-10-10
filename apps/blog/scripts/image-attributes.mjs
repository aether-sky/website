import { readFileSync, existsSync } from 'node:fs';
import { resolve, sep } from 'node:path';
// Give locally hosted PNGs intrinsic sizes so the article does not jump as images load.
export default function imageAttributes(){return tree=>{
const root=resolve('public');
function visit(node){if(node.type==='element'&&node.tagName==='img'){
const p=node.properties;p.loading='lazy';p.decoding='async';
if(typeof p.src==='string'&&p.src.startsWith('/images/')){const path=resolve(root,'.'+p.src);if(path.startsWith(root+sep)&&existsSync(path)&&path.endsWith('.png')){const b=readFileSync(path);if(b.length>24&&b.toString('hex',0,8)==='89504e470d0a1a0a'){p.width=b.readUInt32BE(16);p.height=b.readUInt32BE(20)}}}
}for(const child of node.children||[])visit(child)}visit(tree)
}}
