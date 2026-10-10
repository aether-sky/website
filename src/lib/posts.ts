import { getCollection } from 'astro:content';
export async function publishedPosts() { return (await getCollection('posts', ({ data }) => !data.draft)).sort((a,b) => b.data.date.valueOf()-a.data.date.valueOf()); }
