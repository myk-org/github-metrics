module.exports = {
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended-type-checked', 'plugin:@vitest/recommended'],
  parser: '@typescript-eslint/parser',
  plugins: ['@typescript-eslint', '@vitest'],
  parserOptions: {
    project: true,
    tsconfigRootDir: __dirname,
  },
  rules: {},
  overrides: [
    {
      files: ["**/*.test.ts", "**/*.test.tsx", "**/__tests__/**"],
      rules: {
        // Test files may use mocks and test utilities that trigger unsafe rules
        // TODO: Gradually type test utilities to remove these suppressions
        "@typescript-eslint/no-unsafe-call": "off",
        "@typescript-eslint/no-unsafe-member-access": "off",
        "@typescript-eslint/no-unsafe-assignment": "off",
      },
    },
  ],
  root: true,
};
