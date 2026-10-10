import { mkdir, writeFile } from 'node:fs/promises';
const title=process.argv.slice(2).join(' ').trim();
if(!title){console.error('Usage: pnpm new-post "Your article title"');process.exit(1)}
const slug=title.normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
if(!slug){console.error('Please use a title containing letters or numbers.');process.exit(1)}
const d=new Date();const date=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
await mkdir('src/content/posts',{recursive:true});const path=`src/content/posts/${slug}.md`;
try{await writeFile(path,`---\ntitle: ${JSON.stringify(title)}\ndescription: "Add a short description."\ndate: ${date}\ndraft: true\n---\n\nWrite your post here.\n`,{flag:'wx'});console.log(`Created ${path}. Set draft: false when ready.`)}catch(e){if(e.code==='EEXIST'){console.error('That post already exists; nothing was overwritten.');process.exit(1)}throw e}
