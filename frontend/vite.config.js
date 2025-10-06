import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [
        react(),
        VitePWA({
            registerType: 'autoUpdate',
            includeAssets: ['favicon.svg'],
            manifest: {
                name: 'Crash Pay',
                short_name: 'CrashPay',
                description: 'Crash Pay is a Fintech platform',
                start_url: '/',
                display: 'standalone',
                background_color: '#0d1117',
                theme_color: '#0d1117',
                icons: [
                    { src: 'favicon.svg', sizes: 'any', type: 'image/svg+xml' }
                ]
            },
            devOptions: {
                enabled: true
            }
        })
    ],
    server: {
        host: '0.0.0.0',
        port: 5173,
        proxy: {
            '/api': {
                target: 'http://localhost:8080',
                changeOrigin: true,
                secure: false,
                // Extend dev proxy timeouts for long LLM responses
                timeout: 190000,
                proxyTimeout: 190000,
                // Ensure streaming works in dev
                configure: (proxy) => {
                    proxy.on('proxyRes', (_proxyRes, _req, res) => {
                        res.setHeader('Connection', 'keep-alive')
                        if (typeof res.flushHeaders === 'function') {
                            res.flushHeaders()
                        }
                    })
                }
            }
        }
    },
    build: {
        outDir: 'dist'
    }
})
