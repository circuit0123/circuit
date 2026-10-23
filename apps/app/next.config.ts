import type { NextConfig } from "next";

const config: NextConfig = {
  transpilePackages: ["@circuit/ui", "@circuit/api-client"],
};
export default config;
