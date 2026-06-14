import { useEffect, useMemo } from "react";
import { TilesRenderer, TilesPlugin, TilesAttributionOverlay } from "3d-tiles-renderer/r3f";
import {
  GoogleCloudAuthPlugin,
  GLTFExtensionsPlugin,
  ReorientationPlugin,
  TileCompressionPlugin,
  TilesFadePlugin,
} from "3d-tiles-renderer/plugins";
import { DRACOLoader } from "three/examples/jsm/loaders/DRACOLoader.js";
import { useStore } from "./state/store";

/**
 * Real-world site context: Google Photorealistic 3D Tiles georeferenced around the
 * model. The whole thing is $0 to build/run *until a key is present* — tiles only
 * fetch (and bill) when `geo.enabled` and a key are set.
 *
 * Coordinate strategy — bring the city to the model, not the model to the globe:
 *   • ReorientationPlugin re-centres the tileset so the site lat/lon sits at the
 *     tileset's local origin, Y-up (avoids ECEF's ~6.4e6 m float jitter).
 *   • Our scene is in FEET (Rhino units); tiles are in METRES — so the outer group
 *     scales by 3.2808 (m→ft). This keeps every existing feet-based system
 *     (shadows, entourage heights, box-projected UVs, saved views) untouched.
 *   • The outer group then positions that origin under the building (`siteAnchor`),
 *     nudges it vertically to seat on the terrain (`groundOffset`), and rotates the
 *     context to align with the model's north (`heading`).
 */
const M_TO_FT = 1 / 0.3048; // 3.28084
const DEG2RAD = Math.PI / 180;
// Google's photorealistic tiles are Draco-compressed glTF (JPEG textures, no KTX2).
const DRACO_DECODER_URL = "https://www.gstatic.com/draco/versioned/decoders/1.5.7/";

const attributionStyle: React.CSSProperties = {
  position: "absolute",
  bottom: 6,
  left: "50%",
  right: "auto",
  transform: "translateX(-50%)",
  color: "#fff",
  fontSize: 11,
  lineHeight: 1.3,
  maxWidth: "60%",
  textAlign: "center",
  textShadow: "0 1px 3px rgba(0,0,0,0.9)",
  pointerEvents: "none",
};

export function GeoTiles({ apiToken }: { apiToken: string }) {
  const lat = useStore((s) => s.sky.lat);
  const lng = useStore((s) => s.sky.lng);
  const height = useStore((s) => s.geo.height);
  const heading = useStore((s) => s.geo.heading);
  const groundOffset = useStore((s) => s.geo.groundOffset);
  const anchor = useStore((s) => s.siteAnchor);

  // One Draco decoder for the whole geo session — Google tiles won't decode without it.
  const dracoLoader = useMemo(() => new DRACOLoader().setDecoderPath(DRACO_DECODER_URL), []);
  useEffect(() => {
    return () => {
      dracoLoader.dispose();
    };
  }, [dracoLoader]);

  const [ax, ay, az] = anchor ?? [0, 0, 0];

  return (
    <group
      position={[ax, ay + groundOffset, az]}
      rotation={[0, heading * DEG2RAD, 0]}
      scale={M_TO_FT}
    >
      {/* key forces a clean tileset reload when the key or geolocation changes */}
      {/* args are arrays — TilesPlugin spreads them as constructor args (new plugin(...args)) */}
      <TilesRenderer key={`${apiToken}|${lat.toFixed(6)}|${lng.toFixed(6)}|${height}`}>
        <TilesPlugin plugin={GoogleCloudAuthPlugin} args={[{ apiToken }]} />
        <TilesPlugin plugin={GLTFExtensionsPlugin} args={[{ dracoLoader }]} />
        <TilesPlugin
          plugin={ReorientationPlugin}
          args={[{ lat: lat * DEG2RAD, lon: lng * DEG2RAD, height, recenter: true }]}
        />
        <TilesPlugin plugin={TileCompressionPlugin} />
        <TilesPlugin plugin={TilesFadePlugin} args={[{ fadeDuration: 400 }]} />
        <TilesAttributionOverlay style={attributionStyle} />
      </TilesRenderer>
    </group>
  );
}
