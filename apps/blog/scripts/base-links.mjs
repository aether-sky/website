// Prefix public content URLs at build time; article source/wording stays intact.
export default function baseLinks({ base = '/' } = {}) {
  const prefix = base.replace(/\/$/, '');
  const url = value => typeof value === 'string' && /^\/(?!\/)/.test(value) && !value.startsWith(prefix + '/') ? prefix + value : value;
  return tree => {
    if (!prefix) return;
    function visit(node) {
      if (node.type === 'element') for (const attr of ['src', 'href', 'poster']) {
        if (node.properties?.[attr]) node.properties[attr] = url(node.properties[attr]);
      }
      // Raw HTML embeds in Markdown are trusted owner-authored blog content.
      if (node.type === 'raw' || node.type === 'html') {
        node.value = node.value.replace(/\b(src|href|poster)=(['"])(\/[^'"\s]*)\2/g, (_, attr, quote, value) => `${attr}=${quote}${url(value)}${quote}`);
      }
      for (const child of node.children || []) visit(child);
    }
    visit(tree);
  };
}
