export default [
  {
    ignores: ["**/*.min.js", "**/node_modules/**"],
  },
  {
    files: ["**/*.js"],
    languageOptions: {
      globals: {
        // Browser globals
        window: "readonly",
        document: "readonly",
        console: "readonly",
        fetch: "readonly",
        URL: "readonly",
        URLSearchParams: "readonly",
        localStorage: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        AbortController: "readonly",
        Blob: "readonly",
        HTMLElement: "readonly",
        // Chart.js
        Chart: "readonly",
        // Module/CommonJS (for compatibility checks)
        module: "readonly",
      },
    },
    rules: {
      "no-unused-vars": "warn",
      "no-undef": "error",
    },
  },
];
