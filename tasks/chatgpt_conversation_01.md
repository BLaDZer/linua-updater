I tried to build my linux python app with pyinstaller on github actions but got an error:

```
Run ./scripts/build.sh
[build] Activating virtual environment
[build] Installing PyInstaller and dependencies
[build] Building executable via build.spec
59 INFO: PyInstaller: 6.22.1, contrib hooks: 2026.6
59 INFO: Python: 3.10.20
60 INFO: Platform: Linux-6.17.0-1022-azure-x86_64-with-glibc2.39
60 INFO: Python environment: /home/runner/work/linua-updater/linua-updater/.venv
173 INFO: UPX is available but is disabled on non-Windows due to known compatibility problems.
174 INFO: Module search paths (PYTHONPATH):
['/opt/hostedtoolcache/Python/3.10.20/x64/lib/python310.zip',
 '/opt/hostedtoolcache/Python/3.10.20/x64/lib/python3.10',
 '/opt/hostedtoolcache/Python/3.10.20/x64/lib/python3.10/lib-dynload',
 '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages',
 '/home/runner/work/linua-updater/linua-updater']
287 INFO: checking Analysis
287 INFO: Building Analysis because Analysis-00.toc is non existent
287 INFO: Looking for Python shared library...
297 INFO: Using Python shared library: /opt/hostedtoolcache/Python/3.10.20/x64/lib/libpython3.10.so.1.0
297 INFO: Running Analysis Analysis-00.toc
297 INFO: Target bytecode optimization level: 0
298 INFO: Initializing module dependency graph...
298 INFO: Initializing module graph hook caches...
307 INFO: Analyzing modules for base_library.zip ...
786 INFO: Processing standard module hook 'hook-heapq.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
890 INFO: Processing standard module hook 'hook-encodings.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
2132 INFO: Processing standard module hook 'hook-math.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
2309 INFO: Processing standard module hook 'hook-pickle.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
3982 INFO: Caching module dependency graph...
4027 INFO: Analyzing /home/runner/work/linua-updater/linua-updater/linua_updater/__main__.py
4030 INFO: Processing standard module hook 'hook-urllib3.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/_pyinstaller_hooks_contrib/stdhooks'
4234 INFO: Processing pre-safe-import-module hook 'hook-backports.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/pre_safe_import_module'
4234 INFO: SetuptoolsInfo: initializing cached setuptools info...
7748 INFO: Setuptools: 'backports' appears to be a full setuptools-vendored copy - creating alias to 'setuptools._vendor.backports'!
7753 INFO: Processing standard module hook 'hook-setuptools.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
7783 INFO: Processing standard module hook 'hook-platform.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
7785 INFO: Processing pre-safe-import-module hook 'hook-distutils.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/pre_safe_import_module'
7785 INFO: Processing pre-find-module-path hook 'hook-distutils.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/pre_find_module_path'
7936 INFO: Processing standard module hook 'hook-distutils.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
7994 INFO: Processing standard module hook 'hook-distutils.util.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
8069 INFO: Processing standard module hook 'hook-sysconfig.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
8092 INFO: Processing standard module hook 'hook-_osx_support.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
8162 INFO: Processing pre-safe-import-module hook 'hook-packaging.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/pre_safe_import_module'
8230 INFO: Processing pre-safe-import-module hook 'hook-typing_extensions.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/pre_safe_import_module'
8428 INFO: Processing standard module hook 'hook-multiprocessing.util.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
8552 INFO: Processing standard module hook 'hook-xml.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
8789 INFO: Processing standard module hook 'hook-_ctypes.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
9220 INFO: Processing pre-safe-import-module hook 'hook-jaraco.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/pre_safe_import_module'
9220 INFO: Setuptools: 'jaraco' appears to be a full setuptools-vendored copy - creating alias to 'setuptools._vendor.jaraco'!
9227 INFO: Processing standard module hook 'hook-setuptools._vendor.jaraco.text.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
9236 INFO: Processing pre-safe-import-module hook 'hook-importlib_resources.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/pre_safe_import_module'
9242 INFO: Processing pre-safe-import-module hook 'hook-more_itertools.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/pre_safe_import_module'
9242 INFO: Setuptools: 'more_itertools' appears to be a setuptools-vendored copy - creating alias to 'setuptools._vendor.more_itertools'!
9683 INFO: Processing pre-safe-import-module hook 'hook-importlib_metadata.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/pre_safe_import_module'
9683 INFO: Setuptools: 'importlib_metadata' appears to be a setuptools-vendored copy - creating alias to 'setuptools._vendor.importlib_metadata'!
9698 INFO: Processing standard module hook 'hook-setuptools._vendor.importlib_metadata.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
9699 INFO: Processing pre-safe-import-module hook 'hook-zipp.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/pre_safe_import_module'
9700 INFO: Setuptools: 'zipp' appears to be a setuptools-vendored copy - creating alias to 'setuptools._vendor.zipp'!
10077 INFO: Processing pre-safe-import-module hook 'hook-tomli.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/pre_safe_import_module'
10435 INFO: Processing standard module hook 'hook-pkg_resources.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
10566 INFO: Processing pre-safe-import-module hook 'hook-platformdirs.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/pre_safe_import_module'
10566 INFO: Setuptools: 'platformdirs' appears to be a setuptools-vendored copy - creating alias to 'setuptools._vendor.platformdirs'!
10748 INFO: Processing pre-safe-import-module hook 'hook-wheel.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/pre_safe_import_module'
10748 INFO: Setuptools: 'wheel' appears to be a setuptools-vendored copy - creating alias to 'setuptools._vendor.wheel'!
11441 INFO: Processing standard module hook 'hook-PyQt6.QtCore.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
11534 INFO: Processing standard module hook 'hook-PyQt6.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
12020 INFO: Processing standard module hook 'hook-PyQt6.QtWidgets.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
12463 INFO: Processing standard module hook 'hook-PyQt6.QtGui.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
13406 INFO: Processing standard module hook 'hook-certifi.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/_pyinstaller_hooks_contrib/stdhooks'
13434 INFO: Processing standard module hook 'hook-charset_normalizer.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/_pyinstaller_hooks_contrib/stdhooks'
13727 INFO: Processing standard module hook 'hook-webbrowser.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
13732 INFO: Processing module hooks (post-graph stage)...
13828 INFO: Processing standard module hook 'hook-PyQt6.QtDBus.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
14195 INFO: Processing standard module hook 'hook-difflib.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
14576 INFO: Performing binary vs. data reclassification (152 entries)
14862 INFO: Looking for ctypes DLLs
14873 INFO: Analyzing run-time hooks ...
14876 INFO: Including run-time hook 'pyi_rth_inspect.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/rthooks'
14878 INFO: Including run-time hook 'pyi_rth_pyqt6.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/rthooks'
14879 INFO: Processing pre-find-module-path hook 'hook-_pyi_rth_utils.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/pre_find_module_path'
14880 INFO: Processing standard module hook 'hook-_pyi_rth_utils.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks'
14882 INFO: Including run-time hook 'pyi_rth_pkgutil.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/rthooks'
14883 INFO: Including run-time hook 'pyi_rth_setuptools.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/rthooks'
14884 INFO: Including run-time hook 'pyi_rth_multiprocessing.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/rthooks'
14886 INFO: Including run-time hook 'pyi_rth_pkgres.py' from '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/hooks/rthooks'
14900 INFO: Creating base_library.zip...
14927 INFO: Looking for dynamic libraries
16559 WARNING: Library not found: could not resolve 'libxcb-image.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-egl-integration.so'.
16559 WARNING: Library not found: could not resolve 'libxkbcommon-x11.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-egl-integration.so'.
16559 WARNING: Library not found: could not resolve 'libxcb-keysyms.so.1', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-egl-integration.so'.
16559 WARNING: Library not found: could not resolve 'libxcb-util.so.1', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-egl-integration.so'.
16559 WARNING: Library not found: could not resolve 'libxcb-shape.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-egl-integration.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-xkb.so.1', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-egl-integration.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-icccm.so.4', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-egl-integration.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-render-util.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-egl-integration.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-cursor.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-egl-integration.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-image.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-glx-integration.so'.
16560 WARNING: Library not found: could not resolve 'libxkbcommon-x11.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-glx-integration.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-keysyms.so.1', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-glx-integration.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-util.so.1', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-glx-integration.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-shape.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-glx-integration.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-xkb.so.1', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-glx-integration.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-icccm.so.4', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-glx-integration.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-render-util.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-glx-integration.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-cursor.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/xcbglintegrations/libqxcb-glx-integration.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-image.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/platforms/libqxcb.so'.
16560 WARNING: Library not found: could not resolve 'libxkbcommon-x11.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/platforms/libqxcb.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-keysyms.so.1', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/platforms/libqxcb.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-util.so.1', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/platforms/libqxcb.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-shape.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/platforms/libqxcb.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-xkb.so.1', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/platforms/libqxcb.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-icccm.so.4', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/platforms/libqxcb.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-render-util.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/platforms/libqxcb.so'.
16560 WARNING: Library not found: could not resolve 'libxcb-cursor.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/platforms/libqxcb.so'.
16561 WARNING: Library not found: could not resolve 'libtiff.so.5', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/plugins/imageformats/libqtiff.so'.
16561 WARNING: Library not found: could not resolve 'libxcb-image.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/lib/libQt6XcbQpa.so.6'.
16561 WARNING: Library not found: could not resolve 'libxkbcommon-x11.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/lib/libQt6XcbQpa.so.6'.
16561 WARNING: Library not found: could not resolve 'libxcb-keysyms.so.1', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/lib/libQt6XcbQpa.so.6'.
16561 WARNING: Library not found: could not resolve 'libxcb-util.so.1', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/lib/libQt6XcbQpa.so.6'.
16561 WARNING: Library not found: could not resolve 'libxcb-shape.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/lib/libQt6XcbQpa.so.6'.
16561 WARNING: Library not found: could not resolve 'libxcb-xkb.so.1', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/lib/libQt6XcbQpa.so.6'.
16561 WARNING: Library not found: could not resolve 'libxcb-icccm.so.4', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/lib/libQt6XcbQpa.so.6'.
16561 WARNING: Library not found: could not resolve 'libxcb-render-util.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/lib/libQt6XcbQpa.so.6'.
16561 WARNING: Library not found: could not resolve 'libxcb-cursor.so.0', dependency of '/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyQt6/Qt6/lib/libQt6XcbQpa.so.6'.
16583 INFO: Warnings written to /home/runner/work/linua-updater/linua-updater/build/build/warn-build.txt
16619 INFO: Graph cross-reference written to /home/runner/work/linua-updater/linua-updater/build/build/xref-build.html
16643 INFO: checking PYZ
16643 INFO: Building PYZ because PYZ-00.toc is non existent
16643 INFO: Building PYZ (ZlibArchive) /home/runner/work/linua-updater/linua-updater/build/build/PYZ-00.pyz
16990 INFO: Building PYZ (ZlibArchive) /home/runner/work/linua-updater/linua-updater/build/build/PYZ-00.pyz completed successfully.
Traceback (most recent call last):
  File "/home/runner/work/linua-updater/linua-updater/.venv/bin/pyinstaller", line 6, in <module>
    sys.exit(_console_script_run())
  File "/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/__main__.py", line 231, in _console_script_run
    run()
  File "/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/__main__.py", line 215, in run
    run_build(pyi_config, spec_file, **vars(args))
  File "/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/__main__.py", line 70, in run_build
    PyInstaller.building.build_main.main(pyi_config, spec_file, **kwargs)
  File "/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/building/build_main.py", line 1275, in main
    build(specfile, distpath, workpath, clean_build)
  File "/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/building/build_main.py", line 1213, in build
    exec(code, spec_namespace)
  File "/home/runner/work/linua-updater/linua-updater/build.spec", line 32, in <module>
    exe = EXE(
  File "/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/building/api.py", line 654, in __init__
    self.toc = normalize_toc(self.toc)
  File "/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/building/datastruct.py", line 327, in normalize_toc
    return _normalize_toc(toc, _TOC_TYPE_PRIORITIES, _type_case_normalization_fcn)
  File "/home/runner/work/linua-updater/linua-updater/.venv/lib/python3.10/site-packages/PyInstaller/building/datastruct.py", line 345, in _normalize_toc
    for dest_name, src_name, typecode in toc:
ValueError: not enough values to unpack (expected 3, got 2)
Error: Process completed with exit code 1.
```


The actual failure is **not the Qt/XCB warnings**. Your build gets through `Analysis` and `PYZ`, then crashes while constructing `EXE`:

```text
build.spec", line 32, in <module>
    exe = EXE(
...
ValueError: not enough values to unpack (expected 3, got 2)
```

That strongly indicates that **line 32 of `build.spec` is passing a 2-tuple/list entry to an `EXE(...)` argument that PyInstaller 6.22 expects to contain 3-tuples**.

PyInstaller's spec-file API uses several different tuple formats. In particular, `datas` and `binaries` use **2-tuples** `(source, destination)`, while certain arguments passed directly to `EXE` use **3-tuples**. ([PyInstaller][1])

### Most likely problem

I suspect your spec has something structurally like:

```python
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    ...
)
```

**if this is a one-file build**, or perhaps you've manually constructed something like:

```python
exe = EXE(
    pyz,
    a.scripts,
    [
        ("some/file", "."),
    ],
    ...
)
```

The error comes from PyInstaller doing essentially:

```python
for dest_name, src_name, typecode in toc:
```

and encountering an entry with only:

```python
("some/file", ".")
```

instead of:

```python
("some/name", "some/file", "DATA")
```

### The important distinction

For `Analysis`, this is correct:

```python
datas=[
    ("foo.png", "."),
]
```

because `Analysis.datas` expects `(source, destination)`. ([PyInstaller][1])

Likewise:

```python
binaries=[
    ("foo.so", "."),
]
```

is correct for `Analysis.binaries`. ([PyInstaller][1])

But if you're constructing a TOC that goes directly into `EXE`, PyInstaller expects the normalized three-element form.

### What I need to see

Please paste your **`build.spec`**, especially around line 32. The traceback tells us almost exactly where the problem is:

```text
build.spec", line 32, in <module>
    exe = EXE(
```

With the spec file, I can point to the exact entry that is wrong and give you the corrected version.

The Qt warnings such as:

```text
Library not found: libxcb-image.so.0
Library not found: libxkbcommon-x11.so.0
...
```

are a **separate issue**. They may cause the resulting PyQt application to fail to start on some Linux systems, but they are not what caused this particular PyInstaller exception. Your build actually gets past dynamic-library analysis and fails later while normalizing the `EXE` table of contents.

[1]: https://pyinstaller.org/en/latest/spec-files.html?utm_source=chatgpt.com "Using Spec Files — PyInstaller 6.21.0 documentation"



Yes — the spec file reveals the problem. Your `a.binaries += [(aria2_bin, ".")]` and `a.binaries += [(sevenzip_bin, ".")]` are **correct**. The problem is that you're passing `a.binaries` and `a.datas` directly to `EXE` **without converting them to the TOC format expected by PyInstaller 6.22.1**.

The key clue is exactly:

```text
for dest_name, src_name, typecode in toc:
ValueError: not enough values to unpack (expected 3, got 2)
```

### Why this happens

`Analysis.binaries` uses 2-tuples:

```python
(source, destination)
```

as documented by PyInstaller. ([PyInstaller][1])

But the `EXE` object's internal TOC expects entries in the form:

```python
(destination, source, typecode)
```

Your manually-added entries therefore eventually reach `EXE` as 2-tuples.

There's also an important clue in your spec: you're modifying `a.binaries` **after** `Analysis()`:

```python
a.binaries += [(aria2_bin, ".")]
```

Normally PyInstaller's generated spec handles these lists internally. For your use case, the cleanest solution is to add the binaries to `Analysis` itself.

## Recommended fix

Change your spec to build the binary list first, then give it to `Analysis`:

```python
# -*- mode: python ; coding: utf-8 -*-

import os

base_dir = os.path.dirname(os.path.abspath(SPEC))

extra_binaries = []

aria2_name = "aria2c.exe" if os.name == "nt" else "aria2c"
aria2_bin = os.path.join(base_dir, "tools", aria2_name)
if os.path.exists(aria2_bin):
    extra_binaries.append((aria2_bin, "."))

sevenzip_names = ["7z.exe", "7z.dll"] if os.name == "nt" else ["7zz"]
for name in sevenzip_names:
    sevenzip_bin = os.path.join(base_dir, "tools", name)
    if os.path.exists(sevenzip_bin):
        extra_binaries.append((sevenzip_bin, "."))

a = Analysis(
    ['linua_updater/__main__.py'],
    pathex=[base_dir],
    binaries=extra_binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Linua-Updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

This is also consistent with PyInstaller's documented one-file spec structure: `EXE` receives `a.binaries` and `a.datas` in one-file mode. ([PyInstaller][1])

### But there's a second thing I'd change

Your current code:

```python
a.binaries += [(aria2_bin, ".")]
```

isn't necessarily inherently wrong with PyInstaller's `Analysis` object. The bigger issue is that you're apparently hitting a **PyInstaller 6.22 compatibility/change issue around the resulting TOC**.

I'd therefore avoid mutating `a.binaries` after `Analysis` and use:

```python
binaries=extra_binaries
```

directly in `Analysis`, as above.

### One more concern: `upx=True`

Your log says:

```text
UPX is available but is disabled on non-Windows due to known compatibility problems.
```

So on GitHub's Linux runner, this:

```python
upx=True
```

doesn't actually give you UPX compression. It's not the cause of your failure, though.

---

## And the Qt warnings

These are independent:

```text
libxcb-image.so.0
libxkbcommon-x11.so.0
libxcb-keysyms.so.1
libxcb-util.so.1
...
libtiff.so.5
```

They matter for your **Linux runtime**, especially because you're using PyQt6, but they aren't responsible for this traceback.

After fixing the spec, I'd expect you to potentially encounter runtime problems if those libraries aren't available on the target distribution.

In particular, don't blindly copy the missing `.so` files from the GitHub runner into your application. Some of these are **system libraries that should generally be supplied by the target Linux distribution**, rather than bundled indiscriminately.

### In short

Your immediate change is:

**Instead of:**

```python
a = Analysis(..., binaries=[], ...)

...

a.binaries += [(aria2_bin, ".")]
a.binaries += [(sevenzip_bin, ".")]
```

**do:**

```python
extra_binaries = [
    (aria2_bin, "."),
    (sevenzip_bin, "."),
]

a = Analysis(..., binaries=extra_binaries, ...)
```

Then rebuild with a clean build directory:

```bash
pyinstaller --clean build.spec
```

PyInstaller explicitly supports supplying additional binaries through `Analysis.binaries`, using `(source, destination)` pairs. ([PyInstaller][1])

**One caveat:** if the error persists with the revised spec, I'd want to see the exact `PyInstaller 6.22.1` `EXE` signature/TOC handling, because your `EXE(..., a.binaries, a.datas, [])` structure otherwise looks like the standard one-file spec generated by PyInstaller. In that case, the next thing I'd investigate is the **extra empty `[]` argument** and whether your installed 6.22.1 changed the expected positional arguments.

[1]: https://pyinstaller.org/en/latest/spec-files.html?utm_source=chatgpt.com "Using Spec Files — PyInstaller 6.21.0 documentation"
