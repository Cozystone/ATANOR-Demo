/** @type {import('next').NextConfig} */
const desktopExport = process.env.HOMAGE_TAURI_EXPORT === "1";

const nextConfig = {
  ...(desktopExport
    ? {
        output: "export",
        images: {
          unoptimized: true,
        },
      }
    : {}),
};

export default nextConfig;
