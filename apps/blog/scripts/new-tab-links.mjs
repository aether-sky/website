// Screen-reader description only, including links with custom labels.
export default function newTabLinks() {
  return tree => {
    const ids = new Set();
    function visit(node, callback) {
      callback(node);
      for (const child of node.children || []) visit(child, callback);
    }
    visit(tree, node => { if (node.properties?.id) ids.add(String(node.properties.id)); });
    let index = 0;
    const tokens = value => Array.isArray(value) ? value : String(value || '').split(/\s+/).filter(Boolean);
    visit(tree, node => {
      if (node.type !== 'element' || node.tagName !== 'a' || String(node.properties?.target).toLowerCase() !== '_blank') return;
      const properties = node.properties;
      properties.rel = [...new Set([...tokens(properties.rel).filter(token => token.toLowerCase() !== 'opener'), 'noopener'])];
      if (node.children.some(child => child.properties?.className?.includes('new-tab-notice'))) return;
      let id;
      do { id = `new-tab-notice-${++index}`; } while (ids.has(id));
      ids.add(id);
      properties.ariaDescribedBy = [...tokens(properties.ariaDescribedBy), id];
      node.children.push({
        type: 'element', tagName: 'span',
        // Referenced hidden text is still exposed as the accessible description.
        // Hiding it from the name prevents the notice being announced twice.
        properties: { id, className: ['new-tab-notice'], hidden: true },
        children: [{ type: 'text', value: ' (opens in new tab)' }],
      });
    });
  };
}
