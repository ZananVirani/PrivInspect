import { fileURLToPath } from "url";
import { dirname, resolve } from "path";
import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync, readFileSync, writeFileSync } from "fs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

console.log("🔧 Running post-build script...");

// Copy manifest.json to dist folder
const manifestSrc = resolve(__dirname, "../public/manifest.json");
const manifestDest = resolve(__dirname, "../dist/manifest.json");

try {
  if (existsSync(manifestSrc)) {
    copyFileSync(manifestSrc, manifestDest);
    console.log("✅ Manifest copied to dist folder");
    
    // Fix manifest paths to point to compiled assets
    const manifest = JSON.parse(readFileSync(manifestDest, 'utf8'));
    const assetsDir = resolve(__dirname, "../dist/assets");
    
    if (existsSync(assetsDir)) {
      const assetFiles = readdirSync(assetsDir);
      
      // Find the background script file
      const backgroundFile = assetFiles.find(file => file.startsWith('background.ts-') && file.endsWith('.js'));
      if (backgroundFile) {
        manifest.background.service_worker = `assets/${backgroundFile}`;
        console.log(`✅ Updated background script path: assets/${backgroundFile}`);
      }
      
      // Find the content script file  
      const contentFile = assetFiles.find(file => file.startsWith('content.ts-') && file.endsWith('.js'));
      if (contentFile) {
        manifest.content_scripts[0].js = [`assets/${contentFile}`];
        manifest.web_accessible_resources[0].resources = [`assets/${contentFile}`, "assets/*"];
        console.log(`✅ Updated content script path: assets/${contentFile}`);
      }
      
      // Write updated manifest
      writeFileSync(manifestDest, JSON.stringify(manifest, null, 2));
      console.log("✅ Manifest paths updated for production build");
    }
  } else {
    console.error("❌ Manifest source file not found:", manifestSrc);
  }
} catch (error) {
  console.error("❌ Error copying manifest:", error.message);
}

// Copy icons folder to dist folder
const iconsSrc = resolve(__dirname, "../public/icons");
const iconsDest = resolve(__dirname, "../dist/icons");

try {
  if (existsSync(iconsSrc)) {
    // Create icons directory in dist
    if (!existsSync(iconsDest)) {
      mkdirSync(iconsDest, { recursive: true });
    }

    // Copy all icon files
    const iconFiles = readdirSync(iconsSrc);
    let copiedCount = 0;

    iconFiles.forEach((file) => {
      const srcFile = resolve(iconsSrc, file);
      const destFile = resolve(iconsDest, file);

      if (statSync(srcFile).isFile()) {
        copyFileSync(srcFile, destFile);
        copiedCount++;
      }
    });

    if (copiedCount > 0) {
      console.log(`✅ ${copiedCount} icon(s) copied to dist folder`);
    } else {
      console.log("⚠️  No icon files found to copy");
    }
  } else {
    console.log("⚠️  Icons folder not found - icons will not be available");
  }
} catch (error) {
  console.error("❌ Error copying icons:", error.message);
}

console.log("📦 Extension build completed!");
console.log("🎯 Next steps:");
console.log("   1. Go to chrome://extensions/");
console.log("   2. Enable Developer Mode");
console.log('   3. Click "Load unpacked"');
console.log("   4. Select the /dist folder");
console.log("   5. Click the extension icon to see your React app!");
