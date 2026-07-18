/**
 * Filesystem locations for config, playlists, preview cache and downloads.
 */
import * as os from "os";
import * as path from "path";

export const CONFIG_DIR = path.join(os.homedir(), ".freesoundconnect");
export const CONFIG_PATH = path.join(CONFIG_DIR, "config.json");
export const PLAYLISTS_PATH = path.join(CONFIG_DIR, "playlists.json");
export const LOG_PATH = path.join(CONFIG_DIR, "error.log");
export const PREVIEW_CACHE_DIR = path.join(CONFIG_DIR, "previews");
export const DOWNLOAD_DIR = path.join(
  os.homedir(), "Documents", "FreesoundConnect");
