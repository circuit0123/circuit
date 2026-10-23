import next from "eslint-config-next";
export default [
  ...next,
  { ignores: [".next/**", "e2e/**"] },
  // Straight apostrophes in plain-language copy ("You're caught up.") are intended.
  { rules: { "react/no-unescaped-entities": "off" } },
];
