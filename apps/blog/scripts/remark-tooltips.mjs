export default function remarkTooltips() {
  return (tree, file) => {
    let count = 0;
    const labelText = node => node.value || (node.children || []).map(labelText).join('');
    function visit(node) {
      if (node.type === 'textDirective' && node.name === 'tooltip') {
        const label = labelText(node);
        const text = node.attributes?.text;
        if (!label.trim() || !text?.trim()) {
          file.message('Tooltips need label text and a text="…" attribute; leaving this directive as plain text.', node);
          node.type = 'text';
          node.value = String(file.value).slice(node.position.start.offset, node.position.end.offset);
          delete node.children;
          delete node.data;
          return;
        }
        const id = `blog-tooltip-${++count}`;
        node.data = {
          hName: 'span',
          hProperties: { className: ['inline-tooltip'] },
          hChildren: [
            { type: 'element', tagName: 'button', properties: { type: 'button', className: ['tooltip-trigger'], ariaDescribedBy: [id], dataTooltip: id }, children: [{ type: 'text', value: label }] },
            { type: 'element', tagName: 'span', properties: { id, role: 'tooltip', popover: 'manual', className: ['tooltip-bubble'] }, children: [{ type: 'text', value: text }] },
          ],
        };
        return;
      }
      for (const child of node.children || []) visit(child);
    }
    visit(tree);
  };
}
