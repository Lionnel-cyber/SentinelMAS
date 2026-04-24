import { defineConfig, loadEnv, type Plugin } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';
import { resolve, extname } from 'path';
import { mkdir, readFile, writeFile } from 'fs/promises';
import { brotliCompress } from 'zlib';
import { promisify } from 'util';
import pkg from './package.json';

const brotliCompressAsync = promisify(brotliCompress);
const BROTLI_EXTENSIONS = new Set(['.js', '.mjs', '.css', '.html', '.svg', '.json', '.txt', '.xml', '.wasm']);

function brotliPrecompressPlugin(): Plugin {
  return {
    name: 'brotli-precompress',
    apply: 'build',
    async writeBundle(outputOptions, bundle) {
      const outDir = outputOptions.dir;
      if (!outDir) return;

      await Promise.all(Object.keys(bundle).map(async (fileName) => {
        const extension = extname(fileName).toLowerCase();
        if (!BROTLI_EXTENSIONS.has(extension)) return;

        const sourcePath = resolve(outDir, fileName);
        const compressedPath = `${sourcePath}.br`;
        const sourceBuffer = await readFile(sourcePath);
        if (sourceBuffer.length < 1024) return;

        const compressedBuffer = await brotliCompressAsync(sourceBuffer);
        await mkdir(resolve(sourcePath, '..'), { recursive: true });
        await writeFile(compressedPath, compressedBuffer);
      }));
    },
  };
}

const RSS_PROXY_ALLOWED_DOMAINS = new Set([
  'feeds.bbci.co.uk', 'www.theguardian.com', 'feeds.npr.org', 'news.google.com',
  'www.aljazeera.com', 'rss.cnn.com', 'www.fema.gov', 'www.dhs.gov',
  'www.who.int', 'www.iaea.org', 'www.cisa.gov', 'news.un.org',
  'tools.cdc.gov', 'www.crisisgroup.org', 'www.reliefweb.int',
  'feeds.reuters.com', 'www.reutersagency.com',
]);

function rssProxyPlugin(): Plugin {
  return {
    name: 'rss-proxy',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (!req.url?.startsWith('/api/rss-proxy')) return next();

        const url = new URL(req.url, 'http://localhost');
        const feedUrl = url.searchParams.get('url');
        if (!feedUrl) {
          res.statusCode = 400;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ error: 'Missing url parameter' }));
          return;
        }

        try {
          const parsed = new URL(feedUrl);
          if (!RSS_PROXY_ALLOWED_DOMAINS.has(parsed.hostname)) {
            res.statusCode = 403;
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ error: `Domain not allowed: ${parsed.hostname}` }));
            return;
          }

          const controller = new AbortController();
          const timer = setTimeout(() => controller.abort(), 12000);
          const response = await fetch(feedUrl, {
            signal: controller.signal,
            headers: { 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/rss+xml, application/xml, */*' },
            redirect: 'follow',
          });
          clearTimeout(timer);

          const data = await response.text();
          res.statusCode = response.status;
          res.setHeader('Content-Type', 'application/xml');
          res.setHeader('Cache-Control', 'public, max-age=300');
          res.setHeader('Access-Control-Allow-Origin', '*');
          res.end(data);
        } catch (error: any) {
          res.statusCode = error.name === 'AbortError' ? 504 : 502;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ error: error.name === 'AbortError' ? 'Feed timeout' : 'Failed to fetch feed' }));
        }
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  Object.assign(process.env, env);

  return {
    define: {
      __APP_VERSION__: JSON.stringify(pkg.version),
    },
    plugins: [
      rssProxyPlugin(),
      brotliPrecompressPlugin(),
      VitePWA({
        registerType: 'autoUpdate',
        injectRegister: false,
        includeAssets: ['favico/favicon.ico', 'favico/apple-touch-icon.png', 'favico/favicon-32x32.png'],
        manifest: {
          name: 'SentinelMAS - Disaster Intelligence',
          short_name: 'SentinelMAS',
          description: 'Real-time disaster monitoring and AI-powered event intelligence.',
          start_url: '/',
          scope: '/',
          display: 'standalone',
          orientation: 'any',
          theme_color: '#0a0f0a',
          background_color: '#0a0f0a',
          icons: [
            { src: '/favico/android-chrome-192x192.png', sizes: '192x192', type: 'image/png' },
            { src: '/favico/android-chrome-512x512.png', sizes: '512x512', type: 'image/png' },
            { src: '/favico/android-chrome-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          ],
        },
        workbox: {
          globPatterns: ['**/*.{js,css,ico,png,svg,woff2}'],
          maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
          navigateFallback: null,
          skipWaiting: true,
          clientsClaim: true,
          cleanupOutdatedCaches: true,
        },
        devOptions: { enabled: false },
      }),
    ],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
        child_process: resolve(__dirname, 'src/shims/child-process.ts'),
        'node:child_process': resolve(__dirname, 'src/shims/child-process.ts'),
        '@loaders.gl/worker-utils/dist/lib/process-utils/child-process-proxy.js': resolve(
          __dirname,
          'src/shims/child-process-proxy.ts'
        ),
      },
    },
    worker: { format: 'es' },
    build: {
      chunkSizeWarningLimit: 1200,
      rollupOptions: {
        onwarn(warning, warn) {
          if (
            warning.code === 'EVAL'
            && typeof warning.id === 'string'
            && warning.id.includes('/onnxruntime-web/dist/ort-web.min.js')
          ) return;
          warn(warning);
        },
        input: {
          main: resolve(__dirname, 'index.html'),
        },
        output: {
          manualChunks(id) {
            if (id.includes('node_modules')) {
              if (id.includes('/maplibre-gl/') || id.includes('/pmtiles/') || id.includes('/@protomaps/basemaps/')) return 'maplibre';
              if (id.includes('/@deck.gl/') || id.includes('/@luma.gl/') || id.includes('/@loaders.gl/') || id.includes('/@math.gl/') || id.includes('/h3-js/')) return 'deck-stack';
              if (id.includes('/d3/')) return 'd3';
              if (id.includes('/topojson-client/')) return 'topojson';
              if (id.includes('/i18next')) return 'i18n';
            }
            const localeMatch = id.match(/\/locales\/(\w+)\.json$/);
            if (localeMatch && localeMatch[1] !== 'en') return `locale-${localeMatch[1]}`;
            return undefined;
          },
        },
      },
    },
    server: {
      port: 3000,
      open: true,
      proxy: {
        '/api/earthquake': {
          target: 'https://earthquake.usgs.gov',
          changeOrigin: true,
          timeout: 30000,
          rewrite: (path) => path.replace(/^\/api\/earthquake/, ''),
        },
      },
    },
  };
});
