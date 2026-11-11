# VDO (Android) — build kit

**Status:** VDO source customization and a GitHub Actions APK build workflow. No APK has been built or device-tested in this package. The source is fetched and patched during the GitHub Actions run; this ZIP is not a complete offline Android source tree.

**Based on:** TeamNewPipe/NewPipe, pinned to tag `v0.29.3` (10 November 2026), under GPL-3.0-or-later. **VDO is independent of Team NewPipe.** This modified source remains under GPL-3.0-or-later. The workflow fetches upstream sources, including their LICENSE and notices, and modifies them; keep attribution and source availability when distributing APKs.

### Intended behavior

Existing NewPipe features are retained: video search and ad-free stream playback, background audio, video and audio downloading, popup player, play queue and local playlists, channel subscriptions, related streams. Customization: VDO name, icon, separate application ID, no home navigation drawer, direct overflow access to Settings / Subscriptions / Playlists / Downloads, and stream resolution filter with only 360p, 1080p, 1440p. Only resolutions the source actually supplies can play; playback can fail when a source changes or those qualities are unavailable. The quality selector is filtered, **but unavailable qualities are not yet presented as three disabled buttons**. Some existing upstream settings and submenus remain. These differences need a tested APK/UI pass before calling the app finished.

### To build in the existing repository

The repository is: https://github.com/Ishtiaque786/Vdo

1. Add **the contents of this folder** (preserving `.github/workflows/build-vdo.yml`, `scripts/patch_vdo.py`, and `assets/vdo_icon.png`) to your repository. A ZIP file by itself uploaded to GitHub will not run the build.
2. Open **Actions → Build VDO Android APK → Run workflow**. The workflow can also run on a push when its files change.
3. After a green build, open the run and download the **VDO-Android-APK** artifact. Unzip it to get `VDO-debug.apk`, then install it on Android 6.0+ (subject to device support).

If the build fails, inspect the first actual Gradle or Python error in the Actions log. The patch intentionally stops if the upstream source location changes instead of silently producing an incorrectly branded/unrestricted app.

### Files

- `.github/workflows/build-vdo.yml` — pinned Android build pipeline and APK artifact publishing.
- `scripts/patch_vdo.py` — branding, navigation and resolution restrictions.
- `assets/vdo_icon.png` — original VDO launcher icon.

**Security:** This workflow creates a debug-signed APK suitable for personal tests, not an official app-store release. Do not treat a debug-signed APK as production. Installation requires reviewing Android's unknown-apps warning.
