import tseslint from "typescript-eslint";
export default tseslint.config({ ignores: ["src/schema.d.ts"] }, ...tseslint.configs.recommended);
