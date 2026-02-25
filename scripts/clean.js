const fs = require('fs');
const path = require('path');

const dirsToRemove = ['.next', 'node_modules/.cache'];

dirsToRemove.forEach((dir) => {
  const fullPath = path.join(process.cwd(), dir);
  try {
    fs.rmSync(fullPath, { recursive: true, force: true });
    console.log(`Removed ${dir}`);
  } catch (e) {
    if (e.code !== 'ENOENT') {
      console.warn(`Failed to remove ${dir}:`, e.message);
    }
  }
});
