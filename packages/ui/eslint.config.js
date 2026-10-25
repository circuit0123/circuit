import tseslint from "typescript-eslint";
import hooks from "eslint-plugin-react-hooks";

const message = "packages/ui is presentation only. It never talks to the backend; data arrives as props from a hook in apps/app/src/data (CLAUDE.md: Frontend architecture).";

export default tseslint.config(...tseslint.configs.recommended, {
  plugins: { "react-hooks": hooks },
  rules: {
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "warn",
    "no-restricted-imports": ["error", { patterns: [{ group: ["@circuit/api-client", "@circuit/api-client/*", "@supabase/*", "openapi-fetch"], message }] }],
    "no-restricted-globals": ["error", { name: "fetch", message }],
    "no-restricted-properties": ["error", { object: "window", property: "fetch", message }],
  },
});
