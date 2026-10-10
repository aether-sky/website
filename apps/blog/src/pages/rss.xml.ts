import type { APIRoute } from 'astro';
import { publishedPosts } from '../lib/posts';
import { site as settings } from '../site';
const xml=(value:string)=>value.replace(/[<>&"']/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[c]!));
export const GET:APIRoute=async({site})=>{
const posts=await publishedPosts();const base=site!;
const items=posts.map(p=>{const url=new URL(`/posts/${p.id}/`,base).href;return `<item><title>${xml(p.data.title)}</title><description>${xml(p.data.description)}</description><link>${xml(url)}</link><guid>${xml(url)}</guid><pubDate>${p.data.date.toUTCString()}</pubDate></item>`}).join('');
return new Response(`<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>${xml(settings.title)}</title><description>${xml(settings.description)}</description><link>${xml(base.href)}</link><language>en</language>${items}</channel></rss>`,{headers:{'Content-Type':'application/rss+xml; charset=utf-8'}});
};
