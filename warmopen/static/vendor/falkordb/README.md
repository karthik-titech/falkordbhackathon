# FalkorDB Canvas browser bundle

Official source: https://github.com/FalkorDB/falkordb-ui/tree/main/web-components/canvas
Package: @falkordb/canvas 0.3.3 (MIT).
Bundler: esbuild 0.25.12; ECMAScript module splitting; minified with legal comments preserved.
The package lock records the exact dependency graph. LICENSE and
THIRD_PARTY_LICENSES.txt accompany the browser files.

Built in a disposable node:22-alpine Docker container, with npm lifecycle scripts
and audit disabled. Entry: node_modules/@falkordb/canvas/dist/index.js. Output:
esbuild --bundle --minify --splitting --format=esm --outdir=/out --legal-comments=eof.
The 3D engine is a local lazy-loaded chunk. No runtime CDN or remote font is used.

The handwritten adapter handles public conference data, fixed colors, selected
profiles, resize, and a 2D fallback when WebGL2 is unavailable. Source data and
private credentials are never passed to the component as database connection details.
