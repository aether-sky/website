import { expect } from '@playwright/test';

// Axe cannot resolve textured/gradient backgrounds. Measure the rendered paper
// beneath every text run instead, including its darkest grain and binding edges.
export async function checkPaperContrast(page, incomplete) {
  for (const rule of incomplete) {
    expect(rule.id).toBe('color-contrast');
    for (const node of rule.nodes) {
      expect(node.any.every(check => ['bgGradient', 'bgImage', 'pseudoContent'].includes(check.data?.messageKey))).toBe(true);
      if (node.any.some(check => check.data?.messageKey === 'pseudoContent')) {
        expect(await page.locator(node.target[0]).evaluate(element => !!element.closest('.post-header'))).toBe(true);
      }
      expect(await page.locator(node.target[0]).evaluate(element => !!element.closest('main'))).toBe(true);
    }
  }
  const runs = await page.evaluate(() => {
    const walker = document.createTreeWalker(document.querySelector('main'), NodeFilter.SHOW_TEXT);
    const runs = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!node.textContent.trim()) continue;
      const element = node.parentElement;
      const css = getComputedStyle(element);
      if (css.visibility !== 'visible') continue;
      // Whitespace beside an inline control may contain its focus outline;
      // measure the text itself, not the empty padding around the text run.
      const range = document.createRange();
      range.setStart(node, node.textContent.search(/\S/));
      range.setEnd(node, node.textContent.trimEnd().length);
      const large = parseFloat(css.fontSize) >= 24 || (parseFloat(css.fontSize) >= 18.66 && Number(css.fontWeight) >= 700);
      for (const rect of range.getClientRects()) if (rect.width && rect.height) runs.push({
        text: node.textContent.trim().slice(0, 60), color: css.color, minimum: large ? 3 : 4.5,
        x: rect.x + scrollX, y: rect.y + scrollY, width: rect.width, height: rect.height,
      });
    }
    return runs;
  });
  const png = await page.screenshot({ fullPage: true, style: 'main *{color:transparent!important;-webkit-text-fill-color:transparent!important;text-decoration-color:transparent!important;text-shadow:none!important}' });
  const failures = await page.evaluate(async ({ base64, runs }) => {
    const image = new Image(); image.src = 'data:image/png;base64,' + base64; await image.decode();
    const canvas = document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;
    const ctx = canvas.getContext('2d');ctx.drawImage(image,0,0);
    const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;
    const luminance = rgb => rgb.map(value => {const c=value/255;return c<=.04045?c/12.92:((c+.055)/1.055)**2.4}).reduce((sum,c,i)=>sum+c*[.2126,.7152,.0722][i],0);
    return runs.flatMap(run => {
      const foreground = luminance(run.color.match(/[\d.]+/g).slice(0,3).map(Number));
      let lowest=Infinity;
      for(let y=Math.max(0,Math.ceil(run.y));y<Math.min(canvas.height,run.y+run.height);y+=2) {
        for(let x=Math.max(0,Math.ceil(run.x));x<Math.min(canvas.width,run.x+run.width);x+=2) {
          const offset=(y*canvas.width+x)*4;
          const background=luminance([pixels[offset],pixels[offset+1],pixels[offset+2]]);
          lowest=Math.min(lowest,(Math.max(foreground,background)+.05)/(Math.min(foreground,background)+.05));
        }
      }
      return lowest<run.minimum?[{text:run.text,ratio:lowest,required:run.minimum}]:[];
    });
  }, {base64:png.toString('base64'),runs});
  expect(runs.length).toBeGreaterThan(0);
  expect(failures, 'Rendered paper must meet contrast behind every text run').toEqual([]);
}
