[app]

# ---- identity ---------------------------------------------------------------
title = Lingora
package.name = lingora
package.domain = org.lingora
version = 1.0.0

# ---- sources ----------------------------------------------------------------
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json,txt
source.include_patterns = fonts/*
source.exclude_dirs = .github, bin, .buildozer, __pycache__, tests
source.exclude_patterns = *.pyc, *.db, *.md

# ---- requirements -------------------------------------------------------------
# pure Kivy (no KivyMD).  pyjnius + android: Text-to-Speech, permissions, night mode
# plyer: optional fallback for Text-to-Speech
requirements = python3,kivy==2.3.0,pyjnius,android,plyer

# ---- display ------------------------------------------------------------------------
orientation = portrait
fullscreen = 0
android.window_softinput_mode = adjustResize

# ---- android -------------------------------------------------------------------------
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.logcat_filters = *:S python:D

[buildozer]
log_level = 2
warn_on_root = 1
