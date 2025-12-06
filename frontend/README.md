# GitHub Metrics Frontend

**For comprehensive frontend development documentation, see [DEVELOPMENT.md](./DEVELOPMENT.md).**

## Quick Start

This is a React + TypeScript + Vite application with shadcn/ui components and Tailwind CSS v4.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## ESLint Configuration

This project uses strict TypeScript ESLint rules configured in `eslint.config.js`:

- `@eslint/js` - JavaScript recommended rules
- `typescript-eslint/strictTypeChecked` - Strict type-checked rules
- `eslint-plugin-react-hooks` - React Hooks rules
- `eslint-plugin-react-refresh` - Fast Refresh rules

**For detailed linting information and examples, see [DEVELOPMENT.md](./DEVELOPMENT.md#code-quality).**
