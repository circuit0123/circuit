import type { NextConfig } from "next";

const config: NextConfig = {
  devIndicators: false,
  transpilePackages: ["@circuit/ui", "@circuit/api-client"],
};
export default config;
