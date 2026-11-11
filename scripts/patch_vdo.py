#!/usr/bin/env python3
"""VDO customization for a pinned, independently downloaded NewPipe source checkout.
SPDX-License-Identifier: GPL-3.0-or-later

Fails if essential upstream locations change, instead of silently shipping a
NewPipe-branded app or exposing unwanted video resolutions.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
from shutil import copyfile

UPSTREAM = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path('upstream').resolve()
ROOT = UPSTREAM / 'app' / 'src' / 'main'

def edit(path: Path, transform, name: str) -> None:
    source = path.read_text(encoding='utf-8')
    output = transform(source)
    if output == source:
        raise RuntimeError(f'Cannot apply {name}: upstream file changed: {path}')
    path.write_text(output, encoding='utf-8')
    print('VDO:', name)

def one_replace(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 anchor, got {count}')
    return source.replace(old, new, 1)
# App label: update app_name even if upstream changes XML attribute order or quoting.
strings = ROOT / 'res/values/strings.xml'

def set_app_name(source: str) -> str:
    # Match a <string> whose name attribute is app_name, regardless of attribute
    # order, quote style, or line breaks. Replace only its text content.
    pattern = re.compile(
        r'(?P<open><string\b(?=[^>]*\bname\s*=\s*["\']app_name["\'])[^>]*>)'
        r'.*?'
        r'(?P<close></string\s*>)',
        flags=re.DOTALL,
    )
    matches = list(pattern.finditer(source))
    if len(matches) > 1:
        raise RuntimeError(f'Expected one app_name string resource, found {len(matches)}')
    if matches:
        match = matches[0]
        return (source[:match.start()] + match.group('open') + 'VDO'
                + match.group('close') + source[match.end():])

    # Some upstream layouts may omit the resource. Add it to the base values file;
    # Android's manifest can then continue to reference @string/app_name.
    if '</resources>' not in source:
        raise RuntimeError('Cannot add app_name: strings.xml has no closing </resources> tag')
    return source.replace(
        '</resources>',
        '    <string name="app_name" translatable="false">VDO</string>\n</resources>',
        1,
    )

edit(strings, set_app_name, 'VDO application name')
if not re.search(
    r'<string\b(?=[^>]*\bname=["\']app_name["\'])[^>]*>\s*VDO\s*</string>',
    strings.read_text(encoding='utf-8'),
    flags=re.DOTALL,
):
    raise RuntimeError('VDO application name was not written to strings.xml')


# Separate install package, if upstream build file uses a literal application id.
# Never change the Java namespace, resource namespace, or import statements.
build = UPSTREAM / 'app/build.gradle.kts'
if not build.exists():
    build = UPSTREAM / 'app/build.gradle'
if build.exists():
    content = build.read_text(encoding='utf-8')
    pat = r'(applicationId\s*(?:=\s*|\s+)["\'])org\.schabi\.newpipe(["\'])'
    updated, n = re.subn(pat, r'\g<1>bd.vdo.player\2', content, count=1)
    if n == 0:
        # AGP can declare applicationId via build variables; attach an override to defaultConfig.
        anchor = 'defaultConfig {'
        if anchor not in content:
            raise RuntimeError('Cannot identify defaultConfig to set a separate applicationId')
        updated = content.replace(anchor, anchor + '\n        applicationId = "bd.vdo.player"\n', 1)
    build.write_text(updated, encoding='utf-8')
    print('VDO: independent application ID bd.vdo.player')
else:
    raise RuntimeError('Upstream Android app build file not found')

# Brand artwork. Vector/round icon in manifest points to the same custom asset.
artwork = Path(__file__).resolve().parent.parent / 'assets/vdo_icon.png'
icon_dest = ROOT / 'res/drawable-nodpi/vdo_icon.png'
icon_dest.parent.mkdir(parents=True, exist_ok=True)
copyfile(artwork, icon_dest)
manifest = ROOT / 'AndroidManifest.xml'

def patch_manifest(s: str) -> str:
    s, n = re.subn(r'android:icon="[^"]+"', 'android:icon="@drawable/vdo_icon"', s, count=1)
    if n != 1:
        raise RuntimeError('AndroidManifest has no application icon')
    s = re.sub(r'android:roundIcon="[^"]+"', 'android:roundIcon="@drawable/vdo_icon"', s, count=1)
    return s
edit(manifest, patch_manifest, 'custom app icon')

# Remove access to the navigation drawer (including edge swipes) on home.
# The toolbar overflow is extended with only the few useful destinations.
activity = ROOT / 'java/org/schabi/newpipe/MainActivity.java'

def patch_activity(s: str) -> str:
    s = one_replace(s,
        'mainBinding.getRoot().setDrawerLockMode(DrawerLayout.LOCK_MODE_UNDEFINED);',
        'mainBinding.getRoot().setDrawerLockMode(DrawerLayout.LOCK_MODE_LOCKED_CLOSED);',
        'hide home sidebar')
    if 'toggle.syncState();' not in s:
        raise RuntimeError('Cannot find drawer toggle setup')
    s = s.replace('toggle.syncState();',
                  'toggle.syncState();\n        toggle.setDrawerIndicatorEnabled(false);', 1)
    # Overflow entrypoints to existing, functioning screens.
    needle = '        updateDrawerNavigation();\n\n        return true;'
    if needle not in s:
        # Handle upstream formatting differences with a whitespace-aware regex.
        pat = r'(\s*updateDrawerNavigation\(\);\s*)(return true;)'
        match = re.search(pat, s)
        if not match:
            raise RuntimeError('Cannot find onCreateOptionsMenu return block')
        needle = match.group(0)
        repl = match.group(1) + _menu_add() + match.group(2)
    else:
        repl = '        updateDrawerNavigation();\n' + _menu_add() + '\n        return true;'
    s = one_replace(s, needle, repl, 'overflow destinations')
    needle2 = 'if (item.getItemId() == android.R.id.home) {'
    handlers = '''if (item.getItemId() == 0x0d010001) {
            NavigationHelper.openSettings(this);
            return true;
        }
        if (item.getItemId() == 0x0d010002) {
            NavigationHelper.openSubscriptionFragment(getSupportFragmentManager());
            return true;
        }
        if (item.getItemId() == 0x0d010003) {
            NavigationHelper.openBookmarksFragment(getSupportFragmentManager());
            return true;
        }
        if (item.getItemId() == 0x0d010004) {
            NavigationHelper.openDownloads(this);
            return true;
        }
        ''' + needle2
    s = one_replace(s, needle2, handlers, 'overflow navigation handler')
    return s

def _menu_add() -> str:
    return '''        menu.add(0, 0x0d010001, 300, "Settings")
                .setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER);
        menu.add(0, 0x0d010002, 301, "Subscriptions")
                .setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER);
        menu.add(0, 0x0d010003, 302, "Playlists")
                .setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER);
        menu.add(0, 0x0d010004, 303, "Downloads")
                .setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER);
'''
edit(activity, patch_activity, 'home without sidebar; minimal overflow')

# Filter actual playback / download stream lists to ONLY these resolutions.
# If the source video provides none, no unsupported resolution is offered.
list_helper = ROOT / 'java/org/schabi/newpipe/util/ListHelper.java'

def patch_quality(s: str) -> str:
    anchor = '.flatMap(List::stream)'
    filter_line = ('.flatMap(List::stream)\n'
                   '                .filter(stream -> stream.getResolution().equals("360p")\n'
                   '                        || stream.getResolution().equals("1080p")\n'
                   '                        || stream.getResolution().equals("1440p"))')
    # Only patch the video-stream method, not earlier unrelated streams.
    start = s.index('final List<VideoStream> allInitialStreams')
    stop = s.index('.collect(Collectors.toList());', start)
    segment = s[start:stop]
    if segment.count(anchor) != 1:
        raise RuntimeError('Expected one flatMap in sorted video stream method')
    segment = segment.replace(anchor, filter_line, 1)
    # The source method has an upstream gate that otherwise excludes 1440p.
    # Keep only the exact three allowed resolutions, and no higher-resolution gate.
    first = segment.index(anchor) + len(anchor)
    segment2 = segment[:first] + ("\n                .filter(stream -> "
        "stream.getResolution().equals(\"360p\") || "
        "stream.getResolution().equals(\"1080p\") || "
        "stream.getResolution().equals(\"1440p\"))\n                ")
    return s[:start] + segment2 + s[stop:]
edit(list_helper, patch_quality, 'restrict quality to 360p, 1080p, 1440p')

# Match the default-quality settings selector to the same three choices.
def restrict_resolution_settings(s: str) -> str:
    marker = 'public static List<String> getSortedResolutionList('
    p = s.find(marker)
    if p < 0:
        raise RuntimeError('Cannot locate default resolution settings selector')
    opening = s.find('{', p)
    depth = 0
    closing = None
    for k in range(opening, len(s)):
        if s[k] == '{':
            depth += 1
        elif s[k] == '}':
            depth -= 1
            if depth == 0:
                closing = k
                break
    if closing is None:
        raise RuntimeError('Unclosed default resolution method')
    replacement = '{\n        return Arrays.asList("360p", "1080p", "1440p");\n    }'
    return s[:opening] + replacement + s[closing+1:]
edit(list_helper, restrict_resolution_settings, 'default quality picker has three values')

print('VDO patch complete. Source is a modified NewPipe GPL-3.0-or-later project.')
