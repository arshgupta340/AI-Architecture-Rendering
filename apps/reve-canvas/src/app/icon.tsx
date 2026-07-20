import { ImageResponse } from "next/og";
import { BRAND } from "@/lib/brand";

// Dynamic favicon — a typographic "Strata" mark (no image asset required).
export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0a0a0b",
          color: BRAND.accent,
          fontSize: 22,
          fontWeight: 700,
          fontFamily: "serif",
          letterSpacing: "-1px",
        }}
      >
        S
      </div>
    ),
    { ...size },
  );
}
