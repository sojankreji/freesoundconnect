// electron-builder afterPack hook.
//
// Without a paid Apple Developer ID we can't notarize, but we CAN apply a
// valid ad-hoc signature to the whole .app bundle (sealed resources included).
// electron-builder's default macOS output for an unsigned build is only
// "linker-signed" (just the inner Mach-O), which Gatekeeper reports as
// "damaged and can't be opened" — a dead end for users. A proper deep ad-hoc
// signature turns that into the normal "unidentified developer" prompt, which
// users can allow via right-click → Open or System Settings › Privacy.
const { execFileSync } = require('child_process');
const path = require('path');

exports.default = async function afterPack(context) {
  const { electronPlatformName, appOutDir } = context;
  if (electronPlatformName !== 'darwin') return;

  const appName = context.packager.appInfo.productFilename;
  const appPath = path.join(appOutDir, `${appName}.app`);

  console.log(`[afterPack] ad-hoc signing ${appPath}`);
  // "-" identity == ad-hoc. --deep signs nested helpers/frameworks inside-out.
  execFileSync('codesign', ['--force', '--deep', '--sign', '-', appPath], {
    stdio: 'inherit',
  });
};
