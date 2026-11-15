import js from "@eslint/js";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "src/api/schema.d.ts", "playwright-report", "test-results"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended, jsxA11y.flatConfigs.recommended],
    languageOptions: { ecmaVersion: 2023, globals: { ...globals.browser, ...globals.node } },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true, allowExportNames: ["buttonVariants", "badgeVariants", "useTheme"] },
      ],
      // Radix renders its own labelable element; the rule cannot see through our wrappers.
      "jsx-a11y/label-has-associated-control": ["error", { controlComponents: ["Switch", "Checkbox", "Input", "Select"], assert: "either", depth: 3 }],
      // A scrollable region must be reachable by keyboard (WCAG 2.1.1), so these roles and tags may take focus.
      "jsx-a11y/no-noninteractive-tabindex": ["error", { tags: ["pre"], roles: ["tabpanel", "log", "region"] }],
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/consistent-type-imports": ["error", { fixStyle: "inline-type-imports" }],
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      eqeqeq: ["error", "always", { null: "ignore" }],
      "no-console": ["warn", { allow: ["warn", "error"] }],
    },
  },
  {
    // Test files may use the looser patterns testing needs.
    files: ["**/*.test.{ts,tsx}", "src/test/**", "e2e/**"],
    rules: { "react-refresh/only-export-components": "off", "@typescript-eslint/no-non-null-assertion": "off" },
  },
);
