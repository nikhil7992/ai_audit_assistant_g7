/// <reference types="vite/client" />

// Tells TypeScript about the env variables we use
interface ImportMetaEnv {
  readonly VITE_API_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}