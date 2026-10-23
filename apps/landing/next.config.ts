import type { NextConfig } from "next";

const config: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  transpilePackages: ["@circuit/ui"],
};
export default config;
