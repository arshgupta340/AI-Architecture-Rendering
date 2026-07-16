/**
 * Reve v2 layout API types — verbatim mirror of the official SDK
 * (github.com/reve-ai/reve-sdk, reve/v2/types.py), validated against the live
 * API 2026-07-16. Bounding boxes are normalized [0,1]; regions are OBJECT-level.
 */

export interface ReveBBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export type ReveRegionType =
  | "coarse_detail" | "medium_detail" | "fine_detail" | "text" | "hand" | "face";

export interface ReveRegion {
  label: string; // unique, <=255 chars; we encode RegionKeys here
  prompt: string;
  bbox: ReveBBox;
  parent?: string;
  region_type?: ReveRegionType;
  image_index?: number;
  image_region_index?: number;
}

export interface ReveLayout {
  regions: ReveRegion[];
  prompt?: string;
  normalized_edit_instruction?: string;
  width?: number;
  height?: number;
}

/** create_layout edit command (the proven edit primitive). */
export interface ReveChangeCommand {
  op: "change";
  label: string;
  new_description: string;
}

export interface ReveResponse {
  image?: string; // base64
  layout?: ReveLayout;
  content_violation?: boolean;
  request_id?: string;
  credits_used?: number;
  credits_remaining?: number;
}
