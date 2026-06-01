# assets

Drop a `hermes.ico` here to brand the window and the installer. If it's absent the
build still works — PyInstaller just omits the custom icon (see
`build/pyinstaller/HermesWebUI.spec`).

Recommended: a multi-resolution `.ico` (16/32/48/256 px). You can generate one from
a PNG with ImageMagick:

```bash
magick convert hermes-256.png -define icon:auto-resize=256,48,32,16 hermes.ico
```
