import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // node:sqlite, mammoth va unpdf server tomonda ishlaydi — bundle qilinmasin.
  serverExternalPackages: ["mammoth", "unpdf", "docx"],
  experimental: {
    // Fayl yuklash (hujjat tahlili) uchun katta body limiti.
    serverActions: { bodySizeLimit: "25mb" },
  },
};

export default nextConfig;
