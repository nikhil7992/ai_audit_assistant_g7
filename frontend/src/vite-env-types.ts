/// <reference types="vite/client" />

// Tells TypeScript that .module.css imports return an object of class name strings
declare module '*.module.css' {
  const classes: Record<string, string>
  export default classes
}

// Tells TypeScript about the env variables we use
interface ImportMetaEnv {
  readonly VITE_API_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}